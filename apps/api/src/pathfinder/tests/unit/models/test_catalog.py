"""Unit tests for the model catalog smallest-per-provider invariant."""

from __future__ import annotations

from typing import cast

import pytest

from pathfinder.ai.models.catalog import (
    ModelEntry,
    get_model_catalog,
    get_smallest_model,
)
from pathfinder.platform.types import ModelProvider


def test_every_provider_has_at_most_one_smallest_entry() -> None:
    catalog = get_model_catalog()
    counts: dict[ModelProvider, int] = {}
    for entry in catalog:
        if entry.is_provider_smallest:
            counts[entry.provider] = counts.get(entry.provider, 0) + 1
    duplicates = {p: n for p, n in counts.items() if n > 1}
    assert duplicates == {}, (
        f"multiple is_provider_smallest=True entries per provider: {duplicates}"
    )


def test_every_cloud_provider_has_a_smallest_entry() -> None:
    catalog = get_model_catalog()
    providers_with_smallest: set[ModelProvider] = {
        entry.provider for entry in catalog if entry.is_provider_smallest
    }
    required: set[ModelProvider] = {"openai", "anthropic", "google"}
    missing = required - providers_with_smallest
    assert missing == set(), f"missing smallest-model for providers: {missing}"


@pytest.mark.parametrize("provider", ["openai", "anthropic", "google"])
def test_get_smallest_model_returns_marked_entry(provider: ModelProvider) -> None:
    entry = get_smallest_model(provider)
    assert isinstance(entry, ModelEntry)
    assert entry.provider == provider
    assert entry.is_provider_smallest is True


def test_get_smallest_model_raises_for_unknown_provider() -> None:
    # Cast through a typed var so we don't need `# type: ignore` on the call.
    # The runtime behaviour is what we're asserting; Pyright only sees the
    # narrower Literal[...] after assignment, which matches ModelProvider.
    bogus_provider = cast("ModelProvider", "nonexistent")
    with pytest.raises(LookupError):
        get_smallest_model(bogus_provider)


def test_openai_smallest_is_gpt_4_1_nano() -> None:
    assert get_smallest_model("openai").id == "openai/gpt-4.1-nano"


def test_anthropic_smallest_is_haiku() -> None:
    assert get_smallest_model("anthropic").id == "anthropic/claude-haiku-4-5"


def test_google_smallest_is_gemini_2_5_flash() -> None:
    assert get_smallest_model("google").id == "google/gemini-2.5-flash"
