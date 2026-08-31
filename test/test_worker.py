import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from worker.worker import run_worker
from workflows.spec_architecture import SpecArchitectureWorkflow
from workflows.code_generation import CodeGenerationWorkflow
from activities.linear_activities import fetch_linear_issue_details
from activities.github_activities import inspect_repo_context, commit_code_patches, create_github_pr

from activities.gemini_activities import generate_technical_spec
from activities.slack_activities import dispatch_slack_spec_approval
from activities.code_activities import generate_code_patches
from activities.ci_activities import fetch_ci_failure_logs


@pytest.mark.asyncio
async def test_run_worker_initialization(monkeypatch):
    monkeypatch.setenv("TEMPORAL_HOST", "localhost:7233")
    monkeypatch.setenv("TEMPORAL_NAMESPACE", "test-namespace")
    monkeypatch.setenv("EPOK_TASK_QUEUE", "test-task-queue")

    mock_client = MagicMock()
    mock_worker_instance = MagicMock()
    mock_worker_instance.run = AsyncMock()

    with patch("worker.worker.Client.connect", AsyncMock(return_value=mock_client)) as mock_connect, \
         patch("worker.worker.Worker", return_value=mock_worker_instance) as mock_worker_cls:

        # Run worker with timeout to prevent infinite loop
        await run_worker()

        mock_connect.assert_called_once_with("localhost:7233", namespace="test-namespace")
        mock_worker_cls.assert_called_once_with(
            mock_client,
            task_queue="test-task-queue",
            workflows=[SpecArchitectureWorkflow, CodeGenerationWorkflow],
            activities=[
                fetch_linear_issue_details,
                inspect_repo_context,
                commit_code_patches,
                create_github_pr,
                generate_technical_spec,
                dispatch_slack_spec_approval,
                generate_code_patches,
                fetch_ci_failure_logs,
            ],
        )
        mock_worker_instance.run.assert_called_once()

