"""Tests for prompt bundle helpers used by tracing and agents."""

from hashlib import sha256
from unittest.mock import patch

from pathfinder.ai.prompts.loader import load_system_prompt_bundle
from pathfinder.ai.prompts.workbench_chat import (
    _load_workbench_prompt,
    build_workbench_system_prompt,
)
from pathfinder.platform.langfuse.prompts import LoadedPrompt


def test_load_system_prompt_bundle_metadata() -> None:
    load_system_prompt_bundle.cache_clear()
    prompts = {
        "system": LoadedPrompt(
            name="system",
            text="system prompt",
            label="production",
            source="langfuse",
            version=2,
        ),
        "safety": LoadedPrompt(
            name="safety",
            text="safety prompt",
            label="production",
            source="local",
        ),
        "site-hints": LoadedPrompt(
            name="site-hints",
            text="site hints",
            label="production",
            source="langfuse",
            version=4,
        ),
    }

    with patch(
        "pathfinder.ai.prompts.loader.load_prompt_result",
        side_effect=lambda name: prompts[name],
    ):
        bundle = load_system_prompt_bundle()

    assert bundle.text == "system prompt\n\n---\n\nsafety prompt\n\n---\n\nsite hints"
    assert (
        bundle.langfuse_metadata()["prompt_bundle"]
        == "system@2,safety@local,site-hints@4"
    )
    assert (
        bundle.langfuse_metadata()["prompt_bundle_hash"]
        == sha256(bundle.text.encode("utf-8")).hexdigest()
    )
    assert bundle.langfuse_metadata()["system_prompt_version"] == "2"
    assert bundle.langfuse_metadata()["site_hints_prompt_version"] == "4"


def test_build_workbench_system_prompt_uses_langfuse_managed_prompt() -> None:
    _load_workbench_prompt.cache_clear()
    with (
        patch(
            "pathfinder.ai.prompts.workbench_chat.load_system_prompt",
            return_value="base prompt",
        ),
        patch(
            "pathfinder.ai.prompts.workbench_chat.load_prompt",
            return_value="workbench prompt",
        ) as mock_load_prompt,
    ):
        result = build_workbench_system_prompt(
            site_id="plasmodb",
            experiment_context={},
        )

    assert "base prompt" in result
    assert "workbench prompt" in result
    mock_load_prompt.assert_called_once_with("workbench")
