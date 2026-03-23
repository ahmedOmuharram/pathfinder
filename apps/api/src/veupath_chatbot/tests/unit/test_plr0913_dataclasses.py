"""Tests for dataclasses and helper methods introduced during PLR0913 refactoring."""

import json
from unittest.mock import AsyncMock

import pytest

from veupath_chatbot.ai.tools.planner.optimization_tools import (
    OptimizationControls,
    OptimizationSettings,
    OptimizationTarget,
)
from veupath_chatbot.domain.research.citations import (
    LiteratureFilters,
    LiteratureOutputOptions,
)
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKAnswer,
    WDKSearchConfig,
    WDKStep,
    WDKStrategyDetails,
)
from veupath_chatbot.platform.errors import InternalError
from veupath_chatbot.platform.types import ModelProvider, ReasoningEffort
from veupath_chatbot.services.chat.types import ChatTurnConfig
from veupath_chatbot.services.control_tests import IntersectionConfig
from veupath_chatbot.services.experiment.robustness import BootstrapOptions
from veupath_chatbot.services.experiment.types import DEFAULT_K_VALUES
from veupath_chatbot.services.gene_sets.operations import (
    GeneSetService,
    GeneSetWdkContext,
)
from veupath_chatbot.services.gene_sets.store import GeneSetStore
from veupath_chatbot.services.parameter_optimization.callbacks import (
    OptimizationCompletedEvent,
    OptimizationStartedEvent,
    TrialProgressEvent,
    emit_completed,
    emit_started,
    emit_trial_progress,
)
from veupath_chatbot.services.parameter_optimization.config import (
    OptimizationInput,
    ParameterSpec,
    TrialResult,
)
from veupath_chatbot.services.research.utils import (
    LiteratureItemContext,
    passes_filters,
)

# ChatTurnConfig


class TestChatTurnConfig:
    def test_defaults_are_all_none_or_false(self) -> None:
        cfg = ChatTurnConfig()
        assert cfg.mentions is None
        assert cfg.disable_rag is False
        assert cfg.disabled_tools is None
        assert cfg.provider_override is None
        assert cfg.model_override is None
        assert cfg.reasoning_effort is None
        assert cfg.temperature is None
        assert cfg.seed is None
        assert cfg.context_size is None
        assert cfg.response_tokens is None
        assert cfg.reasoning_budget is None

    def test_all_fields_set(self) -> None:
        provider: ModelProvider = "anthropic"
        effort: ReasoningEffort = "high"
        cfg = ChatTurnConfig(
            mentions=[{"id": "gene1", "type": "gene"}],
            disable_rag=True,
            disabled_tools=["search_literature"],
            provider_override=provider,
            model_override="claude-opus-4",
            reasoning_effort=effort,
            temperature=0.7,
            seed=42,
            context_size=8192,
            response_tokens=2048,
            reasoning_budget=1024,
        )
        assert cfg.disable_rag is True
        assert cfg.disabled_tools == ["search_literature"]
        assert cfg.provider_override == "anthropic"
        assert cfg.model_override == "claude-opus-4"
        assert cfg.reasoning_effort == "high"
        assert cfg.temperature == 0.7
        assert cfg.seed == 42
        assert cfg.context_size == 8192
        assert cfg.response_tokens == 2048
        assert cfg.reasoning_budget == 1024

    def test_mentions_preserved(self) -> None:
        mentions = [{"id": "PF3D7_0100100", "type": "gene"}]
        cfg = ChatTurnConfig(mentions=mentions)
        assert cfg.mentions == mentions

    def test_disable_rag_flag(self) -> None:
        cfg = ChatTurnConfig(disable_rag=True)
        assert cfg.disable_rag is True


# IntersectionConfig


