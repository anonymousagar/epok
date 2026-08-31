import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qs
from fastapi import APIRouter, Header, HTTPException, Request, status
from models.events import SlackBlockActionsPayload

router = APIRouter(prefix="/webhooks/slack", tags=["Slack Webhook"])


def verify_slack_signature(raw_body: bytes, timestamp: str, signature: str, secret: str) -> bool:
    current_ts = int(time.time())
    if abs(current_ts - int(timestamp)) > 60 * 5:
        return False

    sig_basestring = f"v0:{timestamp}:{raw_body.decode('utf-8')}"
    computed = "v0=" + hmac.new(
        secret.encode("utf-8"),
        sig_basestring.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


@router.post("", status_code=status.HTTP_200_OK)
async def receive_slack_webhook(
    request: Request,
    x_slack_signature: str = Header(None, alias="X-Slack-Signature"),
    x_slack_request_timestamp: str = Header(None, alias="X-Slack-Request-Timestamp")
):
    raw_body = await request.body()
    signing_secret = os.getenv("SLACK_SIGNING_SECRET", "")

    if (
        not x_slack_signature
        or not x_slack_request_timestamp
        or not verify_slack_signature(raw_body, x_slack_request_timestamp, x_slack_signature, signing_secret)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Slack signature or expired timestamp."
        )

    try:
        form_data = parse_qs(raw_body.decode("utf-8"))
        payload_raw = json.loads(form_data.get("payload", ["{}"])[0])
        payload = SlackBlockActionsPayload(**payload_raw)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Malformed Slack interaction payload: {exc}"
        )

    return {"status": "ok", "action_value": payload.actions[0].value if payload.actions else None}