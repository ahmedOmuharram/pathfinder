"""Phyletic code lookup, and the binding the two species lists derive."""

from collections.abc import Mapping, Sequence
from typing import cast

import numpy as np
from assistant_core.embeddings.model import get_embedding_model
from assistant_core.platform.logging import get_logger
from assistant_core.platform.types import JSONObject
from pydantic import BaseModel, Field, JsonValue

from pathfinder.domain.parameters.phyletic import (
    NO_CONSTRAINT_PATTERN,
    PhyleticBinding,
    PhyleticTree,
    PhyleticUnresolved,
    derive_binding,
)
from pathfinder.domain.parameters.wdk_vocab import (
    MAX_NEAREST_ENTRIES,
    nearest_entries,
)
from pathfinder.domain.search import SearchContext
from pathfinder.integrations.veupathdb.discovery_service import (
    get_discovery_service,
)
from pathfinder.integrations.veupathdb.phyletic_tree import phyletic_tree_of
from pathfinder.integrations.veupathdb.wdk_parameters import WDKParameter
from pathfinder.platform.errors import AppError, ErrorCode
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error
from pathfinder.services.catalog.param_discovery import fetch_search_details
from pathfinder.services.catalog.param_formatting import (
    PHYLETIC_LIST_PARAMS,
    ParameterInfo,
)
from pathfinder.services.wdk.record_types import resolve_record_type

logger = get_logger(__name__)

# The tree holds hundreds of entries, so the response returns only the best matches.
_MAX_TREE_MATCHES = 20

_PATTERN_PARAM = "profile_pattern"

PhyleticProposals = Mapping[str, str | list[str] | None]

LOOKUP_HINT = (
    "Put a code or its label in included_species (an ortholog must be present) "
    "or in excluded_species (it must be absent). A code with leaf=false is a "
    "clade and selects every species under it. profile_pattern is derived from "
    "the two lists; never write it."
)


class PhyleticUnresolvedProposal(BaseModel):
    """Why a pair of species lists binds nothing, and the entries nearest to them."""

    unresolved: PhyleticUnresolved
    nearest: list[str] = Field(default_factory=list)


class PhyleticNoSelection(BaseModel):
    """Neither list selects a species, so the criterion constrains nothing.

    The bare wildcard is a valid pattern and returns every gene of the chosen
    organisms, which reads as a phyletic answer and is not one.
    """


PhyleticDerivation = PhyleticBinding | PhyleticUnresolvedProposal | PhyleticNoSelection


def is_phyletic_sheet(infos: list[ParameterInfo]) -> bool:
    """Whether this sheet belongs to a phyletic search.

    The sheet drops the two structural maps, so the pattern and the two lists are
    the names that identify the search here. What the call proposes is not part
    of the signature: naming neither list is itself an empty selection.
    """
    names = {info.name for info in infos}
    return {_PATTERN_PARAM, *PHYLETIC_LIST_PARAMS} <= names


def _nearest_entries(tree: PhyleticTree, unknown: Sequence[str]) -> list[str]:
    """The codes and labels closest to the terms that named nothing."""
    options = tree.labels()
    found: list[str] = []
    for term in unknown:
        for match in nearest_entries(options, term, MAX_NEAREST_ENTRIES):
            if match not in found:
                found.append(match)
    return found[:MAX_NEAREST_ENTRIES]


def derive_phyletic_overrides(
    definition_params: list[WDKParameter], proposals: PhyleticProposals
) -> PhyleticDerivation | None:
    """The three parameter values a proposal of the two species lists states.

    ``None`` means the derivation does not apply, because the search is not
    phyletic. A list left null, and a list the call never names, both count as
    the empty selection, and two empty selections state no criterion at all.
    """
    tree = phyletic_tree_of(definition_params)
    if tree is None:
        return None
    if not PHYLETIC_LIST_PARAMS & proposals.keys():
        return PhyleticNoSelection()
    binding = derive_binding(
        tree,
        proposals.get("included_species") or "",
        proposals.get("excluded_species") or "",
    )
    if isinstance(binding, PhyleticUnresolved):
        return PhyleticUnresolvedProposal(
            unresolved=binding,
            nearest=_nearest_entries(
                tree, [*binding.included_unknown, *binding.excluded_unknown]
            ),
        )
    if binding.profile_pattern == NO_CONSTRAINT_PATTERN:
        return PhyleticNoSelection()
    return binding


def _match_phyletic_entries(tree: PhyleticTree, query: str) -> list[JSONObject]:
    """Ranks the clade tree nodes against a query by semantic similarity.

    A node with children is a group, so it expands to its species.
    """
    all_entries = [(node.code, node.label, not node.children) for node in tree.nodes()]
    if not all_entries:
        return []

    ranked = _rank_by_semantic_similarity(query, all_entries)
    return [
        {"code": code, "label": label, "leaf": is_leaf}
        for code, label, is_leaf in ranked[:_MAX_TREE_MATCHES]
    ]


def _rank_by_semantic_similarity(
    query: str,
    candidates: list[tuple[str, str, bool]],
) -> list[tuple[str, str, bool]]:
    """Ranks the candidates by cosine similarity to the query.

    The embedding model loads its weights on first use, so an unreachable cache
    leaves the candidates in tree order.
    """
    try:
        model = get_embedding_model()
        query_emb = np.array(list(model.embed([query])))
        label_embs = np.array(list(model.embed([label for _, label, _ in candidates])))
        sims = (label_embs @ query_emb.T).flatten()
        ranked = sorted(zip(candidates, sims, strict=True), key=lambda x: -x[1])
        return [c for c, _ in ranked]
    except OSError as exc:
        logger.warning(
            "Biencoder ranking unavailable, returning unranked results",
            error=str(exc),
            query=query,
            num_candidates=len(candidates),
        )
        return candidates


async def lookup_phyletic_codes(
    site_id: str,
    record_type: str,
    query: str,
) -> JSONObject | ToolErrorPayload:
    """Searches the phyletic species and clade codes by name. The model puts a
    returned code in ``included_species`` or ``excluded_species``, and
    ``profile_pattern`` is derived from those two lists."""
    try:
        discovery = get_discovery_service()
        record_types = await discovery.get_record_types(site_id)
        resolved = resolve_record_type(record_types, record_type) or record_type

        response, _ = await fetch_search_details(
            SearchContext(site_id, resolved, "GenesByOrthologPattern"),
            record_types=record_types,
        )
        tree = phyletic_tree_of(response.search_data.parameters or [])
        matches = _match_phyletic_entries(tree, query) if tree is not None else []

        return {
            "query": query,
            "matches": cast("JsonValue", matches),
            "total": len(matches),
            "hint": LOOKUP_HINT,
        }
    except AppError as exc:
        return tool_error(
            ErrorCode.INTERNAL_ERROR,
            f"Failed to look up phyletic codes: {exc}",
        )
