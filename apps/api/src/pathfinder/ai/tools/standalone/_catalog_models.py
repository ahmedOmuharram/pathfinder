"""Catalog-related response models and helpers."""

from __future__ import annotations

from assistant_core.platform.types import JSONObject

from pathfinder.ai.agents.state import AgentToolState, SearchOverview
from pathfinder.domain.search import SearchContext
from pathfinder.services.catalog.searches import find_record_type_for_search
from pathfinder.services.wdk import WDKParameter, WDKSearch, get_wdk_client

_UNIVERSAL_SEARCHES: list[JSONObject] = [
    {
        "name": "GenesByText",
        "displayName": "Gene Text Search",
        "description": "Search all text fields for genes matching a keyword or phrase.",
        "category": "general",
        "returns": "transcript",
        "relevanceScore": 0.0,
    },
]


def _filter_vocab(param: WDKParameter, query: str) -> WDKParameter:
    """Filter a parameter vocabulary by a case-insensitive substring."""
    q = query.lower()
    vocab = param.vocabulary
    if vocab is None:
        return param

    if isinstance(vocab, list):
        filtered = [v for v in vocab if q in str(v).lower()]
        return param.model_copy(update={"vocabulary": filtered})

    if isinstance(vocab, dict):
        filtered_dict = {
            k: v for k, v in vocab.items() if q in str(k).lower() or q in str(v).lower()
        }
        return param.model_copy(update={"vocabulary": filtered_dict})

    return param


def _search_overview_of(search: WDKSearch, record_type: str) -> SearchOverview:
    """The discovery-gate entry for a search, from its expanded WDK definition."""
    visible = [p for p in search.parameters or [] if p.is_visible]
    return SearchOverview(
        search_name=search.url_segment,
        display_name=search.display_name or search.url_segment,
        record_type=record_type,
        description=search.description or search.summary,
        parameter_names=[p.name for p in visible],
        required_params=[
            p.name
            for p in visible
            if not p.allow_empty_value or p.min_selected_count >= 1
        ],
    )


async def read_search_definition(
    site_id: str, record_type: str, search_name: str
) -> WDKSearch:
    """The expanded WDK definition of one search: its metadata and parameters."""
    details = await get_wdk_client(site_id).get_search_details(
        record_type, search_name, expand_params=True
    )
    return details.search_data


def register_search(state: AgentToolState, search: WDKSearch, record_type: str) -> None:
    """Register a search in the discovery gate when nothing registered it yet."""
    if state.get_overview(search.url_segment) is not None:
        return
    state.register_search(search.url_segment, _search_overview_of(search, record_type))


async def ensure_search_registered(
    state: AgentToolState, site_id: str, record_type: str, search_name: str
) -> None:
    """Register a search the caller holds no definition for.

    The definition is read only when the discovery gate has no entry yet.
    """
    if state.get_overview(search_name) is not None:
        return
    definition = await read_search_definition(site_id, record_type, search_name)
    register_search(state, definition, record_type)


async def _resolve_record_type(
    site_id: str,
    search_name: str,
    record_type: str | None,
) -> str:
    """Return the record type of a search."""
    if record_type:
        return record_type
    ctx = SearchContext(
        site_id=site_id, search_name=search_name, record_type="transcript"
    )
    return await find_record_type_for_search(ctx)
