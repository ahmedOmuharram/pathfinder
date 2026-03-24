"""Integration tests for experiment refinement service functions.

Tests combine_with_search, apply_transform, and combine_steps using
real WDK API calls (backed by VCR cassettes) instead of mocks.

Record cassettes:
    WDK_AUTH_EMAIL=... WDK_AUTH_PASSWORD=... WDK_TARGET_SITE=plasmodb \
    uv run pytest src/veupath_chatbot/tests/integration/test_experiment_refine.py -v --record-mode=all

Replay (CI / normal dev):
    uv run pytest src/veupath_chatbot/tests/integration/test_experiment_refine.py -v
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from veupath_chatbot.domain.parameters.vocab_utils import collect_leaf_terms
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    WDKSearchConfig,
    WDKStepTree,
)
from veupath_chatbot.platform.errors import NotFoundError, WDKError
from veupath_chatbot.services.experiment.refine import (
    RefineResult,
    apply_transform,
    combine_steps,
    combine_with_search,
)
from veupath_chatbot.services.experiment.store import ExperimentStore
from veupath_chatbot.services.experiment.types import (
    Experiment,
    ExperimentConfig,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _discover_organism(wdk_api: StrategyAPI) -> str:
    """Query WDK to discover the first available organism for GenesByTaxon.

    Returns a JSON-encoded list with one organism term, e.g.
    ``'["Plasmodium falciparum 3D7"]'`` on plasmodb or
    ``'["Toxoplasma gondii ME49"]'`` on toxodb.
    """
    search_response = await wdk_api.client.get_search_details(
        "transcript", "GenesByTaxon"
    )
    for param in search_response.search_data.parameters or []:
        if param.name == "organism" and param.vocabulary is not None:
            if isinstance(param.vocabulary, dict):
                # Tree vocabulary — collect the first leaf term
                leaves = collect_leaf_terms(param.vocabulary)
                if leaves:
                    return json.dumps([leaves[0]])
            elif isinstance(param.vocabulary, list):
                # List vocabulary — take the first entry's value
                for item in param.vocabulary:
                    if isinstance(item, list) and item:
                        return json.dumps([str(item[0])])
                    if isinstance(item, str):
                        return json.dumps([item])
    msg = "Could not discover organism from GenesByTaxon search parameters"
    raise RuntimeError(msg)


def _cfg(site_id: str, organism_param: str) -> ExperimentConfig:
    """Minimal config for test experiments (site-agnostic)."""
    return ExperimentConfig(
        site_id=site_id,
        record_type="transcript",
        search_name="GenesByTaxon",
        parameters={"organism": organism_param},
        positive_controls=["PF3D7_0100100"],
        negative_controls=["PF3D7_0100200"],
        controls_search_name="GeneByLocusTag",
        controls_param_name="single_gene_id",
    )


def _exp(
    site_id: str,
    organism_param: str,
    exp_id: str = "exp_refine_001",
    wdk_strategy_id: int | None = None,
    wdk_step_id: int | None = None,
) -> Experiment:
    """Build a test experiment, optionally pre-wired with WDK IDs."""
    exp = Experiment(id=exp_id, config=_cfg(site_id, organism_param))
    exp.wdk_strategy_id = wdk_strategy_id
    exp.wdk_step_id = wdk_step_id
    return exp


async def _create_base_strategy(
    wdk_api: StrategyAPI,
    organism_param: str,
) -> tuple[int, int]:
    """Create a real WDK strategy with one GenesByTaxon step.

    Returns (strategy_id, step_id).
    """
    step = await wdk_api.create_step(
        NewStepSpec(
            search_name="GenesByTaxon",
            search_config=WDKSearchConfig(
                parameters={"organism": organism_param},
            ),
            custom_name="Base step for refine test",
        ),
        record_type="transcript",
    )

    strategy = await wdk_api.create_strategy(
        step_tree=WDKStepTree(step_id=step.id),
        name="test-refine-base",
    )
    return strategy.id, step.id


async def _create_secondary_step(
    wdk_api: StrategyAPI, organism_param: str
) -> int:
    """Create a secondary GenesByTaxon step (for combine tests).

    Returns the step ID.
    """
    step = await wdk_api.create_step(
        NewStepSpec(
            search_name="GenesByTaxon",
            search_config=WDKSearchConfig(
                parameters={"organism": organism_param},
            ),
            custom_name="Secondary step for combine test",
        ),
        record_type="transcript",
    )
    return step.id


# ---------------------------------------------------------------------------
# combine_with_search
# ---------------------------------------------------------------------------


class TestCombineWithSearch:
    @pytest.mark.vcr
    async def test_creates_step_combines_and_updates(
        self,
        wdk_api: StrategyAPI,
        wdk_test_site: tuple[str, str],
        patch_app_db_engine: None,
        db_cleaner: None,
    ) -> None:
        site_id, _base_url = wdk_test_site
        organism_param = await _discover_organism(wdk_api)
        strategy_id, step_id = await _create_base_strategy(wdk_api, organism_param)

        exp = _exp(site_id, organism_param, wdk_strategy_id=strategy_id, wdk_step_id=step_id)
        store = ExperimentStore()
        store.save(exp)

        result = await combine_with_search(
            api=wdk_api,
            exp=exp,
            search_name="GenesByTaxon",
            parameters={"organism": organism_param},
            operator="INTERSECT",
            store=store,
        )

        assert isinstance(result, RefineResult)
        assert result.operator == "INTERSECT"
        # The combined step must be a NEW step (different from the base)
        assert result.new_step_id != step_id
        # Estimated size should be a non-negative integer from real WDK
        assert result.estimated_size is not None
        assert result.estimated_size >= 0
        # Experiment's wdk_step_id should be updated to the combined step
        assert exp.wdk_step_id == result.new_step_id

    async def test_raises_when_no_strategy(self, wdk_api: StrategyAPI) -> None:
        exp = _exp("plasmodb", '["dummy"]', wdk_strategy_id=None, wdk_step_id=99)
        store = ExperimentStore()

        with pytest.raises(NotFoundError):
            await combine_with_search(
                api=wdk_api,
                exp=exp,
                search_name="X",
                parameters={},
                operator="INTERSECT",
                store=store,
            )

    async def test_raises_when_no_step_id(self, wdk_api: StrategyAPI) -> None:
        exp = _exp("plasmodb", '["dummy"]', wdk_strategy_id=42, wdk_step_id=None)
        store = ExperimentStore()

        with pytest.raises(NotFoundError):
            await combine_with_search(
                api=wdk_api,
                exp=exp,
                search_name="X",
                parameters={},
                operator="INTERSECT",
                store=store,
            )

    @pytest.mark.vcr
    async def test_propagates_wdk_error(
        self,
        wdk_api: StrategyAPI,
        wdk_test_site: tuple[str, str],
        patch_app_db_engine: None,
        db_cleaner: None,
    ) -> None:
        """WDK errors from step creation propagate to the caller."""
        site_id, _base_url = wdk_test_site
        organism_param = await _discover_organism(wdk_api)
        strategy_id, step_id = await _create_base_strategy(wdk_api, organism_param)
        exp = _exp(site_id, organism_param, wdk_strategy_id=strategy_id, wdk_step_id=step_id)
        store = ExperimentStore()

        # Use an invalid search name that WDK will reject
        with pytest.raises(WDKError):
            await combine_with_search(
                api=wdk_api,
                exp=exp,
                search_name="NonExistentSearchThatWDKRejects",
                parameters={},
                operator="INTERSECT",
                store=store,
            )

        # Step ID should NOT have been updated on failure
        assert exp.wdk_step_id == step_id


# ---------------------------------------------------------------------------
# apply_transform
# ---------------------------------------------------------------------------


class TestApplyTransform:
    @pytest.mark.vcr
    async def test_creates_transform_and_updates(
        self,
        wdk_api: StrategyAPI,
        wdk_test_site: tuple[str, str],
        patch_app_db_engine: None,
        db_cleaner: None,
    ) -> None:
        site_id, _base_url = wdk_test_site
        organism_param = await _discover_organism(wdk_api)
        strategy_id, step_id = await _create_base_strategy(wdk_api, organism_param)

        exp = _exp(site_id, organism_param, wdk_strategy_id=strategy_id, wdk_step_id=step_id)
        store = ExperimentStore()
        store.save(exp)

        result = await apply_transform(
            api=wdk_api,
            exp=exp,
            transform_name="GenesByWeightFilter",
            parameters={
                "min_weight": "1",
                "max_weight": "100",
            },
            store=store,
        )

        assert isinstance(result, RefineResult)
        # Transform result should have no operator (it's not a boolean combine)
        assert result.operator is None
        assert result.new_step_id != step_id
        # estimated_size may be None if WDK can't compute the count for
        # this transform type (e.g., GenesByWeightFilter returns 500 on
        # reports/standard).  The important thing is the transform was
        # created and the experiment updated.
        if result.estimated_size is not None:
            assert result.estimated_size >= 0
        assert exp.wdk_step_id == result.new_step_id

    async def test_raises_when_no_strategy(self, wdk_api: StrategyAPI) -> None:
        exp = _exp("plasmodb", '["dummy"]', wdk_strategy_id=None, wdk_step_id=99)
        store = ExperimentStore()

        with pytest.raises(NotFoundError):
            await apply_transform(
                api=wdk_api,
                exp=exp,
                transform_name="X",
                parameters={},
                store=store,
            )

    async def test_raises_when_no_step_id(self, wdk_api: StrategyAPI) -> None:
        exp = _exp("plasmodb", '["dummy"]', wdk_strategy_id=42, wdk_step_id=None)
        store = ExperimentStore()

        with pytest.raises(NotFoundError):
            await apply_transform(
                api=wdk_api,
                exp=exp,
                transform_name="X",
                parameters={},
                store=store,
            )


# ---------------------------------------------------------------------------
# combine_steps
# ---------------------------------------------------------------------------


class TestCombineSteps:
    @pytest.mark.vcr
    async def test_combines_and_returns_result(
        self,
        wdk_api: StrategyAPI,
        wdk_test_site: tuple[str, str],
        patch_app_db_engine: None,
        db_cleaner: None,
    ) -> None:
        site_id, _base_url = wdk_test_site
        organism_param = await _discover_organism(wdk_api)
        strategy_id, step_id = await _create_base_strategy(wdk_api, organism_param)
        secondary_id = await _create_secondary_step(wdk_api, organism_param)

        exp = _exp(site_id, organism_param, wdk_strategy_id=strategy_id, wdk_step_id=step_id)
        store = ExperimentStore()
        store.save(exp)

        result = await combine_steps(
            api=wdk_api,
            exp=exp,
            secondary_step_id=secondary_id,
            operator="UNION",
            store=store,
        )

        assert isinstance(result, RefineResult)
        assert result.new_step_id != step_id
        assert result.operator == "UNION"
        assert result.estimated_size is not None
        assert result.estimated_size >= 0
        assert exp.wdk_step_id == result.new_step_id

    @pytest.mark.vcr
    async def test_handles_count_failure_gracefully(
        self,
        wdk_api: StrategyAPI,
        wdk_test_site: tuple[str, str],
        patch_app_db_engine: None,
        db_cleaner: None,
    ) -> None:
        """When get_step_count raises, estimated_size is None but combine succeeds.

        Uses a targeted mock on get_step_count only — all other API calls
        go through the real VCR-backed StrategyAPI.
        """
        site_id, _base_url = wdk_test_site
        organism_param = await _discover_organism(wdk_api)
        strategy_id, step_id = await _create_base_strategy(wdk_api, organism_param)
        secondary_id = await _create_secondary_step(wdk_api, organism_param)

        exp = _exp(site_id, organism_param, wdk_strategy_id=strategy_id, wdk_step_id=step_id)
        store = ExperimentStore()
        store.save(exp)

        with patch.object(
            wdk_api,
            "get_step_count",
            new=AsyncMock(side_effect=WDKError(detail="WDK error")),
        ):
            result = await combine_steps(
                api=wdk_api,
                exp=exp,
                secondary_step_id=secondary_id,
                operator="INTERSECT",
                store=store,
            )

        assert result.new_step_id != step_id
        assert result.estimated_size is None
        assert exp.wdk_step_id == result.new_step_id

    @pytest.mark.vcr
    async def test_raises_on_combined_step_failure(
        self,
        wdk_api: StrategyAPI,
        wdk_test_site: tuple[str, str],
        patch_app_db_engine: None,
        db_cleaner: None,
    ) -> None:
        """Using an invalid operator causes WDK to reject the combined step."""
        site_id, _base_url = wdk_test_site
        organism_param = await _discover_organism(wdk_api)
        strategy_id, step_id = await _create_base_strategy(wdk_api, organism_param)
        secondary_id = await _create_secondary_step(wdk_api, organism_param)

        exp = _exp(site_id, organism_param, wdk_strategy_id=strategy_id, wdk_step_id=step_id)
        store = ExperimentStore()

        with pytest.raises(WDKError):
            await combine_steps(
                api=wdk_api,
                exp=exp,
                secondary_step_id=secondary_id,
                operator="INVALID_OPERATOR",
                store=store,
            )

        # Step ID unchanged on failure
        assert exp.wdk_step_id == step_id

    @pytest.mark.vcr
    async def test_uses_custom_name(
        self,
        wdk_api: StrategyAPI,
        wdk_test_site: tuple[str, str],
        patch_app_db_engine: None,
        db_cleaner: None,
    ) -> None:
        """Custom name is passed through to the combined step."""
        site_id, _base_url = wdk_test_site
        organism_param = await _discover_organism(wdk_api)
        strategy_id, step_id = await _create_base_strategy(wdk_api, organism_param)
        secondary_id = await _create_secondary_step(wdk_api, organism_param)

        exp = _exp(site_id, organism_param, wdk_strategy_id=strategy_id, wdk_step_id=step_id)
        store = ExperimentStore()
        store.save(exp)

        result = await combine_steps(
            api=wdk_api,
            exp=exp,
            secondary_step_id=secondary_id,
            operator="INTERSECT",
            store=store,
            custom_name="My custom combine",
        )

        # Verify the combine succeeded
        assert result.new_step_id != step_id
        assert exp.wdk_step_id == result.new_step_id

        # Fetch the combined step from WDK and verify the custom name
        step = await wdk_api.find_step(result.new_step_id)
        assert step.custom_name == "My custom combine"

    async def test_raises_when_no_strategy(self, wdk_api: StrategyAPI) -> None:
        exp = _exp("plasmodb", '["dummy"]', wdk_strategy_id=None, wdk_step_id=99)
        store = ExperimentStore()

        with pytest.raises(NotFoundError):
            await combine_steps(
                api=wdk_api,
                exp=exp,
                secondary_step_id=200,
                operator="INTERSECT",
                store=store,
            )
