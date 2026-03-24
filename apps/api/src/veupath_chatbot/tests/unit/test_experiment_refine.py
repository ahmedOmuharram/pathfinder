"""Unit tests for experiment refinement service functions.

Tests combine_with_search, apply_transform, and combine_steps — the shared
strategy-refinement logic extracted from the transport endpoint and AI tools.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.integrations.veupathdb.wdk_models import WDKIdentifier
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


def _cfg() -> ExperimentConfig:
    return ExperimentConfig(
        site_id="plasmodb",
        record_type="gene",
        search_name="GenesByTextSearch",
        parameters={},
        positive_controls=["g1", "g2"],
        negative_controls=["n1"],
        controls_search_name="GeneByLocusTag",
        controls_param_name="single_gene_id",
    )


def _exp(
    exp_id: str = "exp_001",
    wdk_strategy_id: int | None = 42,
    wdk_step_id: int | None = 99,
) -> Experiment:
    exp = Experiment(id=exp_id, config=_cfg())
    exp.wdk_strategy_id = wdk_strategy_id
    exp.wdk_step_id = wdk_step_id
    return exp


def _mock_api() -> AsyncMock:
    api = AsyncMock()
    api.create_step.return_value = WDKIdentifier(id=200)
    api.create_combined_step.return_value = WDKIdentifier(id=300)
    api.create_transform_step.return_value = WDKIdentifier(id=400)
    api.update_strategy = AsyncMock()
    api.get_step_count.return_value = 150
    return api


# ---------------------------------------------------------------------------
# combine_with_search
# ---------------------------------------------------------------------------


class TestCombineWithSearch:
    @patch("veupath_chatbot.platform.store.spawn")
    async def test_creates_step_combines_and_updates(
        self, mock_spawn: MagicMock
    ) -> None:
        api = _mock_api()
        exp = _exp()
        store = ExperimentStore()
        store.save(exp)

        result = await combine_with_search(
            api=api,
            exp=exp,
            search_name="GenesByOrthologs",
            parameters={"organism": "pfal"},
            operator="INTERSECT",
            store=store,
        )

        assert isinstance(result, RefineResult)
        assert result.new_step_id == 300
        assert result.operator == "INTERSECT"
        assert result.estimated_size == 150

        # Experiment updated
        assert exp.wdk_step_id == 300

        # API called correctly
        api.create_step.assert_awaited_once()
        api.create_combined_step.assert_awaited_once()
        api.update_strategy.assert_awaited_once()

    @patch("veupath_chatbot.platform.store.spawn")
    async def test_raises_when_no_strategy(self, mock_spawn: MagicMock) -> None:
        api = _mock_api()
        exp = _exp(wdk_strategy_id=None)
        store = ExperimentStore()

        with pytest.raises(NotFoundError):
            await combine_with_search(
                api=api, exp=exp, search_name="X", parameters={},
                operator="INTERSECT", store=store,
            )

    @patch("veupath_chatbot.platform.store.spawn")
    async def test_raises_when_no_step_id(self, mock_spawn: MagicMock) -> None:
        api = _mock_api()
        exp = _exp(wdk_step_id=None)
        store = ExperimentStore()

        with pytest.raises(NotFoundError):
            await combine_with_search(
                api=api, exp=exp, search_name="X", parameters={},
                operator="INTERSECT", store=store,
            )

    @patch("veupath_chatbot.platform.store.spawn")
    async def test_propagates_wdk_error(self, mock_spawn: MagicMock) -> None:
        api = _mock_api()
        api.create_step.side_effect = WDKError(detail="bad params")
        exp = _exp()
        store = ExperimentStore()

        with pytest.raises(WDKError, match="bad params"):
            await combine_with_search(
                api=api, exp=exp, search_name="X", parameters={},
                operator="INTERSECT", store=store,
            )

        # Step ID should NOT have been updated
        assert exp.wdk_step_id == 99


# ---------------------------------------------------------------------------
# apply_transform
# ---------------------------------------------------------------------------


class TestApplyTransform:
    @patch("veupath_chatbot.platform.store.spawn")
    async def test_creates_transform_and_updates(
        self, mock_spawn: MagicMock
    ) -> None:
        api = _mock_api()
        exp = _exp()
        store = ExperimentStore()
        store.save(exp)

        result = await apply_transform(
            api=api,
            exp=exp,
            transform_name="GenesByOrthologPattern",
            parameters={"organism": "pfal"},
            store=store,
        )

        assert isinstance(result, RefineResult)
        assert result.new_step_id == 400
        assert result.operator is None
        assert result.estimated_size == 150

        # Experiment updated
        assert exp.wdk_step_id == 400

        # API called correctly
        api.create_transform_step.assert_awaited_once()
        api.update_strategy.assert_awaited_once()

    @patch("veupath_chatbot.platform.store.spawn")
    async def test_raises_when_no_strategy(self, mock_spawn: MagicMock) -> None:
        api = _mock_api()
        exp = _exp(wdk_strategy_id=None)
        store = ExperimentStore()

        with pytest.raises(NotFoundError):
            await apply_transform(
                api=api, exp=exp, transform_name="X",
                parameters={}, store=store,
            )

    @patch("veupath_chatbot.platform.store.spawn")
    async def test_raises_when_no_step_id(self, mock_spawn: MagicMock) -> None:
        api = _mock_api()
        exp = _exp(wdk_step_id=None)
        store = ExperimentStore()

        with pytest.raises(NotFoundError):
            await apply_transform(
                api=api, exp=exp, transform_name="X",
                parameters={}, store=store,
            )


# ---------------------------------------------------------------------------
# combine_steps (lower-level, used by AI tools' refine_with_gene_ids)
# ---------------------------------------------------------------------------


class TestCombineSteps:
    @patch("veupath_chatbot.platform.store.spawn")
    async def test_combines_and_returns_result(
        self, mock_spawn: MagicMock
    ) -> None:
        api = _mock_api()
        exp = _exp()
        store = ExperimentStore()
        store.save(exp)

        result = await combine_steps(
            api=api,
            exp=exp,
            secondary_step_id=200,
            operator="UNION",
            store=store,
        )

        assert result.new_step_id == 300
        assert result.operator == "UNION"
        assert result.estimated_size == 150
        assert exp.wdk_step_id == 300

    @patch("veupath_chatbot.platform.store.spawn")
    async def test_handles_count_failure_gracefully(
        self, mock_spawn: MagicMock
    ) -> None:
        api = _mock_api()
        api.get_step_count.side_effect = WDKError(detail="WDK error")
        exp = _exp()
        store = ExperimentStore()
        store.save(exp)

        result = await combine_steps(
            api=api, exp=exp, secondary_step_id=200,
            operator="INTERSECT", store=store,
        )

        assert result.new_step_id == 300
        assert result.estimated_size is None

    @patch("veupath_chatbot.platform.store.spawn")
    async def test_raises_on_combined_step_failure(
        self, mock_spawn: MagicMock
    ) -> None:
        api = _mock_api()
        api.create_combined_step.side_effect = WDKError(detail="invalid operator")
        exp = _exp()
        store = ExperimentStore()

        with pytest.raises(WDKError, match="invalid operator"):
            await combine_steps(
                api=api, exp=exp, secondary_step_id=200,
                operator="INVALID", store=store,
            )

        assert exp.wdk_step_id == 99  # Unchanged

    @patch("veupath_chatbot.platform.store.spawn")
    async def test_uses_custom_name(self, mock_spawn: MagicMock) -> None:
        api = _mock_api()
        exp = _exp()
        store = ExperimentStore()
        store.save(exp)

        await combine_steps(
            api=api, exp=exp, secondary_step_id=200,
            operator="INTERSECT", store=store,
            custom_name="My custom combine",
        )

        call_kwargs = api.create_combined_step.call_args.kwargs
        assert call_kwargs["spec_overrides"].custom_name == "My custom combine"

    @patch("veupath_chatbot.platform.store.spawn")
    async def test_raises_when_no_strategy(self, mock_spawn: MagicMock) -> None:
        api = _mock_api()
        exp = _exp(wdk_strategy_id=None)
        store = ExperimentStore()

        with pytest.raises(NotFoundError):
            await combine_steps(
                api=api, exp=exp, secondary_step_id=200,
                operator="INTERSECT", store=store,
            )
