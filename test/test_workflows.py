import pytest
from unittest.mock import AsyncMock
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflows.spec_architecture import SpecArchitectureWorkflow
from activities.linear_activities import fetch_linear_issue_details
from activities.github_activities import inspect_repo_context
from activities.gemini_activities import generate_technical_spec
from activities.slack_activities import dispatch_slack_spec_approval
from models.dtos import SpecArchitectureOutput



@pytest.mark.asyncio
async def test_spec_architecture_workflow_execution():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        # Define mock activity implementations
        async def mock_linear_activity(issue_id: str):
            return {"id": issue_id, "title": "Add Auth", "description": "Need OAuth", "url": "https://linear.app/1"}

        async def mock_github_activity(repo_name: str, branch: str = "main"):
            return {"repo_name": repo_name, "default_branch": branch, "file_paths": ["src/main.py"], "manifests": {}}

        async def mock_gemini_activity(issue_context, repo_context):
            return SpecArchitectureOutput(
                summary="Build OAuth flow",
                impacted_files=["src/auth.py"],
                implementation_steps=["1. Add route"],
                test_strategy="Unit test tokens"
            )

        async def mock_slack_activity(spec, issue_url="", channel=""):
            return {"channel": "C12345", "ts": "100.1", "status": "posted"}

        async with Worker(
            env.client,
            task_queue="test-spec-queue",
            workflows=[SpecArchitectureWorkflow],
            activities=[
                mock_linear_activity,
                mock_github_activity,
                mock_gemini_activity,
                mock_slack_activity,
            ],
            activity_executors={
                fetch_linear_issue_details: mock_linear_activity,
                inspect_repo_context: mock_github_activity,
                generate_technical_spec: mock_gemini_activity,
                dispatch_slack_spec_approval: mock_slack_activity,
            }
        ):
            handle = await env.client.start_workflow(
                SpecArchitectureWorkflow.run,
                args=["lin-101", "org/epok", "main"],
                id="test-spec-workflow-id",
                task_queue="test-spec-queue",
            )

            # Signal approval to the running workflow
            await handle.signal(SpecArchitectureWorkflow.receive_approval_signal, "approved")

            result = await handle.result()

            assert isinstance(result, SpecArchitectureOutput)
            assert result.summary == "Build OAuth flow"
            assert result.impacted_files == ["src/auth.py"]