import pytest
from pydantic import ValidationError
from models.events import (
    LinearWebhookPayload,
    SlackBlockActionsPayload,
    GitHubWorkflowRunPayload,
)
from models.dtos import (
    SpecArchitectureOutput,
    CodePatchResult,
    CIExecutionResult,
)


def test_linear_webhook_payload():
    valid = {
        "action": "update",
        "data": {
            "id": "lin-123",
            "title": "Fix auth error",
            "description": "Details here",
            "url": "https://linear.app/issue/lin-123",
            "updatedAt": "2026-08-28T19:00:00Z",
        },
    }
    model = LinearWebhookPayload(**valid)
    assert model.data.id == "lin-123"

    with pytest.raises(ValidationError):
        LinearWebhookPayload(action="update", data={"id": "lin-123"})


def test_slack_block_actions_payload():
    valid = {
        "type": "block_actions",
        "user": {"id": "U123", "username": "dev"},
        "actions": [{"block_id": "epok_gate", "action_id": "approve", "value": "approve"}],
        "response_url": "https://hooks.slack.com/actions/123",
    }
    model = SlackBlockActionsPayload(**valid)
    assert model.actions[0].value == "approve"


def test_github_workflow_run_payload():
    valid = {
        "action": "completed",
        "workflow_run": {
            "id": 123456,
            "name": "CI",
            "head_branch": "epok/fix-auth",
            "conclusion": "success",
            "html_url": "https://github.com/org/repo/actions/runs/123456",
        },
    }
    model = GitHubWorkflowRunPayload(**valid)
    assert model.workflow_run.id == 123456
    assert model.workflow_run.conclusion == "success"


def test_spec_architecture_output():
    valid = {
        "summary": "Implementation summary",
        "impacted_files": ["api/main.py"],
        "implementation_steps": ["step 1"],
        "test_strategy": "pytest",
    }
    model = SpecArchitectureOutput(**valid)
    assert len(model.impacted_files) == 1


def test_code_patch_result():
    valid = {
        "branch_name": "epok/fix-auth",
        "pr_url": "https://github.com/org/repo/pull/1",
        "pr_number": 1,
        "commit_sha": "abc1234",
    }
    model = CodePatchResult(**valid)
    assert model.pr_number == 1


def test_ci_execution_result():
    valid = {
        "success": True,
        "iteration": 1,
        "logs": "All tests passed",
    }
    model = CIExecutionResult(**valid)
    assert model.success is True