class TestIntersectionConfig:
    def test_required_fields(self) -> None:
        cfg = IntersectionConfig(
            site_id="plasmodb",
            record_type="transcript",
            target_search_name="GenesByExpressionTwoChannel",
            target_parameters={"fold_change": "2.0"},
            controls_search_name="GenesByLocusTag",
            controls_param_name="ds_gene_ids",
        )
        assert cfg.site_id == "plasmodb"
        assert cfg.record_type == "transcript"
        assert cfg.target_search_name == "GenesByExpressionTwoChannel"
        assert cfg.controls_search_name == "GenesByLocusTag"
        assert cfg.controls_param_name == "ds_gene_ids"

    def test_optional_defaults(self) -> None:
        cfg = IntersectionConfig(
            site_id="toxodb",
            record_type="transcript",
            target_search_name="SomeSearch",
            target_parameters={},
            controls_search_name="GenesByLocusTag",
            controls_param_name="ds_gene_ids",
        )
        assert cfg.controls_value_format == "newline"
        assert cfg.controls_extra_parameters is None
        assert cfg.id_field is None

    def test_boolean_operator_default_is_intersect(self) -> None:
        cfg = IntersectionConfig(
            site_id="plasmodb",
            record_type="transcript",
            target_search_name="SearchA",
            target_parameters={},
            controls_search_name="SearchB",
            controls_param_name="param1",
        )
        assert cfg.boolean_operator.lower() == "intersect"

    def test_custom_boolean_operator(self) -> None:
        cfg = IntersectionConfig(
            site_id="plasmodb",
            record_type="transcript",
            target_search_name="SearchA",
            target_parameters={},
            controls_search_name="SearchB",
            controls_param_name="param1",
            boolean_operator="union",
        )
        assert cfg.boolean_operator == "union"

    def test_controls_extra_parameters_passed_through(self) -> None:
        extra = {"organism": "Plasmodium falciparum 3D7"}
        cfg = IntersectionConfig(
            site_id="plasmodb",
            record_type="transcript",
            target_search_name="SearchA",
            target_parameters={"k": "v"},
            controls_search_name="SearchB",
            controls_param_name="param1",
            controls_extra_parameters=extra,
        )
        assert cfg.controls_extra_parameters == extra


# OptimizationStartedEvent, TrialProgressEvent, OptimizationCompletedEvent


class TestOptimizationStartedEvent:
    def test_construction_and_field_access(self) -> None:
        ev = OptimizationStartedEvent(
            optimization_id="opt-abc123",
            search_name="GenesByExpressionTwoChannel",
            record_type="transcript",
            budget=20,
            objective="f1",
            positive_controls_count=10,
            negative_controls_count=5,
            param_space_json=[{"name": "fold_change", "type": "numeric"}],
        )
        assert ev.optimization_id == "opt-abc123"
        assert ev.search_name == "GenesByExpressionTwoChannel"
        assert ev.record_type == "transcript"
        assert ev.budget == 20
        assert ev.objective == "f1"
        assert ev.positive_controls_count == 10
        assert ev.negative_controls_count == 5
        assert ev.param_space_json == [{"name": "fold_change", "type": "numeric"}]

    def test_is_frozen(self) -> None:
        ev = OptimizationStartedEvent(
            optimization_id="x",
            search_name="S",
            record_type="transcript",
            budget=5,
            objective="recall",
            positive_controls_count=0,
            negative_controls_count=0,
            param_space_json=[],
        )
        with pytest.raises(AttributeError):
            ev.budget = 10  # type: ignore[misc]

    @pytest.mark.asyncio
    async def test_emit_started_payload_shape(self) -> None:
        emitted: list[object] = []

        async def callback(payload: object) -> None:
            emitted.append(payload)

        ev = OptimizationStartedEvent(
            optimization_id="opt-1",
            search_name="GenesByFC",
            record_type="transcript",
            budget=15,
            objective="f1",
            positive_controls_count=8,
            negative_controls_count=4,
            param_space_json=[{"name": "fc", "type": "numeric"}],
        )
        await emit_started(callback, ev)

        assert len(emitted) == 1
        payload = emitted[0]
        assert isinstance(payload, dict)
        assert payload["type"] == "optimization_progress"
        data = payload["data"]
        assert isinstance(data, dict)
        assert data["status"] == "started"
        assert data["optimizationId"] == "opt-1"
        assert data["budget"] == 15
        assert data["currentTrial"] == 0
        assert data["totalTrials"] == 15
        assert data["bestTrial"] is None


