"""Tests for tier preset registry."""

from veupath_chatbot.ai.models.catalog import get_model_entry
from veupath_chatbot.ai.models.tiers import TIER_PRESETS, TierPreset


def test_all_preset_model_ids_exist_in_catalog() -> None:
    """Every model ID referenced by a tier preset must exist in the catalog."""
    missing: list[str] = []
    for provider, tiers in TIER_PRESETS.items():
        for tier_name, preset in tiers.items():
            for phase in ("discovery", "planning", "execution", "verification"):
                phase_config = getattr(preset, phase)
                if get_model_entry(phase_config.model_id) is None:
                    missing.append(f"{provider}/{tier_name}/{phase}: {phase_config.model_id}")
    assert missing == [], f"Missing catalog entries: {missing}"


def test_all_providers_have_all_tiers() -> None:
    """Every provider must define quality, balanced, and fast tiers."""
    for provider, tiers in TIER_PRESETS.items():
        assert set(tiers.keys()) == {"quality", "balanced", "fast"}, (
            f"Provider {provider!r} missing tiers: {set(tiers.keys())}"
        )


def test_preset_returns_correct_type() -> None:
    """Each preset value is a TierPreset dataclass."""
    for tiers in TIER_PRESETS.values():
        for preset in tiers.values():
            assert isinstance(preset, TierPreset)


def test_quality_tier_uses_strongest_for_planning() -> None:
    """Quality tier should use the strongest model for planning."""
    anthropic_quality = TIER_PRESETS["anthropic"]["quality"]
    assert "opus" in anthropic_quality.planning.model_id
    assert anthropic_quality.planning.reasoning_effort == "high"
