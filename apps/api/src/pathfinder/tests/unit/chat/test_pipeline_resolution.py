from pathfinder.ai.models.tiers import get_tier_preset
from pathfinder.platform.event_schemas import PipelineConfig, PipelinePhaseConfig
from pathfinder.services.chat.pipeline_resolution import (
    build_mock_pipeline,
    resolve_pipeline_config,
)


def test_mock_chat_provider_always_uses_mock_pipeline() -> None:
    override = PipelineConfig(
        scoping=PipelinePhaseConfig(
            model_id="anthropic/claude-sonnet-4-6",
            reasoning_effort="medium",
        ),
        discovery=PipelinePhaseConfig(
            model_id="anthropic/claude-sonnet-4-6",
            reasoning_effort="medium",
        ),
        planning=PipelinePhaseConfig(
            model_id="anthropic/claude-opus-4-6",
            reasoning_effort="high",
        ),
        execution=PipelinePhaseConfig(
            model_id="anthropic/claude-sonnet-4-6",
            reasoning_effort="medium",
        ),
        verification=PipelinePhaseConfig(
            model_id="anthropic/claude-opus-4-6",
            reasoning_effort="high",
        ),
    )

    resolved = resolve_pipeline_config(
        chat_provider="mock",
        default_provider="anthropic",
        default_tier="balanced",
        get_tier_preset=get_tier_preset,
        pipeline_override=override,
    )

    assert resolved == build_mock_pipeline()


def test_real_runtime_replaces_mock_override_phases_with_default_pipeline() -> None:
    override = PipelineConfig(
        scoping=PipelinePhaseConfig(
            model_id="mock/deterministic",
            reasoning_effort="medium",
        ),
        discovery=PipelinePhaseConfig(
            model_id="openai/gpt-4.1",
            reasoning_effort="low",
        ),
        planning=PipelinePhaseConfig(
            model_id="mock/deterministic",
            reasoning_effort="medium",
        ),
        execution=PipelinePhaseConfig(
            model_id="openai/gpt-4.1-mini",
            reasoning_effort="low",
        ),
        verification=PipelinePhaseConfig(
            model_id="mock/deterministic",
            reasoning_effort="medium",
        ),
    )

    resolved = resolve_pipeline_config(
        chat_provider="default",
        default_provider="anthropic",
        default_tier="balanced",
        get_tier_preset=get_tier_preset,
        pipeline_override=override,
    )

    assert resolved.scoping.model_id == "anthropic/claude-sonnet-4-6"
    assert resolved.discovery.model_id == "openai/gpt-4.1"
    assert resolved.planning.model_id == "anthropic/claude-opus-4-6"
    assert resolved.execution.model_id == "openai/gpt-4.1-mini"
    assert resolved.verification.model_id == "anthropic/claude-sonnet-4-6"


def test_real_runtime_replaces_mock_persisted_pipeline_with_defaults() -> None:
    resolved = resolve_pipeline_config(
        chat_provider="default",
        default_provider="anthropic",
        default_tier="balanced",
        get_tier_preset=get_tier_preset,
        persisted_pipeline={
            "scoping": {
                "modelId": "mock/deterministic",
                "reasoningEffort": "medium",
            },
            "discovery": {
                "modelId": "mock/deterministic",
                "reasoningEffort": "medium",
            },
            "planning": {
                "modelId": "mock/deterministic",
                "reasoningEffort": "medium",
            },
            "execution": {
                "modelId": "mock/deterministic",
                "reasoningEffort": "medium",
            },
            "verification": {
                "modelId": "mock/deterministic",
                "reasoningEffort": "medium",
            },
        },
    )

    assert resolved.scoping.model_id == "anthropic/claude-sonnet-4-6"
    assert resolved.discovery.model_id == "anthropic/claude-sonnet-4-6"
    assert resolved.planning.model_id == "anthropic/claude-opus-4-6"
    assert resolved.execution.model_id == "anthropic/claude-sonnet-4-6"
    assert resolved.verification.model_id == "anthropic/claude-sonnet-4-6"


def test_real_runtime_uses_default_pipeline_when_no_override_exists() -> None:
    resolved = resolve_pipeline_config(
        chat_provider="default",
        default_provider="openai",
        default_tier="fast",
        get_tier_preset=get_tier_preset,
    )

    assert resolved.scoping.model_id == "openai/gpt-4.1-mini"
    assert resolved.planning.model_id == "openai/gpt-4.1"
