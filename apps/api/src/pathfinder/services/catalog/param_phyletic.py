"""Phyletic pattern code lookup and semantic ranking."""

from typing import cast

from pathfinder.domain.parameters.specs import ParamSpecNormalized
from pathfinder.domain.search import SearchContext
from pathfinder.integrations.veupathdb.discovery_service import (
    get_discovery_service,
)
from pathfinder.platform.errors import AppError, ErrorCode
from pathfinder.platform.logging import get_logger
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error
from pathfinder.platform.types import JSONArray, JSONObject, JSONValue
from pathfinder.services.catalog.param_adapters import adapt_param_specs_from_search
from pathfinder.services.catalog.param_discovery import fetch_search_details
from pathfinder.services.wdk.record_types import resolve_record_type

logger = get_logger(__name__)

_MIN_VOCAB_ENTRY_LENGTH = 2
# Cap phyletic tree matches to keep the tool response concise for the LLM
# and avoid overwhelming it with hundreds of species/clade entries.
_MAX_TREE_MATCHES = 20


def _extract_phyletic_vocabs(
    specs: dict[str, ParamSpecNormalized],
) -> tuple[JSONArray, JSONArray]:
    """Extract phyletic_term_map and phyletic_indent_map vocabularies from param specs."""
    term_map_vocab: JSONArray = []
    indent_map_vocab: JSONArray = []
    term_spec = specs.get("phyletic_term_map")
    if term_spec and isinstance(term_spec.vocabulary, list):
        term_map_vocab = term_spec.vocabulary
    indent_spec = specs.get("phyletic_indent_map")
    if indent_spec and isinstance(indent_spec.vocabulary, list):
        indent_map_vocab = indent_spec.vocabulary
    return term_map_vocab, indent_map_vocab


def _build_group_codes(indent_map_vocab: JSONArray) -> set[str]:
    """Build set of group codes (non-leaf nodes) from indent map entries."""
    group_codes: set[str] = set()
    for i, entry in enumerate(indent_map_vocab):
        if not isinstance(entry, list) or len(entry) < _MIN_VOCAB_ENTRY_LENGTH:
            continue
        code = str(entry[0])
        depth = int(str(entry[1])) if entry[1] is not None else 0
        if i + 1 < len(indent_map_vocab):
            nxt = indent_map_vocab[i + 1]
            if isinstance(nxt, list) and len(nxt) >= _MIN_VOCAB_ENTRY_LENGTH:
                next_depth = int(str(nxt[1])) if nxt[1] is not None else 0
                if next_depth > depth:
                    group_codes.add(code)
    return group_codes


def _match_phyletic_entries(
    term_map_vocab: JSONArray,
    group_codes: set[str],
    query: str,
) -> list[JSONObject]:
    """Match term map entries against a query string.

    Uses the sentence-transformer biencoder to rank matches by semantic
    similarity so that e.g. "human" ranks "Homo sapiens" above
    "Pediculus humanus".
    """
    # Collect all entries.
    all_entries: list[tuple[str, str, bool]] = []
    for entry in term_map_vocab:
        if not isinstance(entry, list) or len(entry) < _MIN_VOCAB_ENTRY_LENGTH:
            continue
        code = str(entry[0])
        label = str(entry[1])
        if code == "ALL":
            continue
        is_leaf = code not in group_codes
        all_entries.append((code, label, is_leaf))

    if not all_entries:
        return []

    # Rank all entries by semantic similarity — no pre-filter.
    ranked = _rank_by_semantic_similarity(query, all_entries)
    return [
        {"code": code, "label": label, "leaf": is_leaf}
        for code, label, is_leaf in ranked[:_MAX_TREE_MATCHES]
    ]


def _rank_by_semantic_similarity(
    query: str,
    candidates: list[tuple[str, str, bool]],
) -> list[tuple[str, str, bool]]:
    """Rank candidates by biencoder cosine similarity to the query."""
    try:
        import numpy as np  # noqa: PLC0415

        from pathfinder.services.catalog.semantic_index import (  # noqa: PLC0415
            _get_model,
        )

        model = _get_model()
        query_emb = np.array(list(model.embed([query])))
        label_embs = np.array(list(model.embed([label for _, label, _ in candidates])))
        sims = (label_embs @ query_emb.T).flatten()
        ranked = sorted(
            zip(candidates, sims, strict=True), key=lambda x: -x[1]
        )
        return [c for c, _ in ranked]
    except (ImportError, OSError) as exc:
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
    """Search phyletic species codes by name for the GenesByOrthologPattern search.

    Returns matching ``{code, label}`` pairs from the ``phyletic_term_map``
    vocabulary. The model uses codes to build ``profile_pattern`` values.

    :param site_id: Site ID.
    :param record_type: Record type (usually "transcript").
    :param query: Species/clade name search term (case-insensitive substring).
    :returns: Dict with ``matches`` list and ``query`` echo.
    """
    try:
        discovery = get_discovery_service()
        record_types = await discovery.get_record_types(site_id)
        resolved = resolve_record_type(record_types, record_type) or record_type

        response, _ = await fetch_search_details(
            discovery,
            SearchContext(site_id, resolved, "GenesByOrthologPattern"),
            record_types=record_types,
        )
        spec_map = adapt_param_specs_from_search(response.search_data)
        term_map_vocab, indent_map_vocab = _extract_phyletic_vocabs(spec_map)
        group_codes = _build_group_codes(indent_map_vocab)
        matches = _match_phyletic_entries(term_map_vocab, group_codes, query)

        return {
            "query": query,
            "matches": cast("JSONValue", matches),
            "total": len(matches),
            "hint": (
                "Use codes in profile_pattern: %CODE:Y% (include) or %CODE:N% (exclude). "
                "Example: '%MAMM:N%pfal:Y%'. "
                "Group codes (leaf=false) support optional quantifier: "
                "MAMM:N:all (absent from all, default for :N), "
                "APIC:Y:any (present in any, default for :Y). "
                "Leaf codes need no quantifier."
            ),
        }
    except AppError as exc:
        return tool_error(
            ErrorCode.INTERNAL_ERROR,
            f"Failed to look up phyletic codes: {exc}",
        )
