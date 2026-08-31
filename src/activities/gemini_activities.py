import os
from typing import Any, Dict
from google import genai
from google.genai import types
from models.dtos import SpecArchitectureOutput
from temporalio import activity

SPEC_SYSTEM_INSTRUCTION = """You are a Principal Software Architect at Epok.
Your job is to analyze incoming feature requests/bug reports and target codebase context to design clean, minimal, production-grade architecture plans.
Always provide a concise executive summary, pinpoint exact file paths to create or modify, step-by-step implementation tasks, and a robust testing strategy."""


@activity.defn
async def generate_technical_spec(
    issue_context: Dict[str, Any],
    repo_context: Dict[str, Any]
) -> SpecArchitectureOutput:
    """Invokes Gemini 2.5 Flash with structured output schema to produce an architecture specification."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set.")

    client = genai.Client(api_key=api_key)

    prompt = f"""
### Linear Issue Context:
- Title: {issue_context.get('title', '')}
- Description: {issue_context.get('description', '')}
- URL: {issue_context.get('url', '')}

### Target Repository Context:
- Repository: {repo_context.get('repo_name', '')}
- Default Branch: {repo_context.get('default_branch', '')}
- File Tree (Sample):
{chr(10).join(repo_context.get('file_paths', [])[:50])}

### Manifests & Entrypoints:
{repo_context.get('manifests', {})}
"""

    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SPEC_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=SpecArchitectureOutput,
            temperature=0.2,
        ),
    )

    if not response.text:
        raise ValueError("Gemini returned empty text response for technical spec generation.")

    return SpecArchitectureOutput.model_validate_json(response.text)