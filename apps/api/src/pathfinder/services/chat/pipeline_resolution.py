"""Shared pipeline resolution for chat turns."""

from collections.abc import Callable

from pathfinder.ai.models.tiers import TierPreset
from pathfinder.platform.event_schemas import PipelineConfig, PipelinePhaseConfig
from pathfinder.platform.types import ModelProvider, TierName


def build_mock_pipeline() -> PipelineConfig:
    """Return the deterministic mock pipeline used for offline testing."""
    mock_phase = PipelinePhaseConfig(
        model_id="mock/deterministic",
        reasoning_effort="medium",
    )
    return PipelineConfig(
        scoping=mock_phase,
        discovery=mock_phase,
        planning=mock_phase,
        execution=mock_phase,
        verification=mock_phase,
    )


def is_mock_model_id(model_id: str) -> bool:
    """Return whether a model id targets the mock engine."""
    return model_id.strip().lower().startswith("mock/")


def pipeline_uses_mock_models(pipeline: PipelineConfig) -> bool:
    """Return whether any phase in the pipeline targets the mock engine."""
    return any(
        is_mock_model_id(phase.model_id)
        for phase in (
            pipeline.scoping,
            pipeline.discovery,
            pipeline.planning,
            pipeline.execution,
            pipeline.verification,
        )
    )


def _replace_mock_phases(
    pipeline: PipelineConfig,
    fallback: PipelineConfig,
) -> PipelineConfig:
    return PipelineConfig(
        scoping=(
            fallback.scoping
            if is_mock_model_id(pipeline.scoping.model_id)
            else pipeline.scoping
        ),
        discovery=(
            fallback.discovery
            if is_mock_model_id(pipeline.discovery.model_id)
            else pipeline.discovery
        ),
        planning=(
            fallback.planning
            if is_mock_model_id(pipeline.planning.model_id)
            else pipeline.planning
        ),
        execution=(
            fallback.execution
            if is_mock_model_id(pipeline.execution.model_id)
            else pipeline.execution
        ),
        verification=(
            fallback.verification
            if is_mock_model_id(pipeline.verification.model_id)
            else pipeline.verification
        ),
    )


def build_default_pipeline(
    *,
    default_provider: ModelProvider,
    default_tier: TierName,
    get_tier_preset: Callable[[ModelProvider, TierName], TierPreset | None],
) -> PipelineConfig:
    """Build the default runtime pipeline from the configured provider tier."""
    preset = get_tier_preset(default_provider, default_tier)
    if preset is None:
        fallback = PipelinePhaseConfig(
            model_id=f"{default_provider}/default",
            reasoning_effort="medium",
        )
        return PipelineConfig(
            scoping=fallback,
            discovery=fallback,
            planning=fallback,
            execution=fallback,
            verification=fallback,
        )

    return PipelineConfig(
        scoping=PipelinePhaseConfig(
            model_id=preset.scoping.model_id,
            reasoning_effort=preset.scoping.reasoning_effort,
        ),
        discovery=PipelinePhaseConfig(
            model_id=preset.discovery.model_id,
            reasoning_effort=preset.discovery.reasoning_effort,
        ),
        planning=PipelinePhaseConfig(
            model_id=preset.planning.model_id,
            reasoning_effort=preset.planning.reasoning_effort,
        ),
        execution=PipelinePhaseConfig(
            model_id=preset.execution.model_id,
            reasoning_effort=preset.execution.reasoning_effort,
        ),
        verification=PipelinePhaseConfig(
            model_id=preset.verification.model_id,
            reasoning_effort=preset.verification.reasoning_effort,
        ),
    )


def resolve_pipeline_config(
    *,
    chat_provider: str,
    default_provider: ModelProvider,
    default_tier: TierName,
    get_tier_preset: Callable[[ModelProvider, TierName], TierPreset | None],
    pipeline_override: PipelineConfig | None = None,
    persisted_pipeline: dict[str, object] | None = None,
) -> PipelineConfig:
    """Resolve the effective pipeline for a chat turn."""
    if chat_provider == "mock":
        return build_mock_pipeline()

    default_pipeline = build_default_pipeline(
        default_provider=default_provider,
        default_tier=default_tier,
        get_tier_preset=get_tier_preset,
    )

    if pipeline_override is not None:
        return _replace_mock_phases(pipeline_override, default_pipeline)

    if persisted_pipeline is not None:
        candidate = dict(persisted_pipeline)
        if "scoping" not in candidate and "discovery" in candidate:
            candidate["scoping"] = candidate["discovery"]
        resolved = PipelineConfig.model_validate(candidate)
        return _replace_mock_phases(resolved, default_pipeline)

    return default_pipeline
