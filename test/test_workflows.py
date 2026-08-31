import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflows.spec_architecture import SpecArchitectureWorkflow
from workflows.code_generation import CodeGenerationWorkflow
from workflows.ci_repair import CIRepairWorkflow
from workflows.feature_delivery import FeatureDeliveryLifecycleWorkflow
from models.dtos import SpecArchitectureOutput, CodePatchResult, CIExecutionResult


@pytest.mark.asyncio
async def test_spec_architecture_workflow_execution():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        @activity.defn(name="fetch_linear_issue_details")
        async def mock_linear_activity(issue_id: str):
            return {"id": issue_id, "title": "Add Auth", "description": "Need OAuth", "url": "https://linear.app/1"}

        @activity.defn(name="inspect_repo_context")
        async def mock_github_activity(repo_name: str, branch: str = "main"):
            return {"repo_name": repo_name, "default_branch": branch, "file_paths": ["src/main.py"], "manifests": {}}

        @activity.defn(name="generate_technical_spec")
        async def mock_gemini_activity(issue_context, repo_context):
            return SpecArchitectureOutput(
                summary="Build OAuth flow",
                impacted_files=["src/auth.py"],
                implementation_steps=["1. Add route"],
                test_strategy="Unit test tokens"
            )

        @activity.defn(name="dispatch_slack_spec_approval")
        async def mock_slack_activity(spec, issue_url="", channel=""):
            return {"channel": "C12345", "ts": "100.1", "status": "posted"}

        @activity.defn(name="generate_code_patches")
        async def mock_gen_patches(spec, repo_context, existing_contents={}):
            return {"src/auth.py": "def auth(): pass\n"}

        @activity.defn(name="commit_code_patches")
        async def mock_commit_patches(repo_name, branch_name, file_patches, commit_message=""):
            return "sha-12345"

        @activity.defn(name="create_github_pr")
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
        ):
            handle = await env.client.start_workflow(
                SpecArchitectureWorkflow.run,
                args=["lin-101", "org/epok", "main"],
                id="test-spec-workflow-id",
                task_queue="test-spec-queue",
            )

            await handle.signal(SpecArchitectureWorkflow.receive_approval_signal, "approved")
            result = await handle.result()

            assert isinstance(result, SpecArchitectureOutput)
            assert result.summary == "Build OAuth flow"
            assert result.impacted_files == ["src/auth.py"]


@pytest.mark.asyncio
async def test_code_generation_workflow_execution():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        @activity.defn(name="generate_code_patches")
        async def mock_gen_patches(spec, repo_context, existing_contents={}):
            return {"src/auth.py": "def auth(): pass\n"}

        @activity.defn(name="commit_code_patches")
        async def mock_commit_patches(repo_name, branch_name, file_patches, commit_message=""):
            return "sha-12345"

        @activity.defn(name="create_github_pr")
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


@pytest.mark.asyncio
async def test_ci_repair_workflow_execution():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        @activity.defn(name="fetch_ci_failure_logs")
        async def mock_fetch_logs(repo_name, run_id):
            return {"run_id": run_id, "error_trace": "AssertionError", "failed_steps": ["test"]}

        @activity.defn(name="inspect_repo_context")
        async def mock_inspect_repo(repo_name, branch="main"):
            return {"repo_name": repo_name, "default_branch": branch, "manifests": {}}

        @activity.defn(name="generate_ci_repair_patches")
        async def mock_gen_repair(repo_name, head_branch, error_trace, current_files={}):
            return {"src/main.py": "fixed"}

        @activity.defn(name="commit_code_patches")
        async def mock_commit_patches(repo_name, branch_name, file_patches, commit_message=""):
            return "sha-fixed"

        async with Worker(
            env.client,
            task_queue="test-ci-repair-queue",
            workflows=[CIRepairWorkflow],
            activities=[
                mock_fetch_logs,
                mock_inspect_repo,
                mock_gen_repair,
                mock_commit_patches,
            ],
        ):
            result = await env.client.execute_workflow(
                CIRepairWorkflow.run,
                args=[88888, "epok/test-branch", "org/epok", 1],
                id="test-ci-repair-workflow-id",
                task_queue="test-ci-repair-queue",
            )

            assert isinstance(result, CIExecutionResult)
            assert result.iteration == 1
            assert "AssertionError" in result.logs


@pytest.mark.asyncio
async def test_feature_delivery_lifecycle_workflow_execution():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        @activity.defn(name="fetch_linear_issue_details")
        async def mock_linear_act(issue_id: str):
            return {"id": issue_id, "title": "Add Auth", "url": "https://linear.app/1"}

        @activity.defn(name="inspect_repo_context")
        async def mock_github_act(repo_name: str, branch: str = "main"):
            return {"repo_name": repo_name, "default_branch": branch, "manifests": {}}

        @activity.defn(name="generate_technical_spec")
        async def mock_gemini_spec_act(issue_context, repo_context):
            return SpecArchitectureOutput(
                summary="Build Auth",
                impacted_files=["src/auth.py"],
                implementation_steps=["1. Add route"],
                test_strategy="pytest"
            )

        @activity.defn(name="dispatch_slack_spec_approval")
        async def mock_slack_act(spec, issue_url="", channel=""):
            return {"channel": "C123", "ts": "1.1", "status": "posted"}

        @activity.defn(name="generate_code_patches")
        async def mock_gen_code_act(spec, repo_context, existing_contents={}):
            return {"src/auth.py": "def auth(): pass\n"}

        @activity.defn(name="commit_code_patches")
        async def mock_commit_code_act(repo_name, branch_name, file_patches, commit_message=""):
            return "sha-555"

        @activity.defn(name="create_github_pr")
        async def mock_create_pr_act(repo_name, head_branch, base_branch="main", title="", body="", commit_sha=""):
            return CodePatchResult(
                branch_name=head_branch,
                pr_url="https://github.com/org/epok/pull/101",
                pr_number=101,
                commit_sha=commit_sha
            )

        async with Worker(
            env.client,
            task_queue="test-feature-delivery-queue",
            workflows=[FeatureDeliveryLifecycleWorkflow],
            activities=[
                mock_linear_act,
                mock_github_act,
                mock_gemini_spec_act,
                mock_slack_act,
                mock_gen_code_act,
                mock_commit_code_act,
                mock_create_pr_act,
            ],
        ):
            handle = await env.client.start_workflow(
                FeatureDeliveryLifecycleWorkflow.run,
                args=["lin-101", "org/epok", "main"],
                id="test-feature-delivery-workflow-id",
                task_queue="test-feature-delivery-queue",
            )

            await handle.signal(FeatureDeliveryLifecycleWorkflow.receive_approval_signal, "approved")
            result = await handle.result()

            assert isinstance(result, CodePatchResult)
            assert result.branch_name == "epok/lin-101"
            assert result.pr_number == 101
            assert result.commit_sha == "sha-555"