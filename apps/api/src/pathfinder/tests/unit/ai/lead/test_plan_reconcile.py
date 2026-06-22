"""Deterministic plan reconciliation: when discovery selects a search with a
``replaces`` link, the matching plan leaf is rewritten to the new search with
params filled from the resolved snapshot — topology untouched, no LLM editing.
This is what makes a denial→swap robust regardless of model (the conv D/E/F
failure where the Lead couldn't reliably apply the GO swap).
"""

from __future__ import annotations

from pathfinder.ai.agents.state import (
    ParamVocabSnapshot,
    SearchOverview,
)
from pathfinder.ai.lead.plan_reconcile import reconcile_plan_with_replacements
from pathfinder.domain.parameters.values import MultiPickValue, SinglePickValue
from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.domain.strategy.plan import (
    ParamStatus,
    PlannedConnection,
    PlannedParameter,
    PlannedStep,
    StepStatus,
    StepType,
    StrategyPlan,
)


def _interpro_leaf() -> PlannedStep:
    return PlannedStep(
        id="s1",
        search_name="GenesByInterproDomain",
        display_name="InterPro kinase",
        step_type=StepType.LEAF,
        status=StepStatus.READY,
        parameters=[
            PlannedParameter(
                name="organism",
                display_name="organism",
                param_type="multi-pick-vocabulary",
                value=MultiPickValue(values=["Plasmodium"]),
                status=ParamStatus.SET,
                required=True,
            ),
            PlannedParameter(
                name="domain_database",
                display_name="domain_database",
                param_type="single-pick-vocabulary",
                value=SinglePickValue(value="PFAM"),
                status=ParamStatus.SET,
                required=True,
            ),
        ],
    )


def _signal_leaf() -> PlannedStep:
    return PlannedStep(
        id="s2",
        search_name="GenesWithSignalPeptide",
        display_name="Signal peptide",
        step_type=StepType.LEAF,
        status=StepStatus.READY,
        parameters=[
            PlannedParameter(
                name="organism",
                display_name="organism",
                param_type="multi-pick-vocabulary",
                value=MultiPickValue(values=["Plasmodium"]),
                status=ParamStatus.SET,
                required=True,
            ),
        ],
    )


def _combine() -> PlannedStep:
    return PlannedStep(
        id="c1",
        search_name="__combine__",
        display_name="Combine",
        step_type=StepType.COMBINE,
        status=StepStatus.READY,
        operator="INTERSECT",
        left_id="s1",
        right_id="s2",
    )


def _plan() -> StrategyPlan:
    return StrategyPlan(
        title="kinases with signal peptide",
        description="d",
        rationale="r",
        steps=[_interpro_leaf(), _signal_leaf(), _combine()],
        connections=[
            PlannedConnection(from_step="s1", to_step="c1", input_type="primary"),
            PlannedConnection(from_step="s2", to_step="c1", input_type="secondary"),
        ],
    )


def _go_overview() -> SearchOverview:
    ov = SearchOverview(
        search_name="GenesByGoTerm",
        display_name="GO term",
        record_type="transcript",
        description="",
        parameter_names=["organism", "go_typeahead", "go_term", "go_term_evidence"],
        required_params=["organism", "go_term", "go_term_evidence"],
        selection_status="selected",
        replaces="GenesByInterproDomain",
        param_hints={
            "organism": ["Plasmodium"],
            "go_typeahead": ["GO:0016301"],
            "go_term": "N/A",
            "go_term_evidence": ["Curated", "Computed"],
        },
    )
    return ov.model_copy(
        update={
            "param_vocab": {
                "organism": ParamVocabSnapshot(
                    param_type="multi-pick-vocabulary", required=True
                ),
                "go_term": ParamVocabSnapshot(
                    param_type="string", required=True, default_value="N/A"
                ),
                "go_term_evidence": ParamVocabSnapshot(
                    param_type="multi-pick-vocabulary",
                    required=True,
                    allowed_values=[
                        VocabOption(value="Curated", display="Curated"),
                        VocabOption(value="Computed", display="Computed"),
                    ],
                ),
                "go_typeahead": ParamVocabSnapshot(
                    param_type="multi-pick-vocabulary", required=False
                ),
            },
        },
    )


def _discovered() -> dict[str, SearchOverview]:
    return {
        "GenesByGoTerm": _go_overview(),
        "GenesWithSignalPeptide": SearchOverview(
            search_name="GenesWithSignalPeptide",
            display_name="Signal peptide",
            record_type="transcript",
            description="",
            parameter_names=["organism"],
            required_params=["organism"],
            selection_status="selected",
        ),
    }


def test_reconcile_swaps_replaced_leaf_to_new_search() -> None:
    result = reconcile_plan_with_replacements(_plan(), _discovered())
    by_id = {s.id: s for s in result.plan.steps}
    assert by_id["s1"].search_name == "GenesByGoTerm"
    assert result.changes  # a change was recorded


def test_reconcile_fills_params_from_hints_and_drops_stale() -> None:
    result = reconcile_plan_with_replacements(_plan(), _discovered())
    s1 = next(s for s in result.plan.steps if s.id == "s1")
    names = {p.name for p in s1.parameters}
    assert "domain_database" not in names  # stale InterPro param gone
    ev = next(p for p in s1.parameters if p.name == "go_term_evidence")
    assert ev.value == MultiPickValue(values=["Curated", "Computed"])
    assert ev.status == ParamStatus.SET


