"""Tests for PipelineConfig validation."""

import pytest
from pydantic import ValidationError

from pathfinder.platform.event_schemas import PipelineConfig, PipelinePhaseConfig


def test_pipeline_config_valid() -> None:
    """A fully specified pipeline config is valid."""
    config = PipelineConfig(
        discovery=PipelinePhaseConfig(model_id="anthropic/claude-sonnet-4-6", reasoning_effort="medium"),
        planning=PipelinePhaseConfig(model_id="anthropic/claude-opus-4-6", reasoning_effort="high"),
        execution=PipelinePhaseConfig(model_id="anthropic/claude-sonnet-4-6", reasoning_effort="medium"),
        verification=PipelinePhaseConfig(model_id="anthropic/claude-opus-4-6", reasoning_effort="high"),
    )
    assert config.planning.model_id == "anthropic/claude-opus-4-6"
    assert config.planning.reasoning_effort == "high"


def test_pipeline_config_camel_case_serialization() -> None:
    """Pipeline config serializes to camelCase for the frontend."""
    config = PipelineConfig(
        discovery=PipelinePhaseConfig(model_id="anthropic/claude-sonnet-4-6", reasoning_effort="medium"),
        planning=PipelinePhaseConfig(model_id="anthropic/claude-opus-4-6", reasoning_effort="high"),
        execution=PipelinePhaseConfig(model_id="anthropic/claude-sonnet-4-6", reasoning_effort="medium"),
        verification=PipelinePhaseConfig(model_id="anthropic/claude-opus-4-6", reasoning_effort="high"),
    )
    data = config.model_dump(by_alias=True)
    assert "modelId" in data["planning"]
    assert "reasoningEffort" in data["planning"]


def test_pipeline_config_missing_phase_raises() -> None:
    """Omitting a required phase raises ValidationError."""
    with pytest.raises(ValidationError):
        PipelineConfig(
            discovery=PipelinePhaseConfig(model_id="x", reasoning_effort="medium"),
            planning=PipelinePhaseConfig(model_id="x", reasoning_effort="medium"),
            execution=PipelinePhaseConfig(model_id="x", reasoning_effort="medium"),
            # verification missing
        )


def test_pipeline_config_invalid_effort_raises() -> None:
    """Invalid reasoning effort raises ValidationError."""
    with pytest.raises(ValidationError):
        PipelinePhaseConfig(model_id="x", reasoning_effort="extreme")  # type: ignore[arg-type]
