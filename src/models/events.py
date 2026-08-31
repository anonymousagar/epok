from typing import List, Optional
from pydantic import BaseModel


class LinearIssueData(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    url: str
    updatedAt: str


class LinearWebhookPayload(BaseModel):
    action: str
    data: LinearIssueData


class SlackAction(BaseModel):
    block_id: str
    action_id: str
    value: str


class SlackUser(BaseModel):
    id: str
    username: str


class SlackBlockActionsPayload(BaseModel):
    type: str
    user: SlackUser
    actions: List[SlackAction]
    response_url: Optional[str] = None


class GitHubWorkflowRun(BaseModel):
    id: int
    name: str
    head_branch: str
    conclusion: Optional[str] = None
    html_url: str


class GitHubWorkflowRunPayload(BaseModel):
    action: str
    workflow_run: GitHubWorkflowRun