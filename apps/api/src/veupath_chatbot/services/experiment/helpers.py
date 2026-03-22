"""Shared helpers for experiment execution and analysis.

Provides gene-list extraction utilities and the progress callback type alias.
"""

import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from veupath_chatbot.platform.errors import AppError, DataParsingError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.types import (
    ControlValueFormat,
    ExperimentConfig,
    GeneInfo,
)
from veupath_chatbot.services.gene_lookup.result import GeneResult
from veupath_chatbot.services.gene_lookup.wdk import resolve_gene_ids

logger = get_logger(__name__)

ProgressCallback = Callable[[JSONObject], Awaitable[None]]
"""Emits an SSE-friendly progress event dict."""


@dataclass
class ControlsContext:
    """Shared context passed to all control-evaluation functions.

    Groups the parameters that are always passed together: the WDK site,
    record type, controls search configuration, and the control gene lists.
    """

    site_id: str
    record_type: str
    controls_search_name: str
    controls_param_name: str
    controls_value_format: ControlValueFormat
    positive_controls: list[str] = field(default_factory=list)
    negative_controls: list[str] = field(default_factory=list)

    @classmethod
    def from_config(cls, config: ExperimentConfig) -> "ControlsContext":
        """Build a ControlsContext from an ExperimentConfig."""
        return cls(
            site_id=config.site_id,
            record_type=config.record_type,
            controls_search_name=config.controls_search_name,
            controls_param_name=config.controls_param_name,
            controls_value_format=config.controls_value_format,
            positive_controls=config.positive_controls or [],
            negative_controls=config.negative_controls or [],
        )


def safe_int(val: object, default: int = 0) -> int:
    """Safely convert a value to int, returning *default* on failure."""
    if isinstance(val, int):
        return val
    if isinstance(val, (float, str)):
        try:
            return int(float(val))
        except ValueError, TypeError, OverflowError:
            pass
    return default


def safe_float(val: object, default: float = 0.0) -> float:
    """Safely convert a value to float, returning *default* on failure.

    Non-finite values (``inf``, ``-inf``, ``nan``) are replaced with
    *default* because they are not JSON-serializable and PostgreSQL
    rejects them in JSON columns.
    """
    result: float
    if isinstance(val, (int, float)):
        result = float(val)
    elif isinstance(val, str):
        try:
            result = float(val)
        except ValueError:
            return default
    else:
        return default
    if not math.isfinite(result):
        return default
    return result


def extract_wdk_id(payload: object, key: str = "id") -> int | None:
    """Extract an integer ID from a WDK JSON response.

    WDK formatters (``StepFormatter``, ``StrategyService``, etc.) emit
    entity IDs as Java longs (always ``int`` in JSON) under a known key
    (typically ``"id"`` or ``"strategyId"``).

    :param payload: WDK response dict.
    :param key: JSON key containing the integer ID.
    :returns: The integer ID, or ``None`` if not found.
    """
    if isinstance(payload, dict):
        raw = payload.get(key)
        if isinstance(raw, int):
            return raw
    return None


def coerce_step_id(payload: object) -> int:
    """Extract step ID from a WDK step-creation response.

    Accepts both typed ``WDKIdentifier`` (preferred) and legacy ``JSONObject``
    dicts during the migration period.

    :param payload: WDK step-creation response.
    :returns: Step ID.
    :raises DataParsingError: If step ID not found.
    """
    # Typed model path (WDKIdentifier or any object with .id: int)
    raw_id = getattr(payload, "id", None)
    if isinstance(raw_id, int):
        return raw_id
    # Legacy dict path
    step_id = extract_wdk_id(payload)
    if step_id is None:
        msg = "Failed to extract step ID from WDK response"
        raise DataParsingError(msg)
    return step_id


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


def _enrich_list(
    genes: list[GeneInfo],
    lookup: dict[str, GeneResult],
) -> list[GeneInfo]:
    """Replace bare GeneInfo objects with enriched versions from *lookup*."""
    enriched: list[GeneInfo] = []
    for g in genes:
        meta = lookup.get(g.id)
        if meta:
            enriched.append(
                GeneInfo(
                    id=g.id,
                    name=meta.gene_name or g.name,
                    organism=meta.organism or g.organism,
                    product=meta.product or g.product,
                )
            )
        else:
            enriched.append(g)
    return enriched


async def _resolve_gene_lookup(
    site_id: str,
    gene_lists: tuple[list[GeneInfo], ...],
) -> dict[str, GeneResult]:
    """Resolve all unique gene IDs across multiple lists into a lookup dict."""
    all_ids: list[str] = []
    seen: set[str] = set()
    for gl in gene_lists:
        for g in gl:
            if g.id not in seen:
                all_ids.append(g.id)
                seen.add(g.id)

    if not all_ids:
        return {}

    resolved = await resolve_gene_ids(site_id=site_id, gene_ids=all_ids)
    if not resolved.records:
        return {}

    lookup: dict[str, GeneResult] = {}
    for rec in resolved.records:
        if rec.gene_id:
            lookup[rec.gene_id] = rec
    return lookup


async def extract_and_enrich_genes(
    *,
    site_id: str,
    result: JSONObject,
    negative_controls: list[str] | None = None,
) -> tuple[list[GeneInfo], list[GeneInfo], list[GeneInfo], list[GeneInfo]]:
    """Extract gene lists from a control-test result and enrich with WDK metadata.

    Single entry point that replaces duplicated extract + enrich blocks.

    :returns: (true_positive, false_negative, false_positive, true_negative)
    """
    tp = _extract_gene_list(result, "positive", "intersectionIds")
    fn = _extract_gene_list(result, "positive", "missingIdsSample")
    fp = _extract_gene_list(result, "negative", "intersectionIds")
    tn = _extract_gene_list(
        result,
        "negative",
        "missingIdsSample",
        fallback_from_controls=True,
        all_controls=negative_controls,
        hit_ids=_extract_id_set(result, "negative", "intersectionIds"),
    )

    try:
        lookup = await _resolve_gene_lookup(site_id, (tp, fn, fp, tn))
    except AppError as exc:
        logger.warning("Gene enrichment failed, returning bare IDs", error=str(exc))
        return tp, fn, fp, tn

    if lookup:
        tp = _enrich_list(tp, lookup)
        fn = _enrich_list(fn, lookup)
        fp = _enrich_list(fp, lookup)
        tn = _enrich_list(tn, lookup)

    return tp, fn, fp, tn
