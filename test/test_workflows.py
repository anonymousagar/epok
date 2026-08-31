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

        async def mock_gen_patches(spec, repo_context, existing_contents={}):
            return {"src/auth.py": "def auth(): pass\n"}

        async def mock_commit_patches(repo_name, branch_name, file_patches, commit_message=""):
            return "sha-12345"

        async def mock_create_pr(repo_name, head_branch, base_branch="main", title="", body="", commit_sha=""):
            return CodePatchResult(
                branch_name=head_branch,
                pr_url="https://github.com/org/epok/pull/99",
                pr_number=99,
                commit_sha=commit_sha
            )

        async with Worker(
            env.client,
            task_queue="test-spec-queue",
            workflows=[SpecArchitectureWorkflow, CodeGenerationWorkflow],
            activities=[
                mock_linear_activity,
                mock_github_activity,
                mock_gemini_activity,
                mock_slack_activity,
                mock_gen_patches,
                mock_commit_patches,
                mock_create_pr,
            ],
            activity_executors={
                fetch_linear_issue_details: mock_linear_activity,
                inspect_repo_context: mock_github_activity,
                generate_technical_spec: mock_gemini_activity,
                dispatch_slack_spec_approval: mock_slack_activity,
                generate_code_patches: mock_gen_patches,
                commit_code_patches: mock_commit_patches,
                create_github_pr: mock_create_pr,
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



from workflows.code_generation import CodeGenerationWorkflow
from activities.code_activities import generate_code_patches
from activities.github_activities import commit_code_patches, create_github_pr
from models.dtos import CodePatchResult


@pytest.mark.asyncio
async def test_code_generation_workflow_execution():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async def mock_gen_patches(spec, repo_context, existing_contents={}):
            return {"src/auth.py": "def auth(): pass\n"}

        async def mock_commit_patches(repo_name, branch_name, file_patches, commit_message=""):
            return "sha-12345"

        async def mock_create_pr(repo_name, head_branch, base_branch="main", title="", body="", commit_sha=""):
            return CodePatchResult(
                branch_name=head_branch,
                pr_url="https://github.com/org/epok/pull/99",
                pr_number=99,
                commit_sha=commit_sha
            )

        spec = SpecArchitectureOutput(
            summary="Build Auth",
            impacted_files=["src/auth.py"],
            implementation_steps=["1. Auth"],
            test_strategy="pytest"
        )

        async with Worker(
            env.client,
            task_queue="test-code-queue",
            workflows=[CodeGenerationWorkflow],
            activities=[
                mock_gen_patches,
                mock_commit_patches,
                mock_create_pr,
            ],
            activity_executors={
                generate_code_patches: mock_gen_patches,
                commit_code_patches: mock_commit_patches,
                create_github_pr: mock_create_pr,
            }
        ):
            result = await env.client.execute_workflow(
                CodeGenerationWorkflow.run,
                args=[spec, "lin-101", "org/epok", "main"],
                id="test-code-gen-workflow-id",
                task_queue="test-code-queue",
            )

            assert isinstance(result, CodePatchResult)
            assert result.branch_name == "epok/lin-101"
            assert result.pr_number == 99
            assert result.commit_sha == "sha-12345"