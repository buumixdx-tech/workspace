"""Markdown prompt loader.

Reads prompts/{mode}.md, parses YAML frontmatter, splits body on `--- user ---`,
and substitutes the schema / input placeholders with text generated from the
Pydantic models in schemas.py.

Public API:
    load_prompt(mode: str, input_payload: LLMInput) -> tuple[str, str, dict]
        returns (system_prompt, user_prompt, frontmatter)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .schemas import LLMInput, LLMOutput

PROMPTS_DIR = Path(__file__).parent
USER_DELIM = "\n--- user ---\n"


def _schema_text(model: type) -> str:
    """Render a Pydantic model as pretty-printed JSON Schema text."""
    return json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2)


def _split_frontmatter(md: str) -> tuple[dict[str, Any], str]:
    """Parse optional `--- \\n yaml \\n --- \\n body` header; return (fm, body)."""
    if md.startswith("---\n"):
        # find the closing `---\n`
        end = md.find("\n---\n", 4)
        if end == -1:
            raise ValueError("frontmatter opened with --- but no closing --- found")
        yaml_block = md[4:end]
        body = md[end + 5 :]
        fm = yaml.safe_load(yaml_block) or {}
        if not isinstance(fm, dict):
            raise ValueError(f"frontmatter must be a YAML mapping, got {type(fm).__name__}")
        return fm, body
    return {}, md


def load_prompt(mode: str, input_payload: LLMInput) -> tuple[str, str, dict[str, Any]]:
    """Load and render the prompt for a given mode + input.

    Returns (system_prompt, user_prompt, frontmatter).
    `frontmatter` is a plain dict with at least `name`, `version`, `model`.
    """
    md_path = PROMPTS_DIR / f"{mode}.md"
    if not md_path.is_file():
        raise FileNotFoundError(f"prompt file not found: {md_path}")
    md = md_path.read_text(encoding="utf-8")

    frontmatter, body = _split_frontmatter(md)
    if "model" not in frontmatter:
        raise ValueError(f"{md_path} frontmatter missing required 'model' field")

    if USER_DELIM not in body:
        raise ValueError(
            f"{md_path} body missing the `--- user ---` delimiter; "
            f"cannot split system vs user sections"
        )
    system_part, user_part = body.split(USER_DELIM, 1)

    # 三个占位符替换
    system = (
        system_part.replace("{{OUTPUT_SCHEMA}}", _schema_text(LLMOutput))
        .replace("{{INPUT_SCHEMA}}", _schema_text(LLMInput))
    )
    user = user_part.replace(
        "{{input_json}}",
        json.dumps(input_payload.model_dump(), ensure_ascii=False, indent=2),
    )

    return system, user, frontmatter
