"""Unit tests for step_analysis.orchestrator -- enrichment/movement logic."""

from dataclasses import dataclass

from veupath_chatbot.services.experiment.step_analysis.orchestrator import (
    _enrich_contributions_with_narrative,
    _enrich_step_evals_with_movement,
)
from veupath_chatbot.services.experiment.types import (
    StepContribution,
    StepEvaluation,
)
from veupath_chatbot.services.experiment.types.control_result import (
    ControlSetData,
    ControlTargetData,
    ControlTestResult,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _StepEvalCounts:
    """Hit counts for _make_step_evaluation."""

    pos_hits: int = 5
    pos_total: int = 10
    neg_hits: int = 2
    neg_total: int = 20


def _make_step_evaluation(
    *,
    step_id: str = "s1",
    counts: _StepEvalCounts | None = None,
    recall: float = 0.5,
    fpr: float = 0.1,
) -> StepEvaluation:
    c = counts or _StepEvalCounts()
    return StepEvaluation(
        step_id=step_id,
        search_name=f"Search_{step_id}",
        display_name=f"Step {step_id}",
        estimated_size=100,
        positive_hits=c.pos_hits,
        positive_total=c.pos_total,
        negative_hits=c.neg_hits,
        negative_total=c.neg_total,
        recall=recall,
        false_positive_rate=fpr,
    )


def _baseline_result(
    pos_hits: int = 8,
    pos_total: int = 10,
    neg_hits: int = 3,
    neg_total: int = 20,
    estimated_size: int = 150,
) -> ControlTestResult:
    return ControlTestResult(
        positive=ControlSetData(
            intersection_count=pos_hits,
            controls_count=pos_total,
        ),
        negative=ControlSetData(
            intersection_count=neg_hits,
            controls_count=neg_total,
        ),
        target=ControlTargetData(estimated_size=estimated_size),
    )


# ---------------------------------------------------------------------------
# _enrich_step_evals_with_movement
# ---------------------------------------------------------------------------


class TestEnrichStepEvalsWithMovement:
    def test_movement_fields_calculated(self) -> None:
        baseline = _baseline_result(pos_hits=8, pos_total=10, neg_hits=3)
        # baseline: TP=8, FP=3, FN=10-8=2
        step_evals = [
            _make_step_evaluation(
                counts=_StepEvalCounts(pos_hits=6, pos_total=10, neg_hits=4)
            )
        ]
        enriched = _enrich_step_evals_with_movement(step_evals, baseline)

        assert len(enriched) == 1
        ev = enriched[0]
        # step TP=6, baseline TP=8  => tp_movement = 6-8 = -2
        assert ev.tp_movement == -2
        # step FP=4, baseline FP=3  => fp_movement = 4-3 = 1
        assert ev.fp_movement == 1
        # step FN=10-6=4, baseline FN=10-8=2 => fn_movement = 4-2 = 2
        assert ev.fn_movement == 2

    def test_preserves_other_fields(self) -> None:
        baseline = _baseline_result()
        step_evals = [_make_step_evaluation(step_id="s42", recall=0.75)]
        enriched = _enrich_step_evals_with_movement(step_evals, baseline)

        assert enriched[0].step_id == "s42"
        assert enriched[0].recall == 0.75
        assert enriched[0].search_name == "Search_s42"

    def test_multiple_step_evals(self) -> None:
        baseline = _baseline_result(pos_hits=5, pos_total=10, neg_hits=2)
        step_evals = [
            _make_step_evaluation(
                step_id="s1",
                counts=_StepEvalCounts(pos_hits=5, pos_total=10, neg_hits=2),
            ),
            _make_step_evaluation(
                step_id="s2",
                counts=_StepEvalCounts(pos_hits=3, pos_total=10, neg_hits=1),
            ),
        ]
        enriched = _enrich_step_evals_with_movement(step_evals, baseline)
        assert len(enriched) == 2

        # s1 matches baseline, so movement should be 0
        assert enriched[0].tp_movement == 0
        assert enriched[0].fp_movement == 0
        assert enriched[0].fn_movement == 0

        # s2: TP=3 vs 5, FP=1 vs 2, FN=7 vs 5
        assert enriched[1].tp_movement == -2
        assert enriched[1].fp_movement == -1
        assert enriched[1].fn_movement == 2

    def test_empty_step_evals(self) -> None:
        result = _enrich_step_evals_with_movement([], _baseline_result())
        assert result == []

    def test_empty_baseline(self) -> None:
        """When baseline has no controls data, baseline counts are all 0."""
        step_evals = [
            _make_step_evaluation(counts=_StepEvalCounts(pos_hits=5, neg_hits=2))
        ]
        enriched = _enrich_step_evals_with_movement(step_evals, ControlTestResult())
        # baseline TP=0, FP=0, FN=0-0=0
        ev = enriched[0]
        assert ev.tp_movement == 5
        assert ev.fp_movement == 2
        assert ev.fn_movement == 5  # step FN = 10-5=5, baseline FN = 0


# ---------------------------------------------------------------------------
# _enrich_contributions_with_narrative
# ---------------------------------------------------------------------------


class TestEnrichContributionsWithNarrative:
    def _make_contribution(
        self,
        recall_delta: float = 0.0,
        fpr_delta: float = 0.0,
        verdict: str = "neutral",
    ) -> StepContribution:
        return StepContribution(
            step_id="s1",
            search_name="Search_s1",
            baseline_recall=0.8,
            ablated_recall=0.8 + recall_delta,
            recall_delta=recall_delta,
            baseline_fpr=0.1,
            ablated_fpr=0.1 + fpr_delta,
            fpr_delta=fpr_delta,
            verdict=verdict,
        )

    def test_neutral_minimal_impact(self) -> None:
        """recall_delta and fpr_delta are both small -> 'minimal impact'."""
        sc = self._make_contribution(recall_delta=0.0, fpr_delta=0.0, verdict="neutral")
        [enriched] = _enrich_contributions_with_narrative([sc])
        assert "minimal impact" in enriched.narrative

    def test_essential_verdict_narrative(self) -> None:
        """Small deltas but essential verdict -> 'critical'."""
        sc = self._make_contribution(
            recall_delta=0.0, fpr_delta=0.0, verdict="essential"
        )
        [enriched] = _enrich_contributions_with_narrative([sc])
        assert "critical" in enriched.narrative.lower()

    def test_large_recall_drop_narrative(self) -> None:
        """Large negative recall_delta produces 'drops recall' message."""
        sc = self._make_contribution(recall_delta=-0.15, verdict="essential")
        [enriched] = _enrich_contributions_with_narrative([sc])
        assert "drops recall" in enriched.narrative.lower()

    def test_recall_improvement_narrative(self) -> None:
        """Positive recall_delta > 0.02 produces 'improves recall'."""
        sc = self._make_contribution(recall_delta=0.05, verdict="neutral")
        [enriched] = _enrich_contributions_with_narrative([sc])
        assert "improves recall" in enriched.narrative.lower()

    def test_fpr_increase_narrative(self) -> None:
        """Large fpr_delta produces 'increases false positive rate'."""
        sc = self._make_contribution(
            recall_delta=-0.10, fpr_delta=0.10, verdict="harmful"
        )
        [enriched] = _enrich_contributions_with_narrative([sc])
        assert "false positive rate" in enriched.narrative.lower()

    def test_fpr_decrease_narrative(self) -> None:
        """Negative fpr_delta produces 'reduces false positive rate'."""
        sc = self._make_contribution(
            recall_delta=-0.10, fpr_delta=-0.10, verdict="helpful"
        )
        [enriched] = _enrich_contributions_with_narrative([sc])
        assert "reduces false positive rate" in enriched.narrative.lower()

    def test_unknown_verdict_narrative(self) -> None:
        """Verdict that isn't 'neutral' or 'essential' with small deltas."""
        sc = self._make_contribution(recall_delta=0.0, fpr_delta=0.0, verdict="helpful")
        [enriched] = _enrich_contributions_with_narrative([sc])
        assert "helpful" in enriched.narrative.lower()

    def test_multiple_contributions(self) -> None:
        scs = [
            self._make_contribution(recall_delta=-0.20, verdict="essential"),
            self._make_contribution(recall_delta=0.0, verdict="neutral"),
        ]
        enriched = _enrich_contributions_with_narrative(scs)
        assert len(enriched) == 2
        assert "drops recall" in enriched[0].narrative.lower()
        assert "minimal impact" in enriched[1].narrative.lower()

    def test_preserves_fields(self) -> None:
        sc = self._make_contribution()
        [enriched] = _enrich_contributions_with_narrative([sc])
        assert enriched.step_id == "s1"
        assert enriched.search_name == "Search_s1"
        assert enriched.baseline_recall == 0.8
        assert enriched.verdict == "neutral"

    def test_empty_list(self) -> None:
        assert _enrich_contributions_with_narrative([]) == []
