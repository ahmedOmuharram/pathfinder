"""Fixture-shape drift tests: verify Pathfinder parsing against realistic WDK payloads.

Uses the pre-recorded WDK responses from tests/fixtures/wdk_responses.py
(verified against live PlasmoDB API) to ensure Pathfinder's parsing code
handles real WDK shapes correctly.

Unlike unit tests that use hand-built dicts, these tests use the SAME
fixtures that integration tests use — so drift between fixture assumptions
and parser expectations is caught.

WDK contracts validated:
- strategy_get_response → build_snapshot_from_wdk produces valid AST
- standard_report_response → WDKAnswer.model_validate succeeds
- search_details_response → WDKSearchResponse.model_validate succeeds
- strategy step tree recursion handles 3-step chain
"""

import pytest

from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKAnswer,
    WDKSearchResponse,
    WDKStrategyDetails,
)
from veupath_chatbot.services.strategies.wdk_conversion import (
    build_snapshot_from_wdk,
)
from veupath_chatbot.tests.fixtures.wdk_responses import (
    DEFAULT_GENE_IDS,
    search_details_response,
    standard_report_response,
    strategy_get_response,
    wdk_answer_json,
)

# ── strategy_get_response → build_snapshot_from_wdk ───────────────


class TestStrategyFixtureRoundTrip:
    """Verify realistic strategy fixture parses into valid AST."""

    def test_three_step_strategy_parses(self) -> None:
        """strategy_get_response (3 steps) → build_snapshot_from_wdk succeeds."""
        raw = strategy_get_response(strategy_id=200, step_ids=[100, 101, 102])
        wdk = WDKStrategyDetails.model_validate(raw)
        ast, steps_data, step_counts = build_snapshot_from_wdk(wdk)

        # AST structure
        assert ast.record_type is not None
        assert ast.root is not None
        assert ast.root.search_name is not None

        # Steps data extracted
        assert len(steps_data) >= 1

        # Step counts from estimatedSize
        for step_id_str, count in step_counts.items():
            assert isinstance(count, int), (
                f"Step count for {step_id_str} should be int, got {type(count)}"
            )

    def test_single_step_strategy(self) -> None:
        raw = strategy_get_response(strategy_id=100, step_ids=[100])
        wdk = WDKStrategyDetails.model_validate(raw)
        ast, steps_data, _step_counts = build_snapshot_from_wdk(wdk)

        assert ast.root.search_name is not None
        assert len(steps_data) == 1


# ── standard_report_response → WDKAnswer ──────────────────────────


class TestReportFixtureRoundTrip:
    """Verify realistic report fixture parses into WDKAnswer."""

    def test_standard_report_validates(self) -> None:
        raw = standard_report_response()
        answer = WDKAnswer.model_validate(raw)
        assert answer.meta.total_count > 0
        assert len(answer.records) > 0

    def test_gene_ids_are_real_pf_ids(self) -> None:
        """Fixture gene IDs must be real Pf3D7 locus tags."""
        raw = standard_report_response()
        answer = WDKAnswer.model_validate(raw)
        for record in answer.records:
            # record is WDKRecordInstance; .id is list[dict[str, str]]
            assert len(record.id) > 0
            gene_source = None
            for pk in record.id:
                if pk.get("name") == "gene_source_id":
                    gene_source = pk.get("value")
            if gene_source:
                assert isinstance(gene_source, str)
                assert gene_source.startswith("PF3D7_"), (
                    f"Expected Pf3D7 locus tag, got {gene_source}"
                )

    def test_default_gene_ids_used(self) -> None:
        """Report fixture uses DEFAULT_GENE_IDS which are verified real."""
        raw = standard_report_response()
        answer = WDKAnswer.model_validate(raw)
        found_ids: set[str] = set()
        for record in answer.records:
            # record is WDKRecordInstance; .id is list[dict[str, str]]
            for pk in record.id:
                if pk.get("name") == "gene_source_id":
                    val = pk.get("value")
                    if isinstance(val, str):
                        found_ids.add(val)
        assert found_ids & set(DEFAULT_GENE_IDS), (
            "Report fixture should use DEFAULT_GENE_IDS"
        )

    def test_wdk_answer_json_validates(self) -> None:
        raw = wdk_answer_json(total_count=100, response_count=5)
        answer = WDKAnswer.model_validate(raw)
        assert answer.meta.total_count == 100


# ── search_details_response → WDKSearchResponse ──────────────────


class TestSearchDetailsFixtureRoundTrip:
    def test_taxon_search_validates(self) -> None:
        raw = search_details_response("GenesByTaxon")
        response = WDKSearchResponse.model_validate(raw)
        assert response.search_data.url_segment is not None
        assert response.validation.is_valid is True

    def test_text_search_validates(self) -> None:
        raw = search_details_response("GenesByTextSearch")
        response = WDKSearchResponse.model_validate(raw)
        assert response.search_data.url_segment is not None

    @pytest.mark.parametrize(
        "search_name",
        ["GenesByTaxon", "GenesByTextSearch"],
    )
    def test_search_has_parameters(self, search_name: str) -> None:
        """Expanded search details must include parameter specs."""
        raw = search_details_response(search_name)
        response = WDKSearchResponse.model_validate(raw)
        # Parameters should be non-empty for real searches
        assert response.search_data.parameters is not None
        assert len(response.search_data.parameters) > 0
