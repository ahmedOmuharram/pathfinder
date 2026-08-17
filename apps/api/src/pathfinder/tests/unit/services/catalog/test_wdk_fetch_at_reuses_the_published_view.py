"""The DAG walk reads the published definition once, from the process cache.

The walk needs the published shape on every pass, to complete the context of a
metadata read. Reading it through the discovery catalog keeps that at one HTTP
GET for the whole walk, and keeps a transient failure of that GET from raising
where the contextual POST would have answered.
"""

from __future__ import annotations

import pytest

from pathfinder.domain.search import SearchContext
from pathfinder.integrations.veupathdb.wdk_models import (
    StepValidation,
    WDKSearch,
    WDKSearchResponse,
)
from pathfinder.integrations.veupathdb.wdk_parameters import (
    WDKParameter,
    WDKStringParam,
)
from pathfinder.services.catalog import param_dag as pd

_RECORD_TYPE = "transcript"
_SEARCH = "GenesByOrthologPattern"


def _param(
    name: str,
    *,
    visible: bool = True,
    allow_empty: bool = False,
    default: str | None = None,
) -> WDKParameter:
    return WDKStringParam(
        name=name,
        display_name=name,
        is_visible=visible,
        allow_empty_value=allow_empty,
        initial_display_value=default,
    )


def _published() -> WDKSearchResponse:
    parameters = [
        _param("organism"),
        _param("phyletic_indent_map", visible=False, allow_empty=True, default="[]"),
        _param("phyletic_term_map", visible=False, allow_empty=True, default="[]"),
    ]
    return WDKSearchResponse(
        search_data=WDKSearch(
            url_segment=_SEARCH,
            param_names=[p.name for p in parameters],
            parameters=parameters,
        ),
        validation=StepValidation(),
    )


class _Client:
    """Counts the reads the walk makes directly, bypassing the catalog."""

    def __init__(self) -> None:
        self.static_calls = 0
        self.contexts: list[dict[str, str]] = []

    async def get_search_details(
        self, record_type: str, search_name: str, *, expand_params: bool = True
    ) -> WDKSearchResponse:
        del record_type, search_name, expand_params
        self.static_calls += 1
        return _published()

    async def get_search_details_with_params(
        self,
        record_type: str,
        search_name: str,
        context: dict[str, str],
        *,
        expand_params: bool = True,
    ) -> WDKSearchResponse:
        del record_type, search_name, expand_params
        self.contexts.append(dict(context))
        return _published()


class _Discovery:
    """Caches per search, the way ``SearchCatalog.get_search_details`` does."""

    def __init__(self) -> None:
        self.reads = 0
        self._cache: dict[str, WDKSearchResponse] = {}

    async def get_search_details(
        self, ctx: SearchContext, *, expand_params: bool = True
    ) -> WDKSearchResponse:
        del expand_params
        key = f"{ctx.record_type}/{ctx.search_name}"
        if key not in self._cache:
            self.reads += 1
            self._cache[key] = _published()
        return self._cache[key]


@pytest.fixture
def wdk(monkeypatch: pytest.MonkeyPatch) -> tuple[_Client, _Discovery]:
    client = _Client()
    discovery = _Discovery()
    monkeypatch.setattr(pd, "get_wdk_client", lambda site_id: client)
    monkeypatch.setattr(pd, "get_discovery_service", lambda: discovery)
    return client, discovery


async def _two_passes(fetch: pd.ParamFetcher) -> None:
    await fetch({})
    await fetch({"organism": '["Plasmodium falciparum 3D7"]'})


class TestThePublishedViewIsReadOnce:
    @pytest.mark.asyncio
    async def test_the_catalog_answers_one_static_read(
        self, wdk: tuple[_Client, _Discovery]
    ) -> None:
        _, discovery = wdk

        await _two_passes(pd.wdk_fetch_at("plasmodb", _RECORD_TYPE, _SEARCH))

        assert discovery.reads == 1

    @pytest.mark.asyncio
    async def test_the_walk_never_reads_around_the_catalog(
        self, wdk: tuple[_Client, _Discovery]
    ) -> None:
        client, _ = wdk

        await _two_passes(pd.wdk_fetch_at("plasmodb", _RECORD_TYPE, _SEARCH))

        assert client.static_calls == 0


class TestThePublishedShapeCompletesTheContext:
    @pytest.mark.asyncio
    async def test_the_hidden_structural_params_are_sent(
        self, wdk: tuple[_Client, _Discovery]
    ) -> None:
        client, _ = wdk

        await _two_passes(pd.wdk_fetch_at("plasmodb", _RECORD_TYPE, _SEARCH))

        assert client.contexts == [
            {
                "organism": '["Plasmodium falciparum 3D7"]',
                "phyletic_indent_map": "[]",
                "phyletic_term_map": "[]",
            }
        ]
