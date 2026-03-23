"""Shared helpers for experiment execution and analysis.

Provides gene-list extraction utilities and the progress callback type alias.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.types import (
    ControlSetData,
    ControlTestResult,
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


def _ids_to_gene_infos(ids: list[str]) -> list[GeneInfo]:
    """Wrap a list of string IDs as :class:`GeneInfo` objects."""
    return [GeneInfo(id=g) for g in ids]


def _gene_infos_from_section(
    section: ControlSetData | None,
    field_name: str,
    *,
    fallback_from_controls: bool = False,
    all_controls: list[str] | None = None,
    hit_ids: set[str] | None = None,
) -> list[GeneInfo]:
    """Extract a gene list from a :class:`ControlSetData` field.

    :param section: The positive or negative control set data (may be ``None``).
    :param field_name: Attribute name on ``ControlSetData`` (e.g. ``"intersection_ids"``).
    :param fallback_from_controls: When True and the section/field is empty,
        derive the list from *all_controls* minus *hit_ids*.
    :param all_controls: Full control list for fallback computation.
    :param hit_ids: IDs that were hits (used to compute the complement for TN).
    """
    if section is not None:
        ids = getattr(section, field_name, [])
        if ids:
            return _ids_to_gene_infos(ids)

    if fallback_from_controls and all_controls and hit_ids is not None:
        return [GeneInfo(id=g) for g in all_controls if g not in hit_ids]
    return []


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
    result: ControlTestResult,
    negative_controls: list[str] | None = None,
) -> tuple[list[GeneInfo], list[GeneInfo], list[GeneInfo], list[GeneInfo]]:
    """Extract gene lists from a control-test result and enrich with WDK metadata.

    Single entry point that replaces duplicated extract + enrich blocks.

    :returns: (true_positive, false_negative, false_positive, true_negative)
    """
    tp = _gene_infos_from_section(result.positive, "intersection_ids")
    fn = _gene_infos_from_section(result.positive, "missing_ids_sample")
    fp = _gene_infos_from_section(result.negative, "intersection_ids")

    neg_hit_ids = set(result.negative.intersection_ids) if result.negative else set()
    tn = _gene_infos_from_section(
        result.negative,
        "missing_ids_sample",
        fallback_from_controls=True,
        all_controls=negative_controls,
        hit_ids=neg_hit_ids,
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