class TestTrialProgressEvent:
    def test_construction(self) -> None:
        trial_result = TrialResult(
            trial_number=1,
            parameters={"fold_change": 2.5},
            score=0.75,
            recall=0.8,
            false_positive_rate=0.1,
            estimated_size=120,
        )
        ev = TrialProgressEvent(
            optimization_id="opt-2",
            trial_num=3,
            budget=20,
            trial_json={"trial_number": 3, "score": 0.75},
            best_trial=trial_result,
            recent_trials=[trial_result],
        )
        assert ev.optimization_id == "opt-2"
        assert ev.trial_num == 3
        assert ev.budget == 20
        assert ev.best_trial is trial_result
        assert len(ev.recent_trials) == 1

    def test_is_frozen(self) -> None:
        ev = TrialProgressEvent(
            optimization_id="x",
            trial_num=1,
            budget=5,
            trial_json={},
            best_trial=None,
            recent_trials=[],
        )
        with pytest.raises(AttributeError):
            ev.trial_num = 99  # type: ignore[misc]

    @pytest.mark.asyncio
    async def test_emit_trial_progress_payload_shape(self) -> None:
        emitted: list[object] = []

        async def callback(payload: object) -> None:
            emitted.append(payload)

        ev = TrialProgressEvent(
            optimization_id="opt-3",
            trial_num=5,
            budget=20,
            trial_json={"trial_number": 5, "score": 0.65},
            best_trial=None,
            recent_trials=[],
        )
        await emit_trial_progress(callback, ev)

        assert len(emitted) == 1
        payload = emitted[0]
        assert isinstance(payload, dict)
        data = payload["data"]
        assert isinstance(data, dict)
        assert data["status"] == "running"
        assert data["currentTrial"] == 5
        assert data["totalTrials"] == 20
        assert data["bestTrial"] is None


class TestOptimizationCompletedEvent:
    def test_construction(self) -> None:
        t = TrialResult(
            trial_number=1,
            parameters={"fc": 2.0},
            score=0.9,
            recall=0.85,
            false_positive_rate=0.05,
            estimated_size=90,
        )
        ev = OptimizationCompletedEvent(
            optimization_id="opt-done",
            status="completed",
            budget=10,
            trials=[t],
            best_trial=t,
            pareto=[t],
            sensitivity={"fc": 0.4},
            elapsed=32.5,
        )
        assert ev.optimization_id == "opt-done"
        assert ev.status == "completed"
        assert len(ev.trials) == 1
        assert ev.best_trial is t
        assert ev.sensitivity == {"fc": 0.4}
        assert ev.elapsed == 32.5

    def test_is_frozen(self) -> None:
        ev = OptimizationCompletedEvent(
            optimization_id="x",
            status="completed",
            budget=5,
            trials=[],
            best_trial=None,
            pareto=[],
            sensitivity={},
            elapsed=1.0,
        )
        with pytest.raises(AttributeError):
            ev.status = "error"  # type: ignore[misc]

    @pytest.mark.asyncio
    async def test_emit_completed_payload_shape(self) -> None:
        emitted: list[object] = []

        async def callback(payload: object) -> None:
            emitted.append(payload)

        ev = OptimizationCompletedEvent(
            optimization_id="opt-final",
            status="completed",
            budget=10,
            trials=[],
            best_trial=None,
            pareto=[],
            sensitivity={"param_a": 0.3},
            elapsed=45.1,
        )
        await emit_completed(callback, ev)

        assert len(emitted) == 1
        payload = emitted[0]
        assert isinstance(payload, dict)
        data = payload["data"]
        assert isinstance(data, dict)
        assert data["status"] == "completed"
        assert data["optimizationId"] == "opt-final"
        assert data["totalTrials"] == 10
        assert data["currentTrial"] == 0
        assert round(data["totalTimeSeconds"], 1) == 45.1


# OptimizationInput


