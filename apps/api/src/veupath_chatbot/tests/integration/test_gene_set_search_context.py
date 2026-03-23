"""Integration test: gene sets from WDK strategies carry correct search context.

Reproduces the critical bug where multi-step strategy params (bq_operator,
bq_left_op_...) leaked into gene sets and caused WDK 422 during evaluation.

Hits real WDK APIs — requires network access to plasmodb.org.

    pytest src/veupath_chatbot/tests/integration/test_gene_set_search_context.py -v -s
"""

from collections.abc import AsyncGenerator
from typing import cast
from uuid import uuid4

import pytest

from veupath_chatbot.domain.strategy.ast import StepTreeNode
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    WDKSearchConfig,
)
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.control_tests import (
    IntersectionConfig,
    run_positive_negative_controls,
)
from veupath_chatbot.services.gene_sets.operations import (
    GeneSetService,
    GeneSetWdkContext,
)
from veupath_chatbot.services.gene_sets.store import get_gene_set_store

pytestmark = pytest.mark.live_wdk

SITE = "plasmodb"
SEARCH = "GenesByTaxon"
SEARCH_PARAMS: dict[str, str] = {"organism": "Plasmodium falciparum 3D7"}
RECORD_TYPE = "transcript"
POSITIVE = ["PF3D7_0709000", "PF3D7_1343700", "PF3D7_0523000"]


@pytest.fixture(autouse=True)
async def _close_wdk_clients() -> AsyncGenerator[None]:
    yield
    try:
        router = get_site_router()
        await router.close_all()
    except RuntimeError, OSError:
        pass  # Client already closed or event loop torn down


class TestSingleStepGeneSet:
    """Single-step strategy → gene set with searchName + parameters."""

    @pytest.mark.asyncio
    async def test_gene_set_has_search_name_and_params(self) -> None:
        api = get_strategy_api(SITE)

        step = await api.create_step(
            NewStepSpec(
                search_name=SEARCH,
                search_config=WDKSearchConfig(parameters=SEARCH_PARAMS),
            ),
            record_type=RECORD_TYPE,
        )
        step_id = step.id
        assert isinstance(step_id, int)

        tree = StepTreeNode(step_id=step_id)
        strategy = await api.create_strategy(tree, name="Test Single")
        sid = strategy.id
        assert isinstance(sid, int)

        try:
            svc = GeneSetService(get_gene_set_store())
            gs = await svc.create(
                user_id=uuid4(),
                name="Single Step GS",
                site_id=SITE,
                gene_ids=[],
                source="strategy",
                wdk=GeneSetWdkContext(
                    wdk_strategy_id=sid,
                    record_type=RECORD_TYPE,
                ),
            )

            assert gs.search_name == SEARCH, f"Expected {SEARCH}, got {gs.search_name}"
            assert gs.parameters is not None, "parameters must be populated"
            assert "organism" in gs.parameters, (
                f"Missing 'organism', got {gs.parameters}"
            )
            assert gs.wdk_step_id == step_id
            assert len(gs.gene_ids) > 0, "Must fetch real gene IDs"
            assert gs.step_count == 1
        finally:
            await api.delete_strategy(sid)

    @pytest.mark.asyncio
    async def test_params_work_in_real_evaluation(self) -> None:
        """Use the extracted params in run_positive_negative_controls — must NOT 422."""
        api = get_strategy_api(SITE)

        step = await api.create_step(
            NewStepSpec(
                search_name=SEARCH,
                search_config=WDKSearchConfig(parameters=SEARCH_PARAMS),
            ),
            record_type=RECORD_TYPE,
        )
        tree = StepTreeNode(step_id=step.id)
        strategy = await api.create_strategy(tree, name="Eval Test")
        sid = strategy.id

        try:
            svc = GeneSetService(get_gene_set_store())
            gs = await svc.create(
                user_id=uuid4(),
                name="Eval GS",
                site_id=SITE,
                gene_ids=[],
                source="strategy",
                wdk=GeneSetWdkContext(
                    wdk_strategy_id=sid,
                    record_type=RECORD_TYPE,
                ),
            )

            assert gs.search_name is not None
            assert gs.parameters is not None

            # THE ACTUAL TEST: this must not throw a 422
            result = await run_positive_negative_controls(
                IntersectionConfig(
                    site_id=SITE,
                    record_type=RECORD_TYPE,
                    target_search_name=gs.search_name,
                    target_parameters=cast("JSONObject", gs.parameters),
                    controls_search_name="GeneByLocusTag",
                    controls_param_name="ds_gene_ids",
                ),
                positive_controls=POSITIVE,
            )

            assert result.positive is not None, "Positive result must not be None"
            assert result.positive.intersection_count is not None
        finally:
            await api.delete_strategy(sid)


class TestMultiStepGeneSet:
    """Multi-step strategy → gene set must NOT have boolean params."""

    @pytest.mark.asyncio
    async def test_no_boolean_params_leak(self) -> None:
        api = get_strategy_api(SITE)

        step1 = await api.create_step(
            NewStepSpec(
                search_name=SEARCH,
                search_config=WDKSearchConfig(parameters=SEARCH_PARAMS),
            ),
            record_type=RECORD_TYPE,
        )
        step2 = await api.create_step(
            NewStepSpec(
                search_name=SEARCH,
                search_config=WDKSearchConfig(parameters=SEARCH_PARAMS),
            ),
            record_type=RECORD_TYPE,
        )
        combined = await api.create_combined_step(
            step1.id,
            step2.id,
            "INTERSECT",
            RECORD_TYPE,
        )
        tree = StepTreeNode(
            step_id=combined.id,
            primary_input=StepTreeNode(step_id=step1.id),
            secondary_input=StepTreeNode(step_id=step2.id),
        )
        strategy = await api.create_strategy(tree, name="Test Multi")
        sid = strategy.id

        try:
            svc = GeneSetService(get_gene_set_store())
            gs = await svc.create(
                user_id=uuid4(),
                name="Multi Step GS",
                site_id=SITE,
                gene_ids=[],
                source="strategy",
                wdk=GeneSetWdkContext(
                    wdk_strategy_id=sid,
                    record_type=RECORD_TYPE,
                ),
            )

            # Must NOT have boolean params
            if gs.parameters:
                for key in gs.parameters:
                    assert not key.startswith("bq_"), (
                        f"Boolean param '{key}' leaked — causes WDK 422"
                    )

            assert gs.step_count > 1
            assert gs.wdk_step_id is not None
            assert len(gs.gene_ids) > 0
        finally:
            await api.delete_strategy(sid)
