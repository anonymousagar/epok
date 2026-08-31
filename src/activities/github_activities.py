import os
from typing import Dict, Any, List
from github import Github, Auth
from temporalio import activity


@activity.defn
async def inspect_repo_context(repo_name: str, branch: str = "main") -> Dict[str, Any]:
    """
    Extract repository tree hierarchy, package manifests, and primary entrypoints.
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
        git_tree = repo.get_git_tree(branch, recursive=True)
    except Exception:
        # Fallback to default branch if target branch tree lookup fails
        git_tree = repo.get_git_tree(repo.default_branch, recursive=True)

    file_paths: List[str] = []
    manifests: Dict[str, str] = {}
    key_files = ["pyproject.toml", "package.json", "requirements.txt", "Dockerfile", "docker-compose.yml"]

    for item in git_tree.tree:
        if item.type == "blob":
            file_paths.append(item.path)
            # Ingest manifest content if matched
            if item.path in key_files or any(item.path.endswith(kf) for kf in key_files):
                try:
                    file_content = repo.get_contents(item.path, ref=branch)
                    if not isinstance(file_content, list) and file_content.decoded_content:
                        manifests[item.path] = file_content.decoded_content.decode("utf-8", errors="replace")
                except Exception:
                    pass

    return {
        "repo_name": repo_name,
        "default_branch": repo.default_branch,
        "file_paths": file_paths[:500],  # Bound tree depth to protect prompt token limits
        "manifests": manifests,
    }