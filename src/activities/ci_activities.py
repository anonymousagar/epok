import os
from typing import Dict, Any
from github import Github, Auth
from temporalio import activity


@activity.defn
async def fetch_ci_failure_logs(
    repo_name: str,
    run_id: int
) -> Dict[str, Any]:
    """
    Downloads and inspects GitHub Actions workflow run logs to extract error traces
    and failed job assertion details.
    """
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable is not set.")

    auth = Auth.Token(token)
    gh = Github(auth=auth)

    try:
        repo = gh.get_repo(repo_name)
    except Exception as exc:
        raise ValueError(f"Failed to access GitHub repository '{repo_name}': {exc}")

    try:
        run = repo.get_workflow_run(run_id)
    except Exception as exc:
        raise ValueError(f"Failed to fetch workflow run '{run_id}' for repo '{repo_name}': {exc}")

    error_trace_lines = []
    failed_steps = []

    try:
        jobs = run.jobs()
        for job in jobs:
            if job.conclusion == "failure":
                for step in job.steps:
                    if step.conclusion == "failure":
                        failed_steps.append(step.name)
                        error_trace_lines.append(f"Job '{job.name}' -> Step '{step.name}' failed.")
    except Exception:
        error_trace_lines.append(f"Workflow run {run_id} failed on branch {run.head_branch}.")

    error_trace = "\n".join(error_trace_lines) or f"CI workflow run {run_id} failed."

    return {
        "run_id": run_id,
        "head_branch": run.head_branch,
        "conclusion": run.conclusion,
        "error_trace": error_trace,
        "failed_steps": failed_steps,
    }
