"""The analysis-state card reaches the thread only when the state changed."""

from __future__ import annotations

from uuid import uuid4

from shared_py.stream_parts.eda import EdaAnalysisState

from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.tools.standalone._eda_stream_parts import (
    analysis_state_chunks_if_changed,
)


def _state(*, num_computations: int = 0) -> EdaAnalysisState:
    return EdaAnalysisState(
        site_id="plasmodb",
        dataset_id="DS_1",
        study_id="STUDY_1",
        analysis_id="AN_1",
        revision=None,
        study_display_name="Febrile versus normal heat-shock expression",
        display_name="Heat shock",
        num_filters=0,
        num_computations=num_computations,
        filters=[],
        filter_summaries=[],
        entity_counts=[],
        can_export_rows=True,
    )


def _pipeline() -> PipelineState:
    return PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
    )


def test_an_unchanged_state_emits_no_second_card() -> None:
    pipeline = _pipeline()
    first = analysis_state_chunks_if_changed(_state(), domain=pipeline.domain)
    second = analysis_state_chunks_if_changed(_state(), domain=pipeline.domain)
    assert len(first) == 1
    assert second == []


def test_a_changed_state_emits_again() -> None:
    pipeline = _pipeline()
    analysis_state_chunks_if_changed(_state(), domain=pipeline.domain)
    changed = analysis_state_chunks_if_changed(
        _state(num_computations=1), domain=pipeline.domain
    )
    assert len(changed) == 1


def test_the_card_reconciles_by_its_analysis_id() -> None:
    pipeline = _pipeline()
    (chunk,) = analysis_state_chunks_if_changed(_state(), domain=pipeline.domain)
    assert chunk.id == "AN_1"
