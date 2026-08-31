import os
from typing import Dict, Any
from google import genai
from google.genai import types
from temporalio import activity
from models.dtos import SpecArchitectureOutput, CodePatchesOutput

CODE_GEN_SYSTEM_INSTRUCTION = """You are a Principal Software Engineer at Epok.
Your job is to take an approved architecture specification, implementation plan, and current target codebase files, and generate complete, production-grade source code updates for all impacted files.
Always return complete file contents for each impacted file path — do not use placeholders, truncated code, or ellipses."""


@activity.defn
async def generate_code_patches(
    spec: SpecArchitectureOutput,
    repo_context: Dict[str, Any],
    existing_file_contents: Dict[str, str] = {}
) -> Dict[str, str]:
    """
    Invokes Gemini 2.5 Flash with structured output schema to produce full code replacements
    for all files specified in spec.impacted_files.
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set.")

    client = genai.Client(api_key=api_key)

    existing_files_summary = ""
    for path in spec.impacted_files:
        content = existing_file_contents.get(path, "(New file)")
        existing_files_summary += f"\n--- File: {path} ---\n{content}\n"

    prompt = f"""
### Executive Architecture Plan:
{spec.summary}

### Implementation Steps:
{chr(10).join(f"- {step}" for step in spec.implementation_steps)}

### Testing Strategy:
{spec.test_strategy}

### Target Repository:
- Repository: {repo_context.get('repo_name', '')}
- Branch: {repo_context.get('default_branch', 'main')}

### Impacted Files & Current Content:
{existing_files_summary}

Please generate the complete, updated code for all impacted files.
"""

    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=CODE_GEN_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=CodePatchesOutput,
            temperature=0.2,
        ),
    )

    if not response.text:
        raise ValueError("Gemini returned empty text response for code patch generation.")

    patches_output = CodePatchesOutput.model_validate_json(response.text)
    return {patch.path: patch.content for patch in patches_output.patches}
