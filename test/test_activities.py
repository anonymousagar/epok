import json
import pytest
import httpx
from unittest.mock import MagicMock, AsyncMock

from activities.linear_activities import fetch_linear_issue_details
from activities.github_activities import inspect_repo_context
from activities.gemini_activities import generate_technical_spec
from models.dtos import SpecArchitectureOutput


# --- Issue 2.1 Tests: Linear Activity ---

@pytest.mark.asyncio
async def test_fetch_linear_issue_details_success(monkeypatch):
    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test_key")

    mock_response_data = {
        "data": {
            "issue": {
                "id": "lin-100",
                "title": "Add Auth Support",
                "description": "Implement OAuth2 login flow",
                "url": "https://linear.app/epok/issue/lin-100",
                "state": {"name": "Todo"},
                "assignee": {"name": "Developer"}
            }
        }
    }

    async def mock_post(self, url, *args, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(200, json=mock_response_data, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    result = await fetch_linear_issue_details("lin-100")
    assert result["id"] == "lin-100"
    assert result["title"] == "Add Auth Support"
    assert result["state"] == "Todo"
    assert result["assignee"] == "Developer"


@pytest.mark.asyncio
async def test_fetch_linear_issue_details_missing_api_key(monkeypatch):
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)
    with pytest.raises(ValueError, match="LINEAR_API_KEY environment variable is not set."):
        await fetch_linear_issue_details("lin-100")


# --- Issue 2.2 Tests: GitHub Context Extractor ---

@pytest.mark.asyncio
async def test_inspect_repo_context_success(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-gh-token")

    mock_blob_item = MagicMock()
    mock_blob_item.type = "blob"
    mock_blob_item.path = "pyproject.toml"

    mock_tree = MagicMock()
    mock_tree.tree = [mock_blob_item]

    mock_content = MagicMock()
    mock_content.decoded_content = b'[project]\nname = "epok"\n'

    mock_repo = MagicMock()
    mock_repo.default_branch = "main"
    mock_repo.get_git_tree.return_value = mock_tree
    mock_repo.get_contents.return_value = mock_content

    mock_gh = MagicMock()
    mock_gh.get_repo.return_value = mock_repo

    monkeypatch.setattr("activities.github_activities.Github", lambda auth: mock_gh)

    result = await inspect_repo_context("org/epok", branch="main")
    assert result["repo_name"] == "org/epok"
    assert result["default_branch"] == "main"
    assert "pyproject.toml" in result["file_paths"]
    assert 'name = "epok"' in result["manifests"]["pyproject.toml"]


@pytest.mark.asyncio
async def test_inspect_repo_context_missing_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(ValueError, match="GITHUB_TOKEN environment variable is not set."):
        await inspect_repo_context("org/epok")


# --- Issue 2.3 Tests: Gemini Technical Spec Generator ---

@pytest.mark.asyncio
async def test_generate_technical_spec_success(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")

    mock_spec_dict = {
        "summary": "Implement JWT authentication filter",
        "impacted_files": ["src/api/auth.py", "test/test_auth.py"],
        "implementation_steps": ["1. Add JWT dependency", "2. Create auth router"],
        "test_strategy": "Unit test token verification and expiration."
    }

    mock_response = MagicMock()
    mock_response.text = json.dumps(mock_spec_dict)

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    monkeypatch.setattr("activities.gemini_activities.genai.Client", lambda api_key: mock_client)

    issue_context = {"title": "Add Auth", "description": "Need JWT", "url": "https://linear.app/1"}
    repo_context = {"repo_name": "org/epok", "default_branch": "main", "file_paths": ["src/api/main.py"], "manifests": {}}

    result = await generate_technical_spec(issue_context, repo_context)
    assert isinstance(result, SpecArchitectureOutput)
    assert result.summary == "Implement JWT authentication filter"
    assert "src/api/auth.py" in result.impacted_files
    assert len(result.implementation_steps) == 2


@pytest.mark.asyncio
async def test_generate_technical_spec_missing_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable is not set."):
        await generate_technical_spec({}, {})


# --- Issue EPO-12 Tests: Slack Spec Dispatch Activity ---

from activities.slack_activities import dispatch_slack_spec_approval


@pytest.mark.asyncio
async def test_dispatch_slack_spec_approval_success(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-fake-slack-token")

    mock_response_data = {"ok": True, "channel": "C123456", "ts": "1725100000.000100"}

    captured_kwargs = {}

    async def mock_post(self, url, *args, **kwargs):
        captured_kwargs.update(kwargs)
        request = httpx.Request("POST", url)
        return httpx.Response(200, json=mock_response_data, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    spec = SpecArchitectureOutput(
        summary="Build OAuth flow",
        impacted_files=["src/auth.py"],
        implementation_steps=["1. Add route"],
        test_strategy="Unit test tokens"
    )

    result = await dispatch_slack_spec_approval(spec, issue_url="https://linear.app/issue/lin-1", channel="#test-channel")
    assert result["status"] == "posted"
    assert result["channel"] == "C123456"
    assert result["ts"] == "1725100000.000100"

    payload = captured_kwargs.get("json", {})
    assert payload["channel"] == "#test-channel"
    assert len(payload["blocks"]) == 7



@pytest.mark.asyncio
async def test_dispatch_slack_spec_approval_missing_token(monkeypatch):
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    spec = SpecArchitectureOutput(
        summary="Build OAuth flow",
        impacted_files=["src/auth.py"],
        implementation_steps=["1. Add route"],
        test_strategy="Unit test tokens"
    )
    with pytest.raises(ValueError, match="SLACK_BOT_TOKEN environment variable is not set."):
        await dispatch_slack_spec_approval(spec)


# --- Ticket 4.1 Tests: Gemini Code Patch Generator Activity ---

from activities.code_activities import generate_code_patches
from models.dtos import CodePatchesOutput, FilePatch


@pytest.mark.asyncio
async def test_generate_code_patches_success(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")

    mock_patches_output = CodePatchesOutput(
        patches=[
            FilePatch(path="src/auth.py", content="def login(): return True\n")
        ]
    )

    mock_response = MagicMock()
    mock_response.text = mock_patches_output.model_dump_json()

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    monkeypatch.setattr("activities.code_activities.genai.Client", lambda api_key: mock_client)

    spec = SpecArchitectureOutput(
        summary="Build OAuth flow",
        impacted_files=["src/auth.py"],
        implementation_steps=["1. Add login function"],
        test_strategy="Unit test login"
    )
    repo_context = {"repo_name": "org/epok", "default_branch": "main"}
    existing_contents = {"src/auth.py": "# Old auth code\n"}

    result = await generate_code_patches(spec, repo_context, existing_contents)
    assert "src/auth.py" in result
    assert result["src/auth.py"] == "def login(): return True\n"
    mock_client.aio.models.generate_content.assert_called_once()


@pytest.mark.asyncio
async def test_generate_code_patches_missing_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    spec = SpecArchitectureOutput(
        summary="Build OAuth flow",
        impacted_files=["src/auth.py"],
        implementation_steps=["1. Add login function"],
        test_strategy="Unit test login"
    )
    with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable is not set."):
        await generate_code_patches(spec, {})


# --- Ticket 4.2 Tests: GitHub Branch & Commit Activity ---

from activities.github_activities import commit_code_patches


@pytest.mark.asyncio
async def test_commit_code_patches_success(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-gh-token")

    mock_commit = MagicMock()
    mock_commit.sha = "sha999"
    mock_repo = MagicMock()

    # Existing file on branch
    mock_file = MagicMock()
    mock_file.sha = "sha123"
    mock_repo.get_contents.return_value = mock_file
    mock_repo.update_file.return_value = {"commit": mock_commit}

    # Branch ref existing
    mock_ref = MagicMock()
    mock_ref.object.sha = "sha888"
    mock_repo.get_git_ref.return_value = mock_ref

    mock_gh = MagicMock()
    mock_gh.get_repo.return_value = mock_repo

    monkeypatch.setattr("activities.github_activities.Github", lambda auth: mock_gh)

    result = await commit_code_patches("org/epok", "epok/test-branch", {"src/main.py": "print('hello')"})
    assert result == "sha999"
    mock_repo.update_file.assert_called_once()



@pytest.mark.asyncio
async def test_commit_code_patches_missing_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(ValueError, match="GITHUB_TOKEN environment variable is not set."):
        await commit_code_patches("org/epok", "epok/test-branch", {})


# --- Ticket 4.3 Tests: GitHub PR Creation Activity ---

from activities.github_activities import create_github_pr
from models.dtos import CodePatchResult


@pytest.mark.asyncio
async def test_create_github_pr_success(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-gh-token")

    mock_pr = MagicMock()
    mock_pr.html_url = "https://github.com/org/epok/pull/42"
    mock_pr.number = 42

    mock_repo = MagicMock()
    mock_repo.create_pull.return_value = mock_pr

    mock_gh = MagicMock()
    mock_gh.get_repo.return_value = mock_repo

    monkeypatch.setattr("activities.github_activities.Github", lambda auth: mock_gh)

    result = await create_github_pr(
        repo_name="org/epok",
        head_branch="epok/test-branch",
        base_branch="main",
        title="feat: add feature",
        body="Automated PR",
        commit_sha="sha999"
    )

    assert isinstance(result, CodePatchResult)
    assert result.branch_name == "epok/test-branch"
    assert result.pr_url == "https://github.com/org/epok/pull/42"
    assert result.pr_number == 42
    assert result.commit_sha == "sha999"
    mock_repo.create_pull.assert_called_once_with(
        title="feat: add feature",
        body="Automated PR",
        head="epok/test-branch",
        base="main"
    )


@pytest.mark.asyncio
async def test_create_github_pr_missing_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(ValueError, match="GITHUB_TOKEN environment variable is not set."):
        await create_github_pr("org/epok", "epok/test-branch")


# --- Ticket 5.1 Tests: CI Log Extractor Activity ---

from activities.ci_activities import fetch_ci_failure_logs


@pytest.mark.asyncio
async def test_fetch_ci_failure_logs_success(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-gh-token")

    mock_step = MagicMock()
    mock_step.name = "pytest"
    mock_step.conclusion = "failure"

    mock_job = MagicMock()
    mock_job.name = "build-and-test"
    mock_job.conclusion = "failure"
    mock_job.steps = [mock_step]

    mock_run = MagicMock()
    mock_run.head_branch = "epok/test-branch"
    mock_run.conclusion = "failure"
    mock_run.jobs.return_value = [mock_job]

    mock_repo = MagicMock()
    mock_repo.get_workflow_run.return_value = mock_run

    mock_gh = MagicMock()
    mock_gh.get_repo.return_value = mock_repo

    monkeypatch.setattr("activities.ci_activities.Github", lambda auth: mock_gh)

    result = await fetch_ci_failure_logs("org/epok", 88888)
    assert result["run_id"] == 88888
    assert result["head_branch"] == "epok/test-branch"
    assert result["conclusion"] == "failure"
    assert "Job 'build-and-test' -> Step 'pytest' failed." in result["error_trace"]
    assert "pytest" in result["failed_steps"]


@pytest.mark.asyncio
async def test_fetch_ci_failure_logs_missing_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(ValueError, match="GITHUB_TOKEN environment variable is not set."):
        await fetch_ci_failure_logs("org/epok", 88888)


# --- Ticket 5.2 Tests: Gemini Self-Healing Patch Repair Activity ---

from activities.ci_activities import generate_ci_repair_patches


@pytest.mark.asyncio
async def test_generate_ci_repair_patches_success(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")

    mock_patches_output = CodePatchesOutput(
        patches=[
            FilePatch(path="src/main.py", content="def main(): return 'fixed'\n")
        ]
    )

    mock_response = MagicMock()
    mock_response.text = mock_patches_output.model_dump_json()

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    monkeypatch.setattr("activities.ci_activities.genai.Client", lambda api_key: mock_client)

    result = await generate_ci_repair_patches(
        repo_name="org/epok",
        head_branch="epok/test-branch",
        error_trace="AssertionError: expected 'fixed' got 'broken'",
        current_files={"src/main.py": "def main(): return 'broken'\n"}
    )
    assert "src/main.py" in result
    assert result["src/main.py"] == "def main(): return 'fixed'\n"
    mock_client.aio.models.generate_content.assert_called_once()


@pytest.mark.asyncio
async def test_generate_ci_repair_patches_missing_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable is not set."):
        await generate_ci_repair_patches("org/epok", "epok/test-branch", "error trace")


# --- Ticket 6.2 Tests: Linear State & Comment Sync Activity ---

from activities.linear_activities import update_linear_issue_status


@pytest.mark.asyncio
async def test_update_linear_issue_status_success(monkeypatch):
    monkeypatch.setenv("LINEAR_API_KEY", "fake-linear-key")

    mock_comment_response = MagicMock()
    mock_comment_response.raise_for_status = lambda: None
    mock_comment_response.json.return_value = {
        "data": {"commentCreate": {"success": True, "comment": {"id": "comment_123"}}}
    }

    mock_states_response = MagicMock()
    mock_states_response.raise_for_status = lambda: None
    mock_states_response.json.return_value = {
        "data": {
            "workflowStates": {
                "nodes": [
                    {"id": "state_in_review", "name": "In Review"}
                ]
            }
        }
    }

    mock_update_response = MagicMock()
    mock_update_response.raise_for_status = lambda: None
    mock_update_response.json.return_value = {
        "data": {"issueUpdate": {"success": True}}
    }

    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=[mock_comment_response, mock_states_response, mock_update_response])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr("activities.linear_activities.httpx.AsyncClient", lambda **kwargs: mock_client)

    result = await update_linear_issue_status(
        issue_id="lin-101",
        state_name="In Review",
        comment_body="PR created: https://github.com/org/epok/pull/42"
    )

    assert result["issue_id"] == "lin-101"
    assert result["state_name"] == "In Review"
    assert result["state_updated"] is True
    assert result["comment_posted"] is True


@pytest.mark.asyncio
async def test_update_linear_issue_status_missing_api_key(monkeypatch):
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)
    with pytest.raises(ValueError, match="LINEAR_API_KEY environment variable is not set."):
        await update_linear_issue_status("lin-101")