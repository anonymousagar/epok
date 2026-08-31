import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qs
from fastapi import APIRouter, Header, HTTPException, Request, status
from temporalio.client import Client
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


async def get_temporal_client() -> Client:
    temporal_host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    temporal_namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
    return await Client.connect(temporal_host, namespace=temporal_namespace)


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

    action_value = payload.actions[0].value if payload.actions else None
    workflow_id = None

    # Check if workflow_id is stored in action block_id or value (formatted as workflow_id:value)
    if payload.actions:
        first_action = payload.actions[0]
        if ":" in first_action.value:
            workflow_id, action_value = first_action.value.split(":", 1)
        elif first_action.block_id and first_action.block_id.startswith("epok-"):
            workflow_id = first_action.block_id

    if workflow_id:
        try:
            client = await get_temporal_client()
            handle = client.get_workflow_handle(workflow_id)
            await handle.signal("spec_approval_signal", action_value)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to signal Temporal workflow: {exc}"
            )

    return {
        "status": "ok",
        "action_value": action_value,
        "workflow_id": workflow_id
    }