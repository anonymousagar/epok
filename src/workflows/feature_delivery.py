import asyncio
from datetime import timedelta
from typing import Optional, Dict, Any
from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activity definitions for type-safe invocation
with workflow.unsafe.imports_passed_through():
    from activities.linear_activities import fetch_linear_issue_details
    from activities.github_activities import inspect_repo_context, commit_code_patches, create_github_pr
    from activities.gemini_activities import generate_technical_spec
    from activities.slack_activities import dispatch_slack_spec_approval
    from activities.code_activities import generate_code_patches
    from models.dtos import SpecArchitectureOutput, CodePatchResult


@workflow.defn
class FeatureDeliveryLifecycleWorkflow:
    def __init__(self) -> None:
        self.approval_decision: Optional[str] = None

    @workflow.signal(name="spec_approval_signal")
    def receive_approval_signal(self, decision: str) -> None:
        self.approval_decision = decision

    @workflow.run
    async def run(self, issue_id: str, repo_name: str, branch: str = "main") -> CodePatchResult:
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3,
        )

        # Phase 1: Ingest Linear issue details & GitHub repository hierarchy
        issue_context: Dict[str, Any] = await workflow.execute_activity(
            fetch_linear_issue_details,
            issue_id,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )

        repo_context: Dict[str, Any] = await workflow.execute_activity(
            inspect_repo_context,
            args=[repo_name, branch],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=retry_policy,
        )

        # Phase 2: Generate Gemini technical architecture plan
        spec_output: SpecArchitectureOutput = await workflow.execute_activity(
            generate_technical_spec,
            args=[issue_context, repo_context],
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=retry_policy,
        )

        # Phase 3: Dispatch Slack Block Kit spec approval UI
        issue_url = issue_context.get("url", "")
        await workflow.execute_activity(
            dispatch_slack_spec_approval,
            args=[spec_output, issue_url],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )

        # Wait for human approval signal or 48-hour SLA gate
        try:
            await workflow.wait_condition(
                lambda: self.approval_decision is not None,
                timeout=timedelta(hours=48),
            )
        except asyncio.TimeoutError:
            workflow.logger.warning("Feature delivery spec approval timed out after 48 hours SLA.")
            self.approval_decision = "timed_out"

        if self.approval_decision != "approved":
            workflow.logger.info(f"Feature delivery workflow halted with status: {self.approval_decision}")
            return CodePatchResult(
                branch_name=f"epok/{issue_id.lower()}",
                pr_url="",
                pr_number=0,
                commit_sha=""
            )

        # Phase 4: Code Patch Generation, Branch Commit & GitHub PR Submission
        file_patches: Dict[str, str] = await workflow.execute_activity(
            generate_code_patches,
            args=[spec_output, repo_context, {}],
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=retry_policy,
        )

        clean_issue_id = issue_id.lower().replace(" ", "-")
        head_branch = f"epok/{clean_issue_id}"
        commit_msg = f"feat(epok): automated feature delivery for issue {issue_id}"

        commit_sha: str = await workflow.execute_activity(
            commit_code_patches,
            args=[repo_name, head_branch, file_patches, commit_msg],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=retry_policy,
        )

        pr_title = f"feat(epok): {spec_output.summary[:60]}"
        pr_body = f"""## 🤖 Epok Automated Feature Delivery

### Issue Reference
* **Linear Issue ID**: `{issue_id}`

### Architecture Summary
{spec_output.summary}

### Implementation Steps Completed
{chr(10).join(f"- {step}" for step in spec_output.implementation_steps)}

### Testing Strategy
{spec_output.test_strategy}
"""

        code_patch_result: CodePatchResult = await workflow.execute_activity(
            create_github_pr,
            args=[repo_name, head_branch, branch, pr_title, pr_body, commit_sha],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )

        return code_patch_result

