"""Tests for ai.models.catalog — ModelEntry, get_model_catalog, and reasoning hyperparams."""

import pytest

from veupath_chatbot.ai.models.catalog import (
    ModelEntry,
    ModelProvider,
    ReasoningEffort,
    build_reasoning_hyperparams,
    get_model_catalog,
    get_model_entry,
)

# ---------------------------------------------------------------------------
# get_model_catalog integrity
# ---------------------------------------------------------------------------


class TestModelCatalog:
    def test_catalog_is_non_empty(self):
        assert len(get_model_catalog()) > 0

    def test_all_entries_are_model_entry(self):
        for entry in get_model_catalog():
            assert isinstance(entry, ModelEntry)

    def test_all_ids_unique(self):
        ids = [e.id for e in get_model_catalog()]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {ids}"

    def test_all_models_unique(self):
        models = [e.model for e in get_model_catalog()]
        assert len(models) == len(set(models)), f"Duplicate models: {models}"

    def test_id_format_is_provider_slash_model(self):
        for entry in get_model_catalog():
            assert "/" in entry.id, f"ID missing '/': {entry.id}"
            prefix = entry.id.split("/")[0]
            assert prefix == entry.provider, (
                f"ID prefix '{prefix}' does not match provider '{entry.provider}'"
            )

    def test_all_providers_are_valid(self):
        valid_providers: set[ModelProvider] = {
            "openai",
            "anthropic",
            "google",
            "ollama",
            "mock",
        }
        for entry in get_model_catalog():
            assert entry.provider in valid_providers, (
                f"Unknown provider: {entry.provider}"
            )

    def test_all_entries_have_name(self):
        for entry in get_model_catalog():
            assert entry.name.strip(), f"Entry {entry.id} has empty name"

    def test_all_entries_have_model(self):
        for entry in get_model_catalog():
            assert entry.model.strip(), f"Entry {entry.id} has empty model"

    def test_has_openai_entries(self):
        openai_entries = [e for e in get_model_catalog() if e.provider == "openai"]
        assert len(openai_entries) >= 1

    def test_has_anthropic_entries(self):
        anthropic_entries = [
            e for e in get_model_catalog() if e.provider == "anthropic"
        ]
        assert len(anthropic_entries) >= 1

    def test_has_google_entries(self):
        google_entries = [e for e in get_model_catalog() if e.provider == "google"]
        assert len(google_entries) >= 1


# ---------------------------------------------------------------------------
# get_model_entry
# ---------------------------------------------------------------------------


class TestGetModelEntry:
    def test_existing_model(self):
        entry = get_model_entry("openai/gpt-4.1")
        assert entry is not None
        assert entry.provider == "openai"
        assert entry.model == "gpt-4.1"

    def test_nonexistent_model(self):
        entry = get_model_entry("openai/nonexistent")
        assert entry is None

    def test_empty_string(self):
        entry = get_model_entry("")
        assert entry is None

    def test_all_catalog_entries_are_findable(self):
        for catalog_entry in get_model_catalog():
            found = get_model_entry(catalog_entry.id)
            assert found is catalog_entry


# ---------------------------------------------------------------------------
# ModelEntry frozen
# ---------------------------------------------------------------------------


class TestModelEntryFrozen:
    def test_frozen(self):
        entry = ModelEntry(
            id="test/model",
            name="Test Model",
            provider="openai",
            model="test-model",
        )
        with pytest.raises(AttributeError):
            entry.id = "changed"  # type: ignore[misc]

    def test_defaults(self):
        entry = ModelEntry(
            id="test/model",
            name="Test Model",
            provider="openai",
            model="test-model",
        )
        assert entry.supports_reasoning is False
        assert entry.description == ""
        assert entry.input_price == 0.0
        assert entry.cached_input_price == 0.0
        assert entry.output_price == 0.0


# ---------------------------------------------------------------------------
# build_reasoning_hyperparams
# ---------------------------------------------------------------------------


class TestBuildReasoningHyperparams:
    def test_none_effort_returns_empty(self):
        result = build_reasoning_hyperparams("openai", None)
        assert result == {}

    @pytest.mark.parametrize("provider", ["openai", "anthropic", "google"])
    def test_all_efforts_for_all_providers(self, provider: ModelProvider):
        efforts: list[ReasoningEffort] = ["none", "low", "medium", "high"]
        for effort in efforts:
            result = build_reasoning_hyperparams(provider, effort)
            assert isinstance(result, dict)

    def test_openai_high_has_reasoning_effort(self):
        result = build_reasoning_hyperparams("openai", "high")
        assert result.get("reasoning_effort") == "high"

    def test_openai_medium_is_empty(self):
        """Medium is server default for OpenAI, so no param needed."""
        result = build_reasoning_hyperparams("openai", "medium")
        assert result == {}

    def test_anthropic_high_has_thinking(self):
        result = build_reasoning_hyperparams("anthropic", "high")
        assert "thinking" in result
        thinking = result["thinking"]
        assert isinstance(thinking, dict)
        assert thinking["type"] == "enabled"
        assert thinking["budget_tokens"] == 32768

    def test_anthropic_none_is_empty(self):
        result = build_reasoning_hyperparams("anthropic", "none")
        assert result == {}

    def test_google_none_disables_thinking(self):
        result = build_reasoning_hyperparams("google", "none")
        assert "thinking_config" in result
        assert result["thinking_config"]["thinking_budget"] == 0

    def test_google_high_has_large_budget(self):
        result = build_reasoning_hyperparams("google", "high")
        assert result["thinking_config"]["thinking_budget"] == 24576

    def test_unknown_provider_returns_empty(self):
        """Unknown provider should return empty dict (no crash)."""
        result = build_reasoning_hyperparams("unknown_provider", "high")  # type: ignore[arg-type]
        assert result == {}

    def test_returns_new_dict_each_call(self):
        """Must return a fresh dict to prevent mutation leaks."""
        r1 = build_reasoning_hyperparams("openai", "high")
        r2 = build_reasoning_hyperparams("openai", "high")
        assert r1 == r2
        assert r1 is not r2  # different dict objects
