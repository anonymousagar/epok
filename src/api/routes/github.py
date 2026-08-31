import hashlib
import hmac
import os
from fastapi import APIRouter, Header, HTTPException, Request, status
from temporalio.client import Client
from models.events import GitHubWorkflowRunPayload

router = APIRouter(prefix="/webhooks/github", tags=["GitHub Webhook"])


def verify_github_signature(raw_body: bytes, signature_header: str, secret: str) -> bool:
    if not signature_header.startswith("sha256="):
        return False
    signature = signature_header.split("sha256=")[-1]
    computed = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)


async def get_temporal_client() -> Client:
    temporal_host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    temporal_namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
    return await Client.connect(temporal_host, namespace=temporal_namespace)


@router.post("", status_code=status.HTTP_200_OK)
async def receive_github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256")
):
    raw_body = await request.body()
    webhook_secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")

    if not x_hub_signature_256 or not verify_github_signature(raw_body, x_hub_signature_256, webhook_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid GitHub signature header."
        )

    try:
        payload_data = await request.json()
        payload = GitHubWorkflowRunPayload(**payload_data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Malformed GitHub payload: {exc}"
        )

    workflow_id = None
    if payload.action == "completed" and payload.workflow_run.conclusion == "failure":
        branch_name = payload.workflow_run.head_branch.replace("/", "-")
        workflow_id = f"epok-ci-repair-{payload.workflow_run.id}-{branch_name}"
        try:
            client = await get_temporal_client()
            # Dispatches CI repair signal / workflow start
            await client.start_workflow(
                "CIRepairWorkflow",
                args=[payload.workflow_run.id, payload.workflow_run.head_branch],
                id=workflow_id,
                task_queue=os.getenv("EPOK_TASK_QUEUE", "epok-task-queue"),
            )
        except Exception as exc:
            # Log error without failing webhook response
            pass

    return {
        "status": "ok",
        "run_id": payload.workflow_run.id,
        "conclusion": payload.workflow_run.conclusion,
        "workflow_id": workflow_id
    }