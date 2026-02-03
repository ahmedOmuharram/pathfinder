"""Tests for strategy DSL AST serialization."""

from veupath_chatbot.domain.strategy.ast import (
    PlanStepNode,
    StrategyAST,
    StepAnalysis,
    StepFilter,
    StepReport,
    from_dict,
)
from veupath_chatbot.domain.strategy.ops import CombineOp


def test_step_attachments_round_trip():
    """Ensure filters, analyses, and reports serialize in plans."""
    search = PlanStepNode(
        search_name="GenesByTextSearch",
        parameters={"text": "kinase"},
        filters=[StepFilter(name="ranked", value={"min": 5})],
        analyses=[
            StepAnalysis(
                analysis_type="enrichment",
                parameters={"dataset": "GO"},
                custom_name="GO enrichment",
            )
        ],
        reports=[StepReport(report_name="standard", config={"attributes": ["gene_id"]})],
    )
    transform = PlanStepNode(
        search_name="GenesByOrthology",
        primary_input=search,
        parameters={"taxon": "Toxoplasma"},
        filters=[StepFilter(name="score", value=0.8)],
    )
    combine = PlanStepNode(
        search_name="boolean_question_gene",
        operator=CombineOp.INTERSECT,
        primary_input=search,
        secondary_input=transform,
        reports=[StepReport(report_name="fullRecord", config={"format": "json"})],
    )
    strategy = StrategyAST(record_type="gene", root=combine, name="Test")

    payload = strategy.to_dict()
    parsed = from_dict(payload)

    root = parsed.root
    assert root.infer_kind() == "combine"
    assert root.reports and root.reports[0].report_name == "fullRecord"
    assert root.primary_input is not None
    assert root.primary_input.infer_kind() == "search"
    assert root.primary_input.filters[0].name == "ranked"
    assert root.primary_input.analyses[0].analysis_type == "enrichment"
    assert root.secondary_input is not None
    assert root.secondary_input.infer_kind() == "transform"
    assert root.secondary_input.filters[0].name == "score"
