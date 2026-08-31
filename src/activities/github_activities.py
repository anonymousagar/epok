import os
from typing import Dict, Any, List
from github import Github, Auth
from temporalio import activity
from models.dtos import CodePatchResult



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


@activity.defn
async def commit_code_patches(
    repo_name: str,
    branch_name: str,
    file_patches: Dict[str, str],
    commit_message: str = ""
) -> str:
    """
    Creates a target feature branch (if it doesn't exist) and commits generated file patches.
    Returns the latest commit SHA on the branch.
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

    # Ensure feature branch exists, creating it from default branch if needed
    try:
        branch_ref = repo.get_git_ref(f"heads/{branch_name}")
        commit_sha = branch_ref.object.sha
    except Exception:
        default_branch = repo.get_branch(repo.default_branch)
        base_sha = default_branch.commit.sha
        ref = repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base_sha)
        commit_sha = ref.object.sha

    msg = commit_message or f"feat: epok automated code patch for branch {branch_name}"

    for file_path, content in file_patches.items():
        try:
            existing_file = repo.get_contents(file_path, ref=branch_name)
            if not isinstance(existing_file, list):
                res = repo.update_file(
                    path=file_path,
                    message=msg,
                    content=content,
                    sha=existing_file.sha,
                    branch=branch_name,
                )
                commit_obj = res.get("commit") if isinstance(res, dict) else getattr(res, "commit", None)
                commit_sha = getattr(commit_obj, "sha", "") or (commit_obj.get("sha") if isinstance(commit_obj, dict) else "")
        except Exception:
            # File does not exist yet on branch -> create file
            res = repo.create_file(
                path=file_path,
                message=msg,
                content=content,
                branch=branch_name,
            )
            commit_obj = res.get("commit") if isinstance(res, dict) else getattr(res, "commit", None)
            commit_sha = getattr(commit_obj, "sha", "") or (commit_obj.get("sha") if isinstance(commit_obj, dict) else "")

    return commit_sha


@activity.defn
async def create_github_pr(
    repo_name: str,
    head_branch: str,
    base_branch: str = "main",
    title: str = "",
    body: str = "",
    commit_sha: str = ""
) -> CodePatchResult:
    """
    Creates a Pull Request on GitHub targeting base_branch and returns a CodePatchResult.
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

    pr_title = title or f"feat: automated code patch for branch {head_branch}"
    pr_body = body or f"Epok Automated Code Generation Pull Request for `{head_branch}`."

    try:
        pr = repo.create_pull(
            title=pr_title,
            body=pr_body,
            head=head_branch,
            base=base_branch,
        )
    except Exception as exc:
        raise ValueError(f"Failed to create GitHub Pull Request for '{head_branch}': {exc}")

    return CodePatchResult(
        branch_name=head_branch,
        pr_url=pr.html_url,
        pr_number=pr.number,
        commit_sha=commit_sha or getattr(pr.head, "sha", ""),
    )