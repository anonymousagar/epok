from datetime import timedelta
from typing import Dict, Any
from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activity definitions for type-safe invocation
with workflow.unsafe.imports_passed_through():
    from activities.code_activities import generate_code_patches
    from activities.github_activities import commit_code_patches, create_github_pr
    from models.dtos import SpecArchitectureOutput, CodePatchResult


@workflow.defn
class CodeGenerationWorkflow:
    @workflow.run
    async def run(
        self,
        spec: SpecArchitectureOutput,
        issue_id: str,
        repo_name: str,
        base_branch: str = "main",
        existing_file_contents: Dict[str, str] = {}
    ) -> CodePatchResult:
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3,
        )

        repo_context = {
            "repo_name": repo_name,
            "default_branch": base_branch,
        }

        # 1. Generate code patches using Gemini
        file_patches: Dict[str, str] = await workflow.execute_activity(
            generate_code_patches,
            args=[spec, repo_context, existing_file_contents],
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=retry_policy,
        )

        # 2. Formulate feature branch & commit message
        clean_issue_id = issue_id.lower().replace(" ", "-")
        head_branch = f"epok/{clean_issue_id}"
        commit_msg = f"feat(epok): automated code patch for issue {issue_id}"

        # 3. Commit code patches to GitHub feature branch
        commit_sha: str = await workflow.execute_activity(
            commit_code_patches,
            args=[repo_name, head_branch, file_patches, commit_msg],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=retry_policy,
        )

        # 4. Formulate PR title and markdown description
        pr_title = f"feat(epok): {spec.summary[:60]}"
        pr_body = f"""## 🤖 Epok Automated Code Delivery

### Issue Reference
* **Linear Issue ID**: `{issue_id}`

### Architecture Summary
{spec.summary}

### Implementation Steps Completed
{chr(10).join(f"- {step}" for step in spec.implementation_steps)}

### Testing Strategy
{spec.test_strategy}
"""

        # 5. Create Pull Request on GitHub
        code_patch_result: CodePatchResult = await workflow.execute_activity(
            create_github_pr,
            args=[repo_name, head_branch, base_branch, pr_title, pr_body, commit_sha],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )

        return code_patch_result
