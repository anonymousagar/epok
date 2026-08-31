import hashlib
import hmac
import os
from fastapi import APIRouter, Header, HTTPException, Request, status
from temporalio.client import Client
from models.events import LinearWebhookPayload
from workflows.spec_architecture import SpecArchitectureWorkflow

router = APIRouter(prefix="/webhooks/linear", tags=["Linear Webhook"])


def verify_linear_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    computed = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)


async def get_temporal_client() -> Client:
    temporal_host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    temporal_namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
    return await Client.connect(temporal_host, namespace=temporal_namespace)


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def receive_linear_webhook(
    request: Request,
    linear_signature: str = Header(None, alias="Linear-Signature")
):
    raw_body = await request.body()
    webhook_secret = os.getenv("LINEAR_WEBHOOK_SECRET", "")

    if not linear_signature or not verify_linear_signature(raw_body, linear_signature, webhook_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Linear signature header."
        )

    try:
        payload_data = await request.json()
        payload = LinearWebhookPayload(**payload_data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Malformed payload: {exc}"
        )

    workflow_id = f"epok-linear-{payload.data.id}-{payload.data.updatedAt}"
    repo_name = os.getenv("EPOK_GITHUB_REPO", "anonymousagar/epok")
    branch = os.getenv("EPOK_DEFAULT_BRANCH", "main")
    task_queue = os.getenv("EPOK_TASK_QUEUE", "epok-task-queue")

    try:
        client = await get_temporal_client()
        await client.start_workflow(
            SpecArchitectureWorkflow.run,
            args=[payload.data.id, repo_name, branch],
            id=workflow_id,
            task_queue=task_queue,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to dispatch Temporal workflow: {exc}"
        )

    return {
        "status": "accepted",
        "workflow_id": workflow_id,
        "issue_id": payload.data.id
    }