class TestOptimizationInput:
    def test_required_fields(self) -> None:
        spec = ParameterSpec(name="fold_change", param_type="numeric", min_value=1.5, max_value=20.0)
        inp = OptimizationInput(
            site_id="plasmodb",
            record_type="transcript",
            search_name="GenesByExpressionTwoChannel",
            parameter_space=[spec],
            controls_search_name="GenesByLocusTag",
            controls_param_name="ds_gene_ids",
        )
        assert inp.site_id == "plasmodb"
        assert inp.record_type == "transcript"
        assert inp.search_name == "GenesByExpressionTwoChannel"
        assert inp.controls_search_name == "GenesByLocusTag"
        assert inp.controls_param_name == "ds_gene_ids"
        assert len(inp.parameter_space) == 1

    def test_optional_defaults(self) -> None:
        spec = ParameterSpec(name="fc", param_type="numeric", min_value=1.0, max_value=10.0)
        inp = OptimizationInput(
            site_id="toxodb",
            record_type="transcript",
            search_name="SomeSearch",
            parameter_space=[spec],
            controls_search_name="GenesByLocusTag",
            controls_param_name="ds_gene_ids",
        )
        assert inp.fixed_parameters == {}
        assert inp.positive_controls is None
        assert inp.negative_controls is None
        assert inp.controls_value_format == "newline"
        assert inp.controls_extra_parameters is None
        assert inp.id_field is None

    def test_with_controls(self) -> None:
        spec = ParameterSpec(name="fc", param_type="numeric", min_value=1.0, max_value=10.0)
        pos = ["PF3D7_0100100", "PF3D7_0200200"]
        neg = ["PF3D7_0300300"]
        inp = OptimizationInput(
            site_id="plasmodb",
            record_type="transcript",
            search_name="Search",
            parameter_space=[spec],
            controls_search_name="ControlSearch",
            controls_param_name="ids",
            positive_controls=pos,
            negative_controls=neg,
        )
        assert inp.positive_controls == pos
        assert inp.negative_controls == neg

    def test_fixed_parameters_can_be_populated(self) -> None:
        spec = ParameterSpec(name="fc", param_type="numeric", min_value=1.0, max_value=10.0)
        inp = OptimizationInput(
            site_id="plasmodb",
            record_type="transcript",
            search_name="Search",
            parameter_space=[spec],
            controls_search_name="CS",
            controls_param_name="ids",
            fixed_parameters={"organism": "Plasmodium falciparum 3D7"},
        )
        assert inp.fixed_parameters["organism"] == "Plasmodium falciparum 3D7"


# LiteratureFilters and LiteratureOutputOptions


class TestLiteratureFilters:
    def test_all_defaults_none_or_false(self) -> None:
        f = LiteratureFilters()
        assert f.year_from is None
        assert f.year_to is None
        assert f.author_includes is None
        assert f.title_includes is None
        assert f.journal_includes is None
        assert f.doi_equals is None
        assert f.pmid_equals is None
        assert f.require_doi is False

    def test_specific_fields_set(self) -> None:
        f = LiteratureFilters(year_from=2020, year_to=2024, require_doi=True)
        assert f.year_from == 2020
        assert f.year_to == 2024
        assert f.require_doi is True

    def test_all_none_filters_passes_item(self) -> None:
        filters = LiteratureFilters()
        item = LiteratureItemContext(
            title="Malaria parasite study",
            authors=["Smith J", "Jones B"],
            year=2022,
            doi="10.1234/test",
            pmid="12345678",
            journal="Nature",
        )
        assert passes_filters(item, filters) is True

    def test_year_from_filters_old_papers(self) -> None:
        filters = LiteratureFilters(year_from=2020)
        item_old = LiteratureItemContext(
            title="Old paper", authors=None, year=2015, doi=None, pmid=None, journal=None
        )
        item_new = LiteratureItemContext(
            title="New paper", authors=None, year=2022, doi=None, pmid=None, journal=None
        )
        assert passes_filters(item_old, filters) is False
        assert passes_filters(item_new, filters) is True

    def test_year_to_filters_future_papers(self) -> None:
        filters = LiteratureFilters(year_to=2018)
        item_recent = LiteratureItemContext(
            title="Recent paper", authors=None, year=2023, doi=None, pmid=None, journal=None
        )
        item_old = LiteratureItemContext(
            title="Old paper", authors=None, year=2015, doi=None, pmid=None, journal=None
        )
        assert passes_filters(item_recent, filters) is False
        assert passes_filters(item_old, filters) is True

    def test_require_doi_excludes_items_without_doi(self) -> None:
        filters = LiteratureFilters(require_doi=True)
        item_no_doi = LiteratureItemContext(
            title="Paper", authors=None, year=2022, doi=None, pmid=None, journal=None
        )
        item_with_doi = LiteratureItemContext(
            title="Paper", authors=None, year=2022, doi="10.1234/abc", pmid=None, journal=None
        )
        assert passes_filters(item_no_doi, filters) is False
        assert passes_filters(item_with_doi, filters) is True

    def test_title_includes_case_insensitive(self) -> None:
        filters = LiteratureFilters(title_includes="malaria")
        item_match = LiteratureItemContext(
            title="Malaria parasite genomics", authors=None, year=2022, doi=None, pmid=None, journal=None
        )
        item_no_match = LiteratureItemContext(
            title="Dengue fever study", authors=None, year=2022, doi=None, pmid=None, journal=None
        )
        assert passes_filters(item_match, filters) is True
        assert passes_filters(item_no_match, filters) is False

    def test_author_includes_matches_substring(self) -> None:
        filters = LiteratureFilters(author_includes="Smith")
        item_match = LiteratureItemContext(
            title="Study", authors=["Smith J", "Jones B"], year=2022, doi=None, pmid=None, journal=None
        )
        item_no_match = LiteratureItemContext(
            title="Study", authors=["Brown A", "White C"], year=2022, doi=None, pmid=None, journal=None
        )
        assert passes_filters(item_match, filters) is True
        assert passes_filters(item_no_match, filters) is False

    def test_doi_equals_exact_match(self) -> None:
        filters = LiteratureFilters(doi_equals="10.1234/abc")
        item_match = LiteratureItemContext(
            title="Study", authors=None, year=2022, doi="10.1234/ABC", pmid=None, journal=None
        )
        item_no_match = LiteratureItemContext(
            title="Study", authors=None, year=2022, doi="10.9999/xyz", pmid=None, journal=None
        )
        assert passes_filters(item_match, filters) is True
        assert passes_filters(item_no_match, filters) is False

    def test_year_with_none_year_fails_ranged_filter(self) -> None:
        filters = LiteratureFilters(year_from=2020)
        item_no_year = LiteratureItemContext(
            title="Undated paper", authors=None, year=None, doi=None, pmid=None, journal=None
        )
        assert passes_filters(item_no_year, filters) is False


