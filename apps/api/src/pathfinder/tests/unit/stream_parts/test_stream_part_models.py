"""Tests for typed stream-part payload models."""

import pytest
from pydantic import ValidationError
from shared_py.stream_parts.gene_set import GeneSet
from shared_py.stream_parts.graph import GraphEdge, GraphNode, GraphSnapshot
from shared_py.stream_parts.optimization import OptimizationSnapshot
from shared_py.stream_parts.phase import PhaseChange
from shared_py.stream_parts.plan import (
    DecisionPresented,
    PlanArtifact,
    PlannedStep,
    PlanUpdate,
)
from shared_py.stream_parts.problem_frame import ProblemFrame
from shared_py.stream_parts.strategy import (
    StrategyLink,
    StrategyMeta,
    StrategyPatch,
)


def test_graph_snapshot_validates_required_fields():
    snapshot = GraphSnapshot(
        strategy_id="s_abc123",
        gene_count=87,
        nodes=[
            GraphNode(
                id="n1",
                search_name="GenesByOrthologPattern",
                estimated_size=342,
            )
        ],
        edges=[GraphEdge(source="n1", target="n2", operator="INTERSECT")],
    )
    assert snapshot.strategy_id == "s_abc123"
    assert snapshot.gene_count == 87
    assert len(snapshot.nodes) == 1


def test_graph_snapshot_rejects_missing_strategy_id():
    with pytest.raises(ValidationError):
        GraphSnapshot(gene_count=0, nodes=[], edges=[])


def test_graph_snapshot_rejects_negative_gene_count():
    with pytest.raises(ValidationError):
        GraphSnapshot(strategy_id="s_x", gene_count=-1, nodes=[], edges=[])


def test_strategy_patch_validates_add_step():
    patch = StrategyPatch(
        strategy_id="s_x",
        operation="add_step",
        step={"id": "step_1", "searchName": "ByText", "parameters": {}},
    )
    assert patch.operation == "add_step"


def test_strategy_patch_rejects_unknown_operation():
    with pytest.raises(ValidationError):
        StrategyPatch(strategy_id="s_x", operation="teleport_step")


def test_strategy_meta_validates():
    meta = StrategyMeta(
        strategy_id="s_x",
        name="My strategy",
        is_saved=False,
        estimated_size=42,
        record_class_name="transcript",
    )
    assert meta.name == "My strategy"


def test_strategy_link_validates():
    link = StrategyLink(
        strategy_id="s_x",
        url="https://plasmodb.org/plasmo/app/record/dataset/s_x",
        title="My strategy",
    )
    assert link.url.startswith("https://")


def test_plan_artifact_validates():
    art = PlanArtifact(
        plan_id="p_x",
        steps=[
            PlannedStep(
                order=0, search_name="ByText", rationale="filter by term"
            )
        ],
        rationale="three-step funnel",
    )
    assert len(art.steps) == 1


def test_plan_update_validates():
    upd = PlanUpdate(plan_id="p_x", status="revised", reason="swapped step 2")
    assert upd.status == "revised"


def test_decision_presented_validates():
    dec = DecisionPresented(
        decision_type="pick_strategy_variant",
        options=[
            {"id": "a", "label": "Variant A"},
            {"id": "b", "label": "Variant B"},
        ],
        rationale="two plausible paths",
    )
    assert len(dec.options) == 2


def test_problem_frame_validates():
    pf = ProblemFrame(
        site_id="plasmodb",
        user_goal="find drug targets for PfATP4",
        interpreted_goal="identify essential plasmodium genes related to ATP4",
        biological_entities=["PfATP4"],
        ready_for_wdk_discovery=True,
        confidence=0.9,
    )
    assert pf.site_id == "plasmodb"
    assert pf.biological_entities == ["PfATP4"]
    assert pf.ready_for_wdk_discovery is True


def test_gene_set_validates():
    gs = GeneSet(
        gene_set_id="gs_1",
        name="exported-proteins",
        gene_count=87,
        site_id="plasmodb",
    )
    assert gs.gene_count == 87


def test_optimization_snapshot_validates():
    snap = OptimizationSnapshot(
        trial_index=14,
        total_trials=100,
        best_score=0.82,
        current_score=0.78,
        is_pareto=False,
    )
    assert snap.trial_index == 14


def test_phase_change_validates():
    pc = PhaseChange(
        phase="discovery",
        status="started",
        duration_ms=None,
    )
    assert pc.phase == "discovery"


# ── Wire-contract tests ─────────────────────────────────────────────────────
# These lock the camelCase alias behavior, snake_case acceptance via
# populate_by_name, and extra-field tolerance. Without them, a flip of
# alias_generator or extra="ignore" in CamelModel passes all the field-validation
# tests above but silently breaks the frontend contract.


def test_camel_model_accepts_camel_case_input():
    snapshot = GraphSnapshot.model_validate(
        {
            "strategyId": "s_abc",
            "geneCount": 42,
            "nodes": [{"id": "n1", "searchName": "ByText", "estimatedSize": 10}],
            "edges": [{"source": "n1", "target": "n2", "operator": "INTERSECT"}],
        }
    )
    assert snapshot.strategy_id == "s_abc"
    assert snapshot.gene_count == 42
    assert snapshot.nodes[0].search_name == "ByText"


def test_camel_model_accepts_snake_case_input_via_populate_by_name():
    snapshot = GraphSnapshot.model_validate(
        {
            "strategy_id": "s_abc",
            "gene_count": 42,
            "nodes": [],
            "edges": [],
        }
    )
    assert snapshot.strategy_id == "s_abc"


def test_camel_model_emits_camel_case_on_by_alias_dump():
    snapshot = GraphSnapshot(
        strategy_id="s_abc",
        gene_count=42,
        nodes=[GraphNode(id="n1", search_name="ByText", estimated_size=10)],
        edges=[GraphEdge(source="n1", target="n2", operator="INTERSECT")],
    )
    dumped = snapshot.model_dump(by_alias=True)
    assert "strategyId" in dumped
    assert "geneCount" in dumped
    assert "strategy_id" not in dumped
    assert "searchName" in dumped["nodes"][0]


def test_camel_model_ignores_extra_fields():
    # `extra="ignore"` on CamelModel means protocol additions from newer servers
    # don't crash old clients. Unknown fields are dropped silently.
    snapshot = GraphSnapshot.model_validate(
        {
            "strategyId": "s_abc",
            "geneCount": 0,
            "nodes": [],
            "edges": [],
            "futureField": "should be dropped",
            "anotherExtra": 12345,
        }
    )
    assert snapshot.strategy_id == "s_abc"
    # Confirm the extras aren't smuggled through
    dumped = snapshot.model_dump(by_alias=True)
    assert "futureField" not in dumped
    assert "anotherExtra" not in dumped


def test_graph_edge_operator_accepts_all_seven_wdk_operators():
    """GraphEdge.operator must match WDK's full BooleanOperator set."""
    for op in ("INTERSECT", "UNION", "MINUS", "RMINUS", "LONLY", "RONLY", "COLOCATE"):
        edge = GraphEdge(source="a", target="b", operator=op)
        assert edge.operator == op


def test_graph_edge_operator_rejects_unknown_operator():
    with pytest.raises(ValidationError):
        GraphEdge(source="a", target="b", operator="TELEPORT")
