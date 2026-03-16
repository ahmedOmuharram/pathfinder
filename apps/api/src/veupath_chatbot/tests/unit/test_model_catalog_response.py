"""Tests for ModelCatalogEntryResponse and ModelListResponse."""

from veupath_chatbot.transport.http.routers.models import (
    ModelCatalogEntryResponse,
    ModelListResponse,
)


def _has_snake_case_key(dumped: dict) -> str | None:
    """Return the first snake_case key at top level, or None."""
    for key in dumped:
        if "_" in key and not key.startswith("_"):
            return key
    return None


class TestModelCatalogEntryResponse:
    """ModelCatalogEntryResponse serialization and construction."""

    def test_construction_with_all_fields(self):
        entry = ModelCatalogEntryResponse(
            id="openai/gpt-4.1",
            name="GPT-4.1",
            provider="openai",
            model="gpt-4.1",
            description="Flagship model",
            supports_reasoning=False,
            enabled=True,
            context_size=1_000_000,
            default_reasoning_budget=0,
            input_price=2.0,
            cached_input_price=0.5,
            output_price=8.0,
        )
        assert entry.id == "openai/gpt-4.1"
        assert entry.supports_reasoning is False
        assert entry.context_size == 1_000_000

    def test_camel_case_serialization(self):
        entry = ModelCatalogEntryResponse(
            id="openai/gpt-4.1",
            name="GPT-4.1",
            provider="openai",
            model="gpt-4.1",
        )
        dumped = entry.model_dump(by_alias=True)
        expected_keys = {
            "id",
            "name",
            "provider",
            "model",
            "description",
            "supportsReasoning",
            "enabled",
            "contextSize",
            "defaultReasoningBudget",
            "inputPrice",
            "cachedInputPrice",
            "outputPrice",
        }
        assert set(dumped.keys()) == expected_keys
        snake_key = _has_snake_case_key(dumped)
        assert snake_key is None, f"snake_case key: {snake_key}"

    def test_defaults(self):
        entry = ModelCatalogEntryResponse(
            id="test",
            name="Test",
            provider="openai",
            model="test-model",
        )
        assert entry.supports_reasoning is False
        assert entry.enabled is True
        assert entry.context_size == 0
        assert entry.default_reasoning_budget == 0
        assert entry.input_price == 0.0
        assert entry.cached_input_price == 0.0
        assert entry.output_price == 0.0
        assert entry.description == ""

    def test_populate_by_name_with_alias(self):
        """Can construct using camelCase aliases."""
        entry = ModelCatalogEntryResponse(
            id="test",
            name="Test",
            provider="anthropic",
            model="claude-4",
            supportsReasoning=True,
            contextSize=200_000,
            inputPrice=3.0,
            cachedInputPrice=0.3,
            outputPrice=15.0,
        )
        assert entry.supports_reasoning is True
        assert entry.context_size == 200_000

    def test_roundtrip(self):
        entry = ModelCatalogEntryResponse(
            id="google/gemini-2.5-pro",
            name="Gemini 2.5 Pro",
            provider="google",
            model="gemini-2.5-pro",
            supports_reasoning=True,
            context_size=1_000_000,
            input_price=1.25,
            cached_input_price=0.32,
            output_price=10.0,
        )
        dumped = entry.model_dump(by_alias=True)
        reconstructed = ModelCatalogEntryResponse(**dumped)
        assert reconstructed.model_dump(by_alias=True) == dumped


class TestModelListResponse:
    """ModelListResponse wraps multiple entries."""

    def test_construction(self):
        entries = [
            ModelCatalogEntryResponse(
                id="openai/gpt-4.1",
                name="GPT-4.1",
                provider="openai",
                model="gpt-4.1",
            ),
            ModelCatalogEntryResponse(
                id="anthropic/claude-4-opus",
                name="Claude 4 Opus",
                provider="anthropic",
                model="claude-4-opus",
            ),
        ]
        response = ModelListResponse(
            models=entries,
            default="openai/gpt-4.1",
            default_reasoning_effort="medium",
        )
        assert len(response.models) == 2
        assert response.default == "openai/gpt-4.1"
        assert response.default_reasoning_effort == "medium"

    def test_camel_case_serialization(self):
        response = ModelListResponse(
            models=[],
            default="openai/gpt-4.1",
            defaultReasoningEffort="high",
        )
        dumped = response.model_dump(by_alias=True)
        assert "defaultReasoningEffort" in dumped
        snake_key = _has_snake_case_key(dumped)
        assert snake_key is None, f"snake_case key: {snake_key}"

    def test_nested_entries_camel_case(self):
        entry = ModelCatalogEntryResponse(
            id="openai/o3",
            name="O3",
            provider="openai",
            model="o3",
            supportsReasoning=True,
        )
        response = ModelListResponse(
            models=[entry],
            default="openai/o3",
            defaultReasoningEffort="high",
        )
        dumped = response.model_dump(by_alias=True)
        model_dumped = dumped["models"][0]
        snake_key = _has_snake_case_key(model_dumped)
        assert snake_key is None, f"Nested snake_case key: {snake_key}"
        assert model_dumped["supportsReasoning"] is True
