import asyncio
from datetime import timedelta
from typing import Optional
from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activity definitions for type-safe invocation
with workflow.unsafe.imports_passed_through():
    from activities.linear_activities import fetch_linear_issue_details
    from activities.github_activities import inspect_repo_context
    from activities.gemini_activities import generate_technical_spec
    from activities.slack_activities import dispatch_slack_spec_approval
    from models.dtos import SpecArchitectureOutput


@workflow.defn
class SpecArchitectureWorkflow:
    def __init__(self) -> None:
        self.approval_decision: Optional[str] = None

    @workflow.signal(name="spec_approval_signal")
    def receive_approval_signal(self, decision: str) -> None:
        self.approval_decision = decision

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

        # 4. Dispatch Slack Block Kit spec approval notification
        issue_url = issue_context.get("url", "")
        await workflow.execute_activity(
            dispatch_slack_spec_approval,
            args=[spec_output, issue_url],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )

        # 5. Wait for human approval signal or 48-hour SLA timeout gate
        try:
            await workflow.wait_condition(
                lambda: self.approval_decision is not None,
                timeout=timedelta(hours=48),
            )
        except asyncio.TimeoutError:
            workflow.logger.warning("Spec architecture approval timed out after 48 hours SLA.")
            self.approval_decision = "timed_out"

        if self.approval_decision != "approved":
            workflow.logger.info(f"Spec workflow completed with decision status: {self.approval_decision}")

        return spec_output