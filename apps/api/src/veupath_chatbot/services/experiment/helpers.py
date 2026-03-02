"""Shared helpers for experiment execution and analysis.

Provides gene-list extraction utilities and the progress callback type alias.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.types import GeneInfo

ProgressCallback = Callable[[JSONObject], Awaitable[None]]
"""Emits an SSE-friendly progress event dict."""


def _extract_gene_list(
    result: JSONObject,
    section: str,
    key: str,
    *,
    fallback_from_controls: bool = False,
    all_controls: list[str] | None = None,
    hit_ids: set[str] | None = None,
) -> list[GeneInfo]:
    """Extract a gene ID list from control-test result and wrap as GeneInfo."""
    section_data = result.get(section)
    if not isinstance(section_data, dict):
        if fallback_from_controls and all_controls and hit_ids is not None:
            return [GeneInfo(id=g) for g in all_controls if g not in hit_ids]
        return []

    ids_raw = section_data.get(key)
    if isinstance(ids_raw, list):
        return [GeneInfo(id=str(g)) for g in ids_raw if g is not None]

    if fallback_from_controls and all_controls and hit_ids is not None:
        return [GeneInfo(id=g) for g in all_controls if g not in hit_ids]
    return []


def _extract_id_set(
    result: JSONObject,
    section: str,
    key: str,
) -> set[str]:
    """Extract a set of IDs from a control-test result section."""
    section_data = result.get(section)
    if not isinstance(section_data, dict):
        return set()
    ids_raw = section_data.get(key)
    if isinstance(ids_raw, list):
        return {str(g) for g in ids_raw if g is not None}
    return set()