def test_reconcile_leaves_topology_and_other_leaves_untouched() -> None:
    result = reconcile_plan_with_replacements(_plan(), _discovered())
    by_id = {s.id: s for s in result.plan.steps}
    assert by_id["s2"].search_name == "GenesWithSignalPeptide"
    combine = by_id["c1"]
    assert combine.operator == "INTERSECT"
    assert combine.left_id == "s1"
    assert combine.right_id == "s2"
    assert len(result.plan.connections) == 2


def test_reconcile_noop_without_replaces_link() -> None:
    discovered = {
        "GenesByGoTerm": _go_overview().model_copy(update={"replaces": None}),
    }
    result = reconcile_plan_with_replacements(_plan(), discovered)
    assert result.changes == []
    assert next(s for s in result.plan.steps if s.id == "s1").search_name == (
        "GenesByInterproDomain"
    )


def test_reconcile_noop_when_replaced_search_not_in_plan() -> None:
    ov = _go_overview().model_copy(update={"replaces": "GenesBySomethingElse"})
    result = reconcile_plan_with_replacements(_plan(), {"GenesByGoTerm": ov})
    assert result.changes == []


def _discovered_reject_select() -> dict[str, SearchOverview]:
    """The reliable pattern a weak model actually produces: it REJECTS the old
    search and SELECTS the new one, without setting an explicit replaces link."""
    go = _go_overview().model_copy(update={"replaces": None})
    return {
        "GenesByGoTerm": go,
        "GenesByInterproDomain": SearchOverview(
            search_name="GenesByInterproDomain",
            display_name="InterPro",
            record_type="transcript",
            description="",
            parameter_names=["organism"],
            required_params=["organism"],
            selection_status="rejected",
        ),
        "GenesWithSignalPeptide": SearchOverview(
            search_name="GenesWithSignalPeptide",
            display_name="Signal peptide",
            record_type="transcript",
            description="",
            parameter_names=["organism"],
            required_params=["organism"],
            selection_status="selected",
        ),
    }


def test_reconcile_infers_swap_from_reject_plus_new_selection() -> None:
    """With inference on, a single orphaned leaf (its search now rejected) and a
    single new selection map 1:1 — no explicit replaces link needed."""
    result = reconcile_plan_with_replacements(
        _plan(), _discovered_reject_select(), infer_replacements=True
    )
    s1 = next(s for s in result.plan.steps if s.id == "s1")
    assert s1.search_name == "GenesByGoTerm"
    assert result.changes


def test_reconcile_inference_off_by_default() -> None:
    """Without infer_replacements, only explicit replaces links act (safe
    default for non-targeted discovery)."""
    result = reconcile_plan_with_replacements(_plan(), _discovered_reject_select())
    assert result.changes == []


def test_reconcile_supersedes_directs_swap_without_signals() -> None:
    """The Lead's denial classification: supersedes names the plan search to
    replace. Even with the old search still 'selected' and no replaces link
    (the conv-H case), the single new selection swaps into that leaf."""
    discovered = {
        "GenesByGoTerm": _go_overview().model_copy(update={"replaces": None}),
        "GenesByInterproDomain": SearchOverview(
            search_name="GenesByInterproDomain",
            display_name="InterPro",
            record_type="transcript",
            description="",
            parameter_names=["organism"],
            required_params=["organism"],
            selection_status="selected",  # still selected — no reject signal
        ),
        "GenesWithSignalPeptide": SearchOverview(
            search_name="GenesWithSignalPeptide",
            display_name="Signal peptide",
            record_type="transcript",
            description="",
            parameter_names=["organism"],
            required_params=["organism"],
            selection_status="selected",
        ),
    }
    result = reconcile_plan_with_replacements(
        _plan(), discovered, supersedes="GenesByInterproDomain"
    )
    s1 = next(s for s in result.plan.steps if s.id == "s1")
    assert s1.search_name == "GenesByGoTerm"
    assert result.changes


def test_reconcile_supersedes_noop_when_not_a_plan_leaf() -> None:
    discovered = {"GenesByGoTerm": _go_overview().model_copy(update={"replaces": None})}
    result = reconcile_plan_with_replacements(
        _plan(), discovered, supersedes="GenesByText"
    )
    assert result.changes == []


def test_reconcile_supersedes_ambiguous_two_candidates() -> None:
    discovered = {
        "GenesByGoTerm": _go_overview().model_copy(update={"replaces": None}),
        "GenesByText": SearchOverview(
            search_name="GenesByText",
            display_name="Text",
            record_type="transcript",
            description="",
            parameter_names=["organism"],
            required_params=["organism"],
            selection_status="selected",
        ),
    }
    result = reconcile_plan_with_replacements(
        _plan(), discovered, supersedes="GenesByInterproDomain"
    )
    assert result.changes == []


def test_reconcile_no_inference_when_ambiguous() -> None:
    """Two new selections → ambiguous mapping → no inference (don't guess)."""
    discovered = _discovered_reject_select()
    discovered["GenesByText"] = SearchOverview(
        search_name="GenesByText",
        display_name="Text",
        record_type="transcript",
        description="",
        parameter_names=["organism"],
        required_params=["organism"],
        selection_status="selected",
    )
    result = reconcile_plan_with_replacements(
        _plan(), discovered, infer_replacements=True
    )
    assert result.changes == []