class TestLiteratureOutputOptions:
    def test_defaults(self) -> None:
        opts = LiteratureOutputOptions()
        assert opts.include_abstract is False
        assert opts.abstract_max_chars == 2000
        assert opts.max_authors == 2

    def test_custom_values(self) -> None:
        opts = LiteratureOutputOptions(
            include_abstract=True,
            abstract_max_chars=500,
            max_authors=5,
        )
        assert opts.include_abstract is True
        assert opts.abstract_max_chars == 500
        assert opts.max_authors == 5


# Pydantic models for AI optimization tools


class TestOptimizationTargetModel:
    def test_construction(self) -> None:
        t = OptimizationTarget(
            record_type="transcript",
            search_name="GenesByExpressionTwoChannel",
            parameter_space_json='[{"name":"fold_change","type":"numeric","min":1.5,"max":20}]',
            fixed_parameters_json='{"organism":"Plasmodium falciparum 3D7"}',
        )
        assert t.record_type == "transcript"
        assert t.search_name == "GenesByExpressionTwoChannel"
        assert "fold_change" in t.parameter_space_json

    def test_json_schema_is_serializable(self) -> None:
        schema = OptimizationTarget.model_json_schema()
        serialized = json.dumps(schema)
        assert "record_type" in serialized
        assert "search_name" in serialized


class TestOptimizationControlsModel:
    def test_construction_required_only(self) -> None:
        c = OptimizationControls(
            controls_search_name="GenesByLocusTag",
            controls_param_name="ds_gene_ids",
        )
        assert c.controls_search_name == "GenesByLocusTag"
        assert c.controls_param_name == "ds_gene_ids"
        assert c.positive_controls is None
        assert c.negative_controls is None

    def test_defaults(self) -> None:
        c = OptimizationControls(
            controls_search_name="S",
            controls_param_name="p",
        )
        assert c.controls_value_format == "newline"
        assert c.controls_extra_parameters_json is None
        assert c.id_field is None

    def test_json_schema_is_serializable(self) -> None:
        schema = OptimizationControls.model_json_schema()
        serialized = json.dumps(schema)
        assert "controls_search_name" in serialized


class TestOptimizationSettingsModel:
    def test_defaults(self) -> None:
        s = OptimizationSettings()
        assert s.budget == 15
        assert s.objective == "f1"
        assert s.beta == 1.0
        assert s.method == "bayesian"
        assert s.estimated_size_penalty == 0.1

    def test_custom_values(self) -> None:
        s = OptimizationSettings(
            budget=30,
            objective="recall",
            method="random",
            estimated_size_penalty=0.0,
        )
        assert s.budget == 30
        assert s.objective == "recall"
        assert s.method == "random"
        assert s.estimated_size_penalty == 0.0

    def test_json_schema_is_serializable(self) -> None:
        schema = OptimizationSettings.model_json_schema()
        serialized = json.dumps(schema)
        assert "budget" in serialized
        assert "objective" in serialized


