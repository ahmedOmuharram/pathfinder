from typing import Any, cast

import pytest
from pydantic import JsonValue

from pathfinder.domain.parameters.values import SinglePickValue
from pathfinder.domain.search import SearchContext
from pathfinder.integrations.veupathdb.wdk_models import (
    StepValidation,
    WDKSearch,
    WDKSearchResponse,
)
from pathfinder.integrations.veupathdb.wdk_parameters import (
    WDKEnumParam,
    WDKParameter,
)
from pathfinder.platform.errors import ValidationError
from pathfinder.platform.types import JSONObject
from pathfinder.services.catalog import param_validation as pv


def _enum_param(
    name: str,
    *,
    type_: str = "single-pick-vocabulary",
    vocab: list[list[str | None]],
    dependent_params: list[str] | None = None,
) -> WDKParameter:
    raw: JSONObject = {
        "type": type_,
        "name": name,
        "display_name": name,
        "vocabulary": cast("JsonValue", vocab),
        "dependent_params": cast("JsonValue", list(dependent_params or [])),
        "allow_empty_value": False,
    }
    return cast("WDKParameter", WDKEnumParam.model_validate(raw))


def _make_response(parameters: list[WDKParameter]) -> WDKSearchResponse:
    return WDKSearchResponse(
        search_data=WDKSearch(
            url_segment="GenesByOrganism",
            full_name="GenesByOrganism",
            display_name="Genes by organism",
            param_names=[p.name for p in parameters],
            parameters=parameters,
        ),
        validation=StepValidation(),
    )


_STATIC_TAXON_VOCAB = [
    ["TaxonA", "Taxon A", None],
    ["TaxonB", "Taxon B", None],
    ["TaxonC", "Taxon C", None],
]
_REFRESHED_TAXON_VOCAB = [["TaxonA", "Taxon A", None]]


@pytest.fixture
def stub_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    organism = _enum_param(
        "organism",
        vocab=[["Pf3D7", "P. falciparum 3D7", None], ["PvP01", "P. vivax P01", None]],
        dependent_params=["taxon"],
    )
    taxon = _enum_param("taxon", vocab=_STATIC_TAXON_VOCAB)
    static_response = _make_response([organism, taxon])

    async def _fake_expand(
        ctx: SearchContext,
        raw_context: JSONObject,
    ) -> WDKSearchResponse:
        del ctx, raw_context
        return static_response

    async def _fake_resolve_search(
        ctx: SearchContext,
        *,
        resolved_record_type: str,
        parameters: JSONObject,
    ) -> WDKSearchResponse:
        del ctx, resolved_record_type, parameters
        return static_response

    refreshed_taxon = _enum_param("taxon", vocab=_REFRESHED_TAXON_VOCAB)

    async def _fake_refresh(
        ctx: SearchContext,
        *,
        parameter_name: str,
        context_values: JSONObject,
    ) -> list[WDKParameter]:
        del ctx, context_values
        if parameter_name == "organism":
            return [refreshed_taxon]
        return []

    monkeypatch.setattr(pv, "expand_search_details_with_params", _fake_expand)
    monkeypatch.setattr(pv, "_resolve_search_details", _fake_resolve_search)
    monkeypatch.setattr(pv, "get_refreshed_dependent_params", _fake_refresh)


def _callbacks() -> pv.ValidationCallbacks:
    async def _resolve(
        record_type: str | None,
        search_name: str | None,
        *,
        require_match: bool = False,
        allow_fallback: bool = False,
    ) -> str | None:
        del search_name, require_match, allow_fallback
        return record_type

    async def _hint(search_name: str, record_type: str | None) -> str | None:
        del search_name, record_type
        return None

    return pv.ValidationCallbacks(
        resolve_record_type_for_search=_resolve,
        find_record_type_hint=_hint,
    )


@pytest.mark.asyncio
async def test_invalid_dependent_value_error_carries_refreshed_vocab(
    stub_validation: None,
) -> None:
    del stub_validation
    ctx = SearchContext(
        site_id="plasmodb",
        record_type="transcript",
        search_name="GenesByOrganism",
    )
    with pytest.raises(ValidationError) as excinfo:
        await pv.validate_parameters(
            ctx,
            parameters={
                "organism": SinglePickValue(value="Pf3D7"),
                "taxon": SinglePickValue(value="TaxonB"),
            },
            callbacks=_callbacks(),
        )

    err = excinfo.value
    assert err.errors is not None
    entry = cast("dict[str, Any]", err.errors[0])
    assert entry["param"] == "taxon"
    assert entry["value"] == "TaxonB"
    assert entry["validOptions"] == ["TaxonA"]


