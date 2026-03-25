"""VCR-backed integration test for ensure_single_output combine chain.

Reproduces the bug where _chain_combines reads ``stepId`` from the
create_step response, but the response uses ``id``.  After the first
combine succeeds, ``current`` is never updated, so the second combine
tries to reuse the now-consumed root — and fails.

Record:
    WDK_AUTH_EMAIL=<email> WDK_AUTH_PASSWORD=<pw> \
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_ensure_single_output.py -v --record-mode=all

Replay:
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_ensure_single_output.py -v
"""

import pytest

from veupath_chatbot.ai.tools.strategy_tools.operations import StrategyTools
from veupath_chatbot.domain.strategy.session import StrategySession
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.tests.conftest import discover_organism


class TestEnsureSingleOutput:
    """Integration test: ensure_single_output chains combines correctly."""

    @pytest.mark.vcr
    async def test_chain_combines_four_roots(
        self,
        wdk_api: StrategyAPI,
        wdk_test_site: tuple[str, str],
    ) -> None:
        """Four leaf steps → ensure_single_output → single root on first call.

        This is the exact scenario from the eval run: the AI creates
        multiple leaf steps, then calls ensure_single_output.  Before the
        fix, _chain_combines failed on its second iteration because
        ``current`` was never updated (``stepId`` vs ``id`` key mismatch).
        """
        site_id, _ = wdk_test_site
        organism_param = await discover_organism(wdk_api)

        session = StrategySession(site_id)
        tools = StrategyTools(session)
        graph = session.create_graph("test-ensure-single-output")

        # Create 4 leaf steps.
        for _ in range(4):
            result = await tools.create_step(
                search_name="GenesByTaxon",
                parameters={"organism": organism_param},
                record_type="transcript",
                graph_id=graph.id,
            )
            assert "id" in result, f"create_step failed: {result}"

        # Verify 4 roots.
        validation = await tools.validate_graph_structure(graph_id=graph.id)
        assert validation.root_count == 4
        assert validation.ok is False

        # THE TEST: ensure_single_output must succeed on the FIRST call.
        result = await tools.ensure_single_output(
            graph_id=graph.id, operator="INTERSECT"
        )

        assert result.get("ok") is True, (
            f"ensure_single_output failed: {result}"
        )
        assert len(result.get("rootStepIds", [])) == 1

    @pytest.mark.vcr
    async def test_chain_combines_five_roots(
        self,
        wdk_api: StrategyAPI,
        wdk_test_site: tuple[str, str],
    ) -> None:
        """Five leaf steps — mirrors the eval run exactly."""
        site_id, _ = wdk_test_site
        organism_param = await discover_organism(wdk_api)

        session = StrategySession(site_id)
        tools = StrategyTools(session)
        graph = session.create_graph("test-five-roots")

        for _ in range(5):
            result = await tools.create_step(
                search_name="GenesByTaxon",
                parameters={"organism": organism_param},
                record_type="transcript",
                graph_id=graph.id,
            )
            assert "id" in result, f"create_step failed: {result}"

        validation = await tools.validate_graph_structure(graph_id=graph.id)
        assert validation.root_count == 5

        result = await tools.ensure_single_output(
            graph_id=graph.id, operator="INTERSECT"
        )

        assert result.get("ok") is True, (
            f"ensure_single_output failed: {result}"
        )
        assert len(result.get("rootStepIds", [])) == 1