# GeneSetWdkContext


class TestGeneSetWdkContext:
    def test_all_defaults_none(self) -> None:
        ctx = GeneSetWdkContext()
        assert ctx.wdk_strategy_id is None
        assert ctx.wdk_step_id is None
        assert ctx.search_name is None
        assert ctx.record_type is None
        assert ctx.parameters is None

    def test_construction_with_all_fields(self) -> None:
        ctx = GeneSetWdkContext(
            wdk_strategy_id=999,
            wdk_step_id=888,
            search_name="GenesByExpressionTwoChannel",
            record_type="transcript",
            parameters={"fold_change": "2.0", "organism": "Plasmodium falciparum 3D7"},
        )
        assert ctx.wdk_strategy_id == 999
        assert ctx.wdk_step_id == 888
        assert ctx.search_name == "GenesByExpressionTwoChannel"
        assert ctx.record_type == "transcript"
        assert ctx.parameters == {"fold_change": "2.0", "organism": "Plasmodium falciparum 3D7"}

    def test_partial_construction(self) -> None:
        ctx = GeneSetWdkContext(wdk_strategy_id=123)
        assert ctx.wdk_strategy_id == 123
        assert ctx.wdk_step_id is None
        assert ctx.search_name is None


# BootstrapOptions


class TestBootstrapOptions:
    def test_defaults(self) -> None:
        opts = BootstrapOptions()
        assert opts.n_bootstrap == 200
        assert opts.k_values == DEFAULT_K_VALUES
        assert opts.seed == 42
        assert opts.alternative_negatives is None
        assert opts.include_rank_metrics is True

    def test_k_values_default_is_a_copy(self) -> None:
        opts_a = BootstrapOptions()
        opts_b = BootstrapOptions()
        assert opts_a.k_values is not opts_b.k_values

    def test_custom_values(self) -> None:
        opts = BootstrapOptions(
            n_bootstrap=100,
            k_values=[10, 50],
            seed=7,
            alternative_negatives={"housekeeping": ["GENE_A", "GENE_B"]},
            include_rank_metrics=False,
        )
        assert opts.n_bootstrap == 100
        assert opts.k_values == [10, 50]
        assert opts.seed == 7
        assert opts.alternative_negatives == {"housekeeping": ["GENE_A", "GENE_B"]}
        assert opts.include_rank_metrics is False


# GeneSetService helper methods


def _make_service() -> GeneSetService:
    store = GeneSetStore()
    return GeneSetService(store)


def _make_api() -> AsyncMock:
    api = AsyncMock()
    api._resolved_user_id = 12345
    return api


