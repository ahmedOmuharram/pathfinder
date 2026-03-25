"""VCR-backed integration tests for StrategyAPI step/strategy CRUD.

Record:
    WDK_AUTH_EMAIL=<email> WDK_AUTH_PASSWORD=<pw> \
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_steps.py -v --record-mode=all

Replay:
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_steps.py -v
"""

import pytest

from veupath_chatbot.integrations.veupathdb.strategy_api import (
    PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX,
    StrategyAPI,
)
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    WDKSearchConfig,
    WDKStepTree,
)
from veupath_chatbot.tests.conftest import discover_organism


class TestStrategyAPI:
    """Tests for StrategyAPI using real WDK calls backed by VCR cassettes."""

    @pytest.mark.vcr
    async def test_create_step(self, wdk_api: StrategyAPI) -> None:
        organism_param = await discover_organism(wdk_api)

        result = await wdk_api.create_step(
            NewStepSpec(
                search_name="GenesByTaxon",
                search_config=WDKSearchConfig(parameters={"organism": organism_param}),
                custom_name="Taxon Step",
            ),
            record_type="transcript",
        )

        assert result.id > 0

    @pytest.mark.vcr
    async def test_create_combined_step(self, wdk_api: StrategyAPI) -> None:
        organism_param = await discover_organism(wdk_api)

        step_a = await wdk_api.create_step(
            NewStepSpec(
                search_name="GenesByTaxon",
                search_config=WDKSearchConfig(parameters={"organism": organism_param}),
                custom_name="Step A",
            ),
            record_type="transcript",
        )
        step_b = await wdk_api.create_step(
            NewStepSpec(
                search_name="GenesByTaxon",
                search_config=WDKSearchConfig(parameters={"organism": organism_param}),
                custom_name="Step B",
            ),
            record_type="transcript",
        )

        result = await wdk_api.create_combined_step(
            primary_step_id=step_a.id,
            secondary_step_id=step_b.id,
            boolean_operator="INTERSECT",
            record_type="transcript",
        )

        assert result.id > 0
        assert result.id != step_a.id
        assert result.id != step_b.id

    @pytest.mark.vcr
    async def test_create_strategy(self, wdk_api: StrategyAPI) -> None:
        organism_param = await discover_organism(wdk_api)

        step = await wdk_api.create_step(
            NewStepSpec(
                search_name="GenesByTaxon",
                search_config=WDKSearchConfig(parameters={"organism": organism_param}),
                custom_name="Strategy Root",
            ),
            record_type="transcript",
        )

        tree = WDKStepTree(step_id=step.id)
        result = await wdk_api.create_strategy(
            step_tree=tree, name="Test Strategy", is_saved=False,
        )

        assert result.id > 0
        await wdk_api.delete_strategy(result.id)

    @pytest.mark.vcr
    async def test_create_internal_strategy(self, wdk_api: StrategyAPI) -> None:
        organism_param = await discover_organism(wdk_api)

        step = await wdk_api.create_step(
            NewStepSpec(
                search_name="GenesByTaxon",
                search_config=WDKSearchConfig(parameters={"organism": organism_param}),
                custom_name="Internal Step",
            ),
            record_type="transcript",
        )

        tree = WDKStepTree(step_id=step.id)
        result = await wdk_api.create_strategy(
            step_tree=tree, name="Pathfinder step counts", is_internal=True,
        )

        assert result.id > 0

        strategy = await wdk_api.get_strategy(result.id)
        assert strategy.name.startswith(PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX)
        assert strategy.is_saved is False
        assert strategy.is_public is False

        await wdk_api.delete_strategy(result.id)
