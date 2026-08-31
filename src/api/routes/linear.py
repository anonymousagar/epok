import hashlib
import hmac
import os
from fastapi import APIRouter, Header, HTTPException, Request, status
from models.events import LinearWebhookPayload

router = APIRouter(prefix="/webhooks/linear", tags=["Linear Webhook"])


def verify_linear_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    computed = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)


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
    return {
        "status": "accepted",
        "workflow_id": workflow_id,
        "issue_id": payload.data.id
    }