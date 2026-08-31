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


COMMENT_CREATE_MUTATION = """
mutation CreateComment($issueId: String!, $body: String!) {
  commentCreate(input: { issueId: $issueId, body: $body }) {
    success
    comment {
      id
    }
  }
}
"""

WORKFLOW_STATES_QUERY = """
query GetWorkflowStates {
  workflowStates {
    nodes {
      id
      name
    }
  }
}
"""

ISSUE_UPDATE_MUTATION = """
mutation UpdateIssue($id: String!, $stateId: String!) {
  issueUpdate(id: $id, input: { stateId: $stateId }) {
    success
  }
}
"""


@activity.defn
async def update_linear_issue_status(
    issue_id: str,
    state_name: str = "",
    comment_body: str = ""
) -> dict:
    """
    Updates a Linear issue status and/or posts a markdown comment via Linear GraphQL API.
    """
    api_key = os.getenv("LINEAR_API_KEY", "")
    if not api_key:
        raise ValueError("LINEAR_API_KEY environment variable is not set.")

    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }

    comment_posted = False
    state_updated = False

    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Post comment if provided
        if comment_body:
            res = await client.post(
                LINEAR_GRAPHQL_ENDPOINT,
                headers=headers,
                json={"query": COMMENT_CREATE_MUTATION, "variables": {"issueId": issue_id, "body": comment_body}}
            )
            res.raise_for_status()
            data = res.json()
            if "data" in data and data["data"].get("commentCreate", {}).get("success"):
                comment_posted = True

        # 2. Update issue state if provided
        if state_name:
            # Query state ID matching state_name
            states_res = await client.post(
                LINEAR_GRAPHQL_ENDPOINT,
                headers=headers,
                json={"query": WORKFLOW_STATES_QUERY}
            )
            states_res.raise_for_status()
            states_data = states_res.json()
            nodes = states_data.get("data", {}).get("workflowStates", {}).get("nodes", [])

            state_id = None
            for node in nodes:
                if node.get("name", "").lower() == state_name.lower():
                    state_id = node.get("id")
                    break

            if state_id:
                update_res = await client.post(
                    LINEAR_GRAPHQL_ENDPOINT,
                    headers=headers,
                    json={"query": ISSUE_UPDATE_MUTATION, "variables": {"id": issue_id, "stateId": state_id}}
                )
                update_res.raise_for_status()
                update_data = update_res.json()
                if "data" in update_data and update_data["data"].get("issueUpdate", {}).get("success"):
                    state_updated = True

    return {
        "issue_id": issue_id,
        "state_name": state_name,
        "state_updated": state_updated,
        "comment_posted": comment_posted,
    }