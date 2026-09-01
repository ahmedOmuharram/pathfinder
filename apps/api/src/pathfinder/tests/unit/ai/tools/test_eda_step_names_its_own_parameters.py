"""The tool's prose names only parameters its schema declares."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic_ai import Tool

import pathfinder.ai.tools.standalone.eda_step
from pathfinder.ai.tools.standalone.eda_step import create_eda_step


def test_the_docstring_and_retries_name_only_declared_parameters() -> None:
    tool = Tool(create_eda_step)
    declared = set(tool.function_schema.json_schema["properties"])
    source = Path(pathfinder.ai.tools.standalone.eda_step.__file__).read_text()
    camel_forms = set(
        re.findall(r"\b(?:effect|significance)[A-Za-z]*[A-Z][A-Za-z]*\b", source)
    )
    assert camel_forms == set(), camel_forms
    for name in ("effect_size_threshold", "significance_threshold", "effect_direction"):
        assert name in declared
        assert name in (tool.description or "")
