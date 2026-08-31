import os
from typing import Dict, Any
import httpx
from temporalio import activity
from models.dtos import SpecArchitectureOutput

SLACK_API_POST_MESSAGE = "https://slack.com/api/chat.postMessage"


@activity.defn
async def dispatch_slack_spec_approval(
    spec: SpecArchitectureOutput,
    issue_url: str = "",
    channel: str = ""
) -> Dict[str, Any]:
    """
    Formats and dispatches an interactive Block Kit architecture spec message to Slack
    with Approve and Request Revision action buttons.
    """
    bot_token = os.getenv("SLACK_BOT_TOKEN", "")
    if not bot_token:
        raise ValueError("SLACK_BOT_TOKEN environment variable is not set.")

    target_channel = channel or os.getenv("SLACK_DEFAULT_CHANNEL", "#epok-approvals")

    impacted_files_str = "\n".join(f"• `{f}`" for f in spec.impacted_files) if spec.impacted_files else "• None"
    steps_str = "\n".join(spec.implementation_steps) if spec.implementation_steps else "• None"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🏗️ Epok Architecture Spec Approval Required",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Executive Summary:*\n{spec.summary}",
            },
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Impacted Files:*\n{impacted_files_str}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Linear Issue:*\n<{issue_url}|View Issue Ticket>" if issue_url else "*Linear Issue:*\nN/A",
                },
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Implementation Steps:*\n{steps_str}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Testing Strategy:*\n{spec.test_strategy}",
            },
        },
        {"type": "divider"},
        {
            "type": "actions",
            "block_id": "epok_spec_approval_actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve Spec", "emoji": True},
                    "style": "primary",
                    "value": "approved",
                    "action_id": "approve_spec",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Request Revision", "emoji": True},
                    "style": "danger",
                    "value": "rejected",
                    "action_id": "reject_spec",
                },
            ],
        },
    ]

    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json; charset=utf-8",
    }

    payload = {
        "channel": target_channel,
        "text": f"New Epok Architecture Spec for approval: {spec.summary}",
        "blocks": blocks,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(SLACK_API_POST_MESSAGE, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    if not data.get("ok"):
        raise ValueError(f"Slack API error posting spec approval message: {data.get('error')}")

    return {
        "channel": data.get("channel", target_channel),
        "ts": data.get("ts", ""),
        "status": "posted",
    }
