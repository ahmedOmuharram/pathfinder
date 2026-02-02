"""Tests for strategy DSL AST serialization."""

from veupath_chatbot.domain.strategy.ast import (
    SearchStep,
    CombineStep,
    TransformStep,
    StrategyAST,
    StepAnalysis,
    StepFilter,
    StepReport,
    from_dict,
)
from veupath_chatbot.domain.strategy.ops import CombineOp


def test_step_attachments_round_trip():
    """Ensure filters, analyses, and reports serialize in plans."""
    search = SearchStep(
        record_type="gene",
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
    transform = TransformStep(
        transform_name="GenesByOrthology",
        input=search,
        parameters={"taxon": "Toxoplasma"},
        filters=[StepFilter(name="score", value=0.8)],
    )
    combine = CombineStep(
        op=CombineOp.INTERSECT,
        left=search,
        right=transform,
        reports=[StepReport(report_name="fullRecord", config={"format": "json"})],
    )
    strategy = StrategyAST(record_type="gene", root=combine, name="Test")

    payload = strategy.to_dict()
    parsed = from_dict(payload)

    root = parsed.root
    assert isinstance(root, CombineStep)
    assert root.reports and root.reports[0].report_name == "fullRecord"
    assert isinstance(root.left, SearchStep)
    assert root.left.filters[0].name == "ranked"
    assert root.left.analyses[0].analysis_type == "enrichment"
    assert isinstance(root.right, TransformStep)
    assert root.right.filters[0].name == "score"