class TestGeneSetServiceHelpers:
    """Test individual helper methods of GeneSetService using mocked StrategyAPI."""

    @pytest.mark.asyncio
    async def test_resolve_root_step_uses_provided_step_id(self) -> None:
        svc = _make_service()
        api = _make_api()
        result = await svc._resolve_root_step(api, strategy_id=100, step_id=42)
        assert result == 42
        api.get_strategy.assert_not_called()

    @pytest.mark.asyncio
    async def test_resolve_root_step_fetches_from_strategy_when_none(self) -> None:
        svc = _make_service()
        api = _make_api()
        api.get_strategy.return_value = WDKStrategyDetails.model_validate({
            "strategyId": 100,
            "name": "test",
            "rootStepId": 77,
            "stepTree": {"stepId": 77},
        })
        result = await svc._resolve_root_step(api, strategy_id=100, step_id=None)
        assert result == 77
        api.get_strategy.assert_called_once_with(100)

    @pytest.mark.asyncio
    async def test_resolve_root_step_returns_none_on_api_error(self) -> None:
        svc = _make_service()
        api = _make_api()
        api.get_strategy.side_effect = InternalError(detail="WDK unreachable")
        result = await svc._resolve_root_step(api, strategy_id=999, step_id=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_step_genes_returns_empty_when_step_id_none(self) -> None:
        svc = _make_service()
        api = _make_api()
        result = await svc._fetch_step_genes(api, step_id=None)
        assert result == []
        api.get_step_answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_step_genes_returns_ids_from_step(self) -> None:
        svc = _make_service()
        api = _make_api()
        api.get_step_answer.return_value = WDKAnswer.model_validate({
            "records": [
                {"id": [{"name": "source_id", "value": "PF3D7_0100100"}]},
                {"id": [{"name": "source_id", "value": "PF3D7_0200200"}]},
            ],
            "meta": {"totalCount": 2},
        })
        result = await svc._fetch_step_genes(api, step_id=55)
        assert "PF3D7_0100100" in result
        assert "PF3D7_0200200" in result

    @pytest.mark.asyncio
    async def test_fetch_step_genes_returns_empty_on_error(self) -> None:
        svc = _make_service()
        api = _make_api()
        api.get_step_answer.side_effect = InternalError(detail="step not found")
        result = await svc._fetch_step_genes(api, step_id=55)
        assert result == []

    @pytest.mark.asyncio
    async def test_count_strategy_steps_returns_one_for_single_step(self) -> None:
        svc = _make_service()
        api = _make_api()
        _sc = WDKSearchConfig()
        api.get_strategy.return_value = WDKStrategyDetails.model_validate({
            "strategyId": 200,
            "name": "test",
            "rootStepId": 10,
            "stepTree": {"stepId": 10},
            "steps": {
                "10": {"id": 10, "searchName": "GenesByTextSearch", "searchConfig": _sc.model_dump(by_alias=True)},
            },
        })
        count = await svc._count_strategy_steps(api, strategy_id=200)
        assert count == 1

    @pytest.mark.asyncio
    async def test_count_strategy_steps_counts_nested_tree(self) -> None:
        svc = _make_service()
        api = _make_api()
        _sc = WDKSearchConfig()
        api.get_strategy.return_value = WDKStrategyDetails.model_validate({
            "strategyId": 300,
            "name": "test",
            "rootStepId": 30,
            "stepTree": {
                "stepId": 30,
                "primaryInput": {"stepId": 10},
                "secondaryInput": {"stepId": 20},
            },
            "steps": {
                "10": {"id": 10, "searchName": "Search1", "searchConfig": _sc.model_dump(by_alias=True)},
                "20": {"id": 20, "searchName": "Search2", "searchConfig": _sc.model_dump(by_alias=True)},
                "30": {"id": 30, "searchName": "BooleanQuestion", "searchConfig": _sc.model_dump(by_alias=True)},
            },
        })
        count = await svc._count_strategy_steps(api, strategy_id=300)
        assert count == 3

    @pytest.mark.asyncio
    async def test_count_strategy_steps_returns_one_on_error(self) -> None:
        svc = _make_service()
        api = _make_api()
        api.get_strategy.side_effect = InternalError(detail="strategy not found")
        count = await svc._count_strategy_steps(api, strategy_id=404)
        assert count == 1

    @pytest.mark.asyncio
    async def test_extract_step_search_context_returns_search_name(self) -> None:
        svc = _make_service()
        api = _make_api()
        api.find_step = AsyncMock(return_value=WDKStep(
            id=99,
            search_name="GenesByExpressionTwoChannel",
            search_config=WDKSearchConfig(
                parameters={"fold_change": "2.0", "organism": "Pf3D7"}
            ),
            record_class_name="GeneRecordClass",
        ))
        search_name, _record_type, parameters = await svc._extract_step_search_context(
            api, step_id=99, record_type=None
        )
        assert search_name == "GenesByExpressionTwoChannel"
        assert parameters is not None
        assert parameters["fold_change"] == "2.0"

    @pytest.mark.asyncio
    async def test_extract_step_search_context_ignores_boolean_questions(self) -> None:
        svc = _make_service()
        api = _make_api()
        api.find_step = AsyncMock(return_value=WDKStep(
            id=77,
            search_name="boolean_question_combined",
            search_config=WDKSearchConfig(parameters={}),
            record_class_name="GeneRecordClass",
        ))
        search_name, _record_type, _parameters = await svc._extract_step_search_context(
            api, step_id=77, record_type=None
        )
        assert search_name is None

    @pytest.mark.asyncio
    async def test_extract_step_search_context_returns_none_on_error(self) -> None:
        svc = _make_service()
        api = _make_api()
        api.find_step = AsyncMock(side_effect=InternalError(detail="step missing"))
        search_name, _record_type, parameters = await svc._extract_step_search_context(
            api, step_id=0, record_type=None
        )
        assert search_name is None
        assert parameters is None
