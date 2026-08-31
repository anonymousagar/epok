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


from google import genai

from google.genai import types
from models.dtos import CodePatchesOutput

CI_REPAIR_SYSTEM_INSTRUCTION = """You are an expert Automated Debugging & Self-Healing AI Engineer at Epok.
Your task is to analyze build/test failure stack traces and current codebase file contents, identify the root cause of the error, and generate fixed, production-grade replacement code for all failing files."""


@activity.defn
async def generate_ci_repair_patches(
    repo_name: str,
    head_branch: str,
    error_trace: str,
    current_files: Dict[str, str] = {}
) -> Dict[str, str]:
    """
    Invokes Gemini 2.5 Flash to analyze CI failure logs and generate repaired code patches.
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set.")

    client = genai.Client(api_key=api_key)

    files_summary = ""
    for path, content in current_files.items():
        files_summary += f"\n--- File: {path} ---\n{content}\n"

    prompt = f"""
### Target Repository:
- Repository: {repo_name}
- Branch: {head_branch}

### CI Build / Test Failure Trace:
{error_trace}

### Current Source Code Files:
{files_summary or "No file contents provided."}

Please analyze the failure trace and generate complete, repaired code for any files that require fixes to pass CI.
"""

    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=CI_REPAIR_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=CodePatchesOutput,
            temperature=0.2,
        ),
    )

    if not response.text:
        raise ValueError("Gemini returned empty text response for CI repair patch generation.")

    patches_output = CodePatchesOutput.model_validate_json(response.text)
    return {patch.path: patch.content for patch in patches_output.patches}


