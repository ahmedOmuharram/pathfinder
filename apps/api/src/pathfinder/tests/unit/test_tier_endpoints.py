"""Tests for tier and model endpoint responses."""

from pathfinder.ai.models.catalog import get_model_entry
from pathfinder.ai.models.tiers import TIER_PRESETS
from pathfinder.transport.http.routers.tiers import list_tiers


async def test_tiers_endpoint_returns_all_providers() -> None:
    """GET /api/v1/tiers returns presets for all providers with tiers."""
    response = await list_tiers()
    data = response.model_dump(by_alias=True)
    assert "presets" in data
    assert "anthropic" in data["presets"]
    assert "openai" in data["presets"]
    assert "google" in data["presets"]


async def test_tiers_endpoint_has_all_tier_names() -> None:
    """Each provider has quality, balanced, and fast tiers."""
    response = await list_tiers()
    data = response.model_dump(by_alias=True)
    for provider, tiers in data["presets"].items():
        assert set(tiers.keys()) == {"quality", "balanced", "fast"}, (
            f"{provider} missing tiers"
        )


async def test_tiers_endpoint_phases_have_required_fields() -> None:
    """Each phase in a preset has modelId and reasoningEffort."""
    response = await list_tiers()
    data = response.model_dump(by_alias=True)
    for provider, tiers in data["presets"].items():
        for tier_name, preset in tiers.items():
            for phase in ("discovery", "planning", "execution", "verification"):
                assert "modelId" in preset[phase], f"{provider}/{tier_name}/{phase} missing modelId"
                assert "reasoningEffort" in preset[phase], f"{provider}/{tier_name}/{phase} missing reasoningEffort"


async def test_all_tier_models_exist_in_catalog() -> None:
    """Every model ID in tier presets resolves in the catalog."""
    for provider, tiers in TIER_PRESETS.items():
        for tier_name, preset in tiers.items():
            for phase in ("discovery", "planning", "execution", "verification"):
                phase_config = getattr(preset, phase)
                entry = get_model_entry(phase_config.model_id)
                assert entry is not None, (
                    f"{provider}/{tier_name}/{phase}: {phase_config.model_id} not in catalog"
                )
