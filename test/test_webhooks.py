import hashlib
import hmac
import json
import time
from urllib.parse import urlencode
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}



def test_linear_webhook_success(monkeypatch):
    secret = "test-linear-secret"
    monkeypatch.setenv("LINEAR_WEBHOOK_SECRET", secret)

    mock_client = MagicMock()
    mock_client.start_workflow = AsyncMock()

    async def mock_get_client():
        return mock_client

    monkeypatch.setattr("api.routes.linear.get_temporal_client", mock_get_client)

    payload = {
        "action": "update",
        "data": {
            "id": "lin-abc",
            "title": "Build authentication",
            "url": "https://linear.app/issue/lin-abc",
            "updatedAt": "2026-08-29T10:00:00Z"
        }
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    response = client.post(
        "/webhooks/linear",
        content=raw_body,
        headers={"Linear-Signature": sig, "Content-Type": "application/json"}
    )
    assert response.status_code == 202
    assert response.json()["workflow_id"] == "epok-linear-lin-abc-2026-08-29T10:00:00Z"
    mock_client.start_workflow.assert_called_once()



def test_linear_webhook_unauthorized():
    response = client.post(
        "/webhooks/linear",
        content=b"{}",
        headers={"Linear-Signature": "invalidsig", "Content-Type": "application/json"}
    )
    assert response.status_code == 401


def test_slack_webhook_success(monkeypatch):
    secret = "test-slack-secret"
    monkeypatch.setenv("SLACK_SIGNING_SECRET", secret)

    mock_handle = MagicMock()
    mock_handle.signal = AsyncMock()
    mock_client = MagicMock()
    mock_client.get_workflow_handle.return_value = mock_handle

    async def mock_get_client():
        return mock_client

    monkeypatch.setattr("api.routes.slack.get_temporal_client", mock_get_client)

    slack_data = {
        "type": "block_actions",
        "user": {"id": "U123", "username": "testuser"},
        "actions": [{"block_id": "epok-workflow-100", "action_id": "approve", "value": "epok-workflow-100:approved"}]
    }
    raw_payload = urlencode({"payload": json.dumps(slack_data)})
    ts = str(int(time.time()))
    basestring = f"v0:{ts}:{raw_payload}".encode("utf-8")
    sig = "v0=" + hmac.new(secret.encode("utf-8"), basestring, hashlib.sha256).hexdigest()

    response = client.post(
        "/webhooks/slack",
        content=raw_payload.encode("utf-8"),
        headers={
            "X-Slack-Signature": sig,
            "X-Slack-Request-Timestamp": ts,
            "Content-Type": "application/x-www-form-urlencoded"
        }
    )
    assert response.status_code == 200
    assert response.json()["action_value"] == "approved"
    assert response.json()["workflow_id"] == "epok-workflow-100"

    mock_client.get_workflow_handle.assert_called_once_with("epok-workflow-100")
    mock_handle.signal.assert_called_once_with("spec_approval_signal", "approved")



def test_github_webhook_success(monkeypatch):
    secret = "test-github-secret"
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", secret)

    payload = {
        "action": "completed",
        "workflow_run": {
            "id": 99999,
            "name": "build",
            "head_branch": "epok/lin-abc",
            "conclusion": "success",
            "html_url": "https://github.com/runs/99999"
        }
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    response = client.post(
        "/webhooks/github",
        content=raw_body,
        headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"}
    )
    assert response.status_code == 200
    assert response.json()["run_id"] == 99999