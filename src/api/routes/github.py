import hashlib
import hmac
import os
from fastapi import APIRouter, Header, HTTPException, Request, status
from models.events import GitHubWorkflowRunPayload

router = APIRouter(prefix="/webhooks/github", tags=["GitHub Webhook"])


def verify_github_signature(raw_body: bytes, signature_header: str, secret: str) -> bool:
    if not signature_header.startswith("sha256="):
        return False
    signature = signature_header.split("sha256=")[-1]
    computed = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)


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

    return {
        "status": "ok",
        "run_id": payload.workflow_run.id,
        "conclusion": payload.workflow_run.conclusion
    }