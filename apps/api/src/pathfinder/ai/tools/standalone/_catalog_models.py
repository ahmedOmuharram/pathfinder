"""Catalog-related response models and helpers."""

from __future__ import annotations

from pydantic import Field

from pathfinder.domain.search import SearchContext
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import JSONObject
from pathfinder.services.catalog.searches import find_record_type_for_search
from pathfinder.services.wdk import WDKBaseParameter, WDKParameter

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


class DependencyEntry(CamelModel):
    """One entry in the dependency DAG."""

    depends_on: list[str] = Field(default_factory=list)
    controls: list[str] = Field(default_factory=list)
    is_required: bool = False


class DependencyDag(CamelModel):
    """Parameter dependency DAG with topological fill order."""

    fill_order: list[str] = Field(default_factory=list)
    dependencies: dict[str, DependencyEntry] = Field(default_factory=dict)


def _collect_param_edges(
    params: list[WDKParameter],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Return the depends-on and controls adjacency maps for the
    parameters."""
    depends_on: dict[str, list[str]] = {}
    controls: dict[str, list[str]] = {}
    for p in params:
        base: WDKBaseParameter = p
        if base.dependent_params:
            controls[base.name] = list(base.dependent_params)
            for dep in base.dependent_params:
                depends_on.setdefault(dep, []).append(base.name)
    return depends_on, controls


def _topological_fill_order(
    all_names: list[str],
    depends_on: dict[str, list[str]],
    controls: dict[str, list[str]],
) -> list[str]:
    """Return a topological fill order using Kahn's algorithm."""
    in_degree = {name: len(depends_on.get(name, [])) for name in all_names}
    queue = [n for n in all_names if in_degree[n] == 0]
    fill_order: list[str] = []
    while queue:
        node = queue.pop(0)
        fill_order.append(node)
        for dep in controls.get(node, []):
            if dep in in_degree:
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    queue.append(dep)
    # A cycle leaves nodes unvisited, and those go at the end.
    fill_order.extend(n for n in all_names if n not in fill_order)
    return fill_order


def _build_dependency_dag(params: list[WDKParameter]) -> DependencyDag:
    """Build a dependency DAG from WDK parameters."""
    depends_on, controls = _collect_param_edges(params)
    all_names = [p.name for p in params if p.is_visible]
    fill_order = _topological_fill_order(all_names, depends_on, controls)
    entries: dict[str, DependencyEntry] = {}
    for p in params:
        if not p.is_visible:
            continue
        base_p: WDKBaseParameter = p
        entries[base_p.name] = DependencyEntry(
            depends_on=depends_on.get(base_p.name, []),
            controls=controls.get(base_p.name, []),
            is_required=not base_p.allow_empty_value or base_p.min_selected_count >= 1,
        )
    return DependencyDag(fill_order=fill_order, dependencies=entries)


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
