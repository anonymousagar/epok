from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activity definitions for type-safe invocation
with workflow.unsafe.imports_passed_through():
    from activities.linear_activities import fetch_linear_issue_details
    from activities.github_activities import inspect_repo_context
    from activities.gemini_activities import generate_technical_spec
    from models.dtos import SpecArchitectureOutput


@workflow.defn
class SpecArchitectureWorkflow:
    @workflow.run
    async def run(self, issue_id: str, repo_name: str, branch: str = "main") -> SpecArchitectureOutput:
        # Default exponential backoff policy per PRD Section 5.1
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3,
        )

        # 1. Fetch Linear issue context
        issue_context = await workflow.execute_activity(
            fetch_linear_issue_details,
            issue_id,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )

        # 2. Extract GitHub repository structure and manifest context
        repo_context = await workflow.execute_activity(
            inspect_repo_context,
            args=[repo_name, branch],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=retry_policy,
        )

        # 3. Generate Gemini architecture plan
        spec_output: SpecArchitectureOutput = await workflow.execute_activity(
            generate_technical_spec,
            args=[issue_context, repo_context],
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=retry_policy,
        )

        return spec_output