@pytest.mark.asyncio
async def test_missing_required_error_serializes_refreshed_spec(
    stub_validation: None,
) -> None:
    del stub_validation
    ctx = SearchContext(
        site_id="plasmodb",
        record_type="transcript",
        search_name="GenesByOrganism",
    )
    with pytest.raises(ValidationError) as excinfo:
        await pv.validate_parameters(
            ctx,
            parameters={"organism": SinglePickValue(value="Pf3D7")},
            callbacks=_callbacks(),
        )

    err = excinfo.value
    assert err.errors is not None
    raw_entry = cast("dict[str, Any]", err.errors[0])
    context = cast("dict[str, Any]", raw_entry["context"])
    assert context["missing"] == ["taxon"]
    parameters_spec = cast("list[dict[str, Any]]", context["parameters"])
    taxon_spec = next(p for p in parameters_spec if p["name"] == "taxon")
    taxon_values = [v["value"] for v in taxon_spec["allowedValues"]]
    assert taxon_values == ["TaxonA"]


def _hidden_parent(name: str, *, default: str, dependents: list[str]) -> WDKParameter:
    raw: JSONObject = {
        "type": "single-pick-vocabulary",
        "name": name,
        "display_name": name,
        "vocabulary": cast("JsonValue", [[default, default, None]]),
        "dependent_params": cast("JsonValue", list(dependents)),
        "allow_empty_value": False,
        "is_visible": False,
        "initial_display_value": default,
    }
    return cast("WDKParameter", WDKEnumParam.model_validate(raw))


class TestHiddenParentIsFilledBeforeRefresh:
    """A hidden parent's default must be present when its child refreshes.

    Live failure: `samples_percentile_generic` declares
    `depends_on: ["profileset_generic", "channel"]`. `channel` is
    `is_visible=False`, required, with `initial_display_value="Channel 1"`,
    so `fill_hidden_required_defaults` supplies it -- but that ran *after*
    `_refresh_dependent_vocabularies`, which skips any parent whose value is
    empty. The child never refreshed against the channel dimension, and 13
    DeRisi time points WDK accepts (a non-empty result) were reported invalid.
    """

    @pytest.fixture
    def stub_with_hidden_parent(self, monkeypatch: pytest.MonkeyPatch) -> list[str]:
        refreshed_parents: list[str] = []

        channel = _hidden_parent("channel", default="Channel 1", dependents=["samples"])
        samples = _enum_param(
            "samples", type_="multi-pick-vocabulary", vocab=_STATIC_TAXON_VOCAB
        )
        response = _make_response([channel, samples])

        async def _fake_expand(
            ctx: SearchContext, raw_context: JSONObject
        ) -> WDKSearchResponse:
            del ctx, raw_context
            return response

        async def _fake_resolve_search(
            ctx: SearchContext, *, resolved_record_type: str, parameters: JSONObject
        ) -> WDKSearchResponse:
            del ctx, resolved_record_type, parameters
            return response

        async def _fake_refresh(
            ctx: SearchContext, *, parameter_name: str, context_values: JSONObject
        ) -> list[WDKParameter]:
            del ctx, context_values
            refreshed_parents.append(parameter_name)
            return []

        monkeypatch.setattr(pv, "expand_search_details_with_params", _fake_expand)
        monkeypatch.setattr(pv, "_resolve_search_details", _fake_resolve_search)
        monkeypatch.setattr(pv, "get_refreshed_dependent_params", _fake_refresh)
        return refreshed_parents

    @pytest.mark.asyncio
    async def test_the_hidden_parent_triggers_a_refresh(
        self, stub_with_hidden_parent: list[str]
    ) -> None:
        # The caller never mentions `channel` -- exactly what the model sends.
        await pv.validate_parameters(
            SearchContext("plasmodb", "transcript", "GenesByMicroarray"),
            parameters={"samples": SinglePickValue(value="TaxonA")},
            callbacks=_callbacks(),
        )

        assert "channel" in stub_with_hidden_parent, (
            "a hidden parent with a default must be filled before its child's "
            "vocabulary is refreshed"
        )

    @pytest.mark.asyncio
    async def test_the_filled_default_reaches_the_result(
        self, stub_with_hidden_parent: list[str]
    ) -> None:
        del stub_with_hidden_parent
        out = await pv.validate_parameters(
            SearchContext("plasmodb", "transcript", "GenesByMicroarray"),
            parameters={"samples": SinglePickValue(value="TaxonA")},
            callbacks=_callbacks(),
        )

        assert "channel" in out.params
