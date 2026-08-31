import os
import httpx
from temporalio import activity

LINEAR_GRAPHQL_ENDPOINT = "https://api.linear.app/graphql"

ISSUE_QUERY = """
query GetIssueDetails($id: String!) {
  issue(id: $id) {
    id
    title
    description
    url
    state {
      name
    }
    assignee {
      name
    }
  }
}
"""


@activity.defn
async def fetch_linear_issue_details(issue_id: str) -> dict:
    api_key = os.getenv("LINEAR_API_KEY", "")
    if not api_key:
        raise ValueError("LINEAR_API_KEY environment variable is not set.")

    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            LINEAR_GRAPHQL_ENDPOINT,
            headers=headers,
            json={"query": ISSUE_QUERY, "variables": {"id": issue_id}}
        )
        response.raise_for_status()
        data = response.json()

    if "errors" in data and data["errors"]:
        raise ValueError(f"Linear GraphQL error: {data['errors']}")

    issue_data = data.get("data", {}).get("issue")
    if not issue_data:
        raise ValueError(f"Issue {issue_id} not found in Linear.")

    return {
        "id": issue_data["id"],
        "title": issue_data["title"],
        "description": issue_data.get("description") or "",
        "url": issue_data["url"],
        "state": issue_data.get("state", {}).get("name") if issue_data.get("state") else "Unknown",
        "assignee": issue_data.get("assignee", {}).get("name") if issue_data.get("assignee") else None
    }