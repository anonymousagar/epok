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