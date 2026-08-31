from typing import List, Optional
from pydantic import BaseModel


class SpecArchitectureOutput(BaseModel):
    summary: str
    impacted_files: List[str]
    implementation_steps: List[str]
    test_strategy: str


class CodePatchResult(BaseModel):
    branch_name: str
    pr_url: str
    pr_number: int
    commit_sha: str


class CIExecutionResult(BaseModel):
    success: bool
    iteration: int
    logs: Optional[str] = None
    error_trace: Optional[str] = None
