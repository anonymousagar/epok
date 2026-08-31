import pytest
import httpx
from activities.linear_activities import fetch_linear_issue_details


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