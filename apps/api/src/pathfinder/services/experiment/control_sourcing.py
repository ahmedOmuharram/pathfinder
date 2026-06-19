"""Build control gene lists for scored experiments from any source.

A scored experiment needs positive/negative control gene-id lists. In a chat,
the Lead sources these from: pasted text, an uploaded CSV/TSV file, a saved
workbench gene set, or another strategy's results. This module normalizes all
of those to validated ``list[str]`` and persists a ControlSet.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.services.eval import get_strategy_gene_ids
from pathfinder.services.gene_lookup.wdk import resolve_gene_ids
from pathfinder.services.gene_sets.operations import GeneSetService
from pathfinder.services.gene_sets.store import get_gene_set_store

_ID_SPLIT_RE = re.compile(r"[\s,;\t]+")


def parse_gene_id_blob(raw: str) -> list[str]:
    """Parse pasted / CSV / TSV text into a deduped list of gene IDs.

    Splits on whitespace, commas, semicolons, and tabs; strips quotes; drops
    a ``gene_id`` header token. Order-preserving dedup.
    """
    seen: set[str] = set()
    out: list[str] = []
    for tok in _ID_SPLIT_RE.split(raw):
        cleaned = tok.strip().strip('"').strip("'")
        if cleaned == "" or cleaned.lower() == "gene_id":
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


@dataclass
class ResolvedControls:
    """Outcome of validating raw gene IDs against WDK."""

    valid_ids: list[str] = field(default_factory=list)
    unresolved_ids: list[str] = field(default_factory=list)


async def validate_control_ids(
    site_id: str,
    gene_ids: list[str],
    *,
    record_type: str = "transcript",
) -> ResolvedControls:
    """Validate gene IDs against WDK, splitting recognized from unresolved.

    Lets the Lead warn the user about typos/aliases before using a list as
    controls. Order-preserving and deduped.
    """
    cleaned = [g.strip() for g in gene_ids if g.strip()]
    deduped = list(dict.fromkeys(cleaned))
    if not deduped:
        return ResolvedControls()
    result = await resolve_gene_ids(site_id, deduped, record_type=record_type)
    recognized = {r.gene_id for r in result.records}
    return ResolvedControls(
        valid_ids=[g for g in deduped if g in recognized],
        unresolved_ids=[g for g in deduped if g not in recognized],
    )


async def control_ids_from_saved_gene_set(
    user_id: UUID,
    gene_set_id: str,
) -> list[str]:
    """Pull the gene-id list out of a saved workbench gene set."""
    service = GeneSetService(get_gene_set_store())
    gene_set = await service.get_for_user(user_id, gene_set_id)
    return list(gene_set.gene_ids)


@dataclass
class StrategyControls:
    """Gene IDs imported from another strategy's results."""

    gene_ids: list[str] = field(default_factory=list)
    error: str | None = None


async def control_ids_from_strategy(
    session: AsyncSession,
    strategy_id: UUID,
    site_id: str,
) -> StrategyControls:
    """Import a strategy's result gene IDs (to use as positive or negative
    controls). Returns an error message rather than raising when the strategy
    has no linked WDK results."""
    result = await get_strategy_gene_ids(session, strategy_id, site_id)
    error = result.get("error")
    gene_ids = result.get("geneIds", [])
    ids = [str(g) for g in gene_ids] if isinstance(gene_ids, list) else []
    return StrategyControls(
        gene_ids=ids,
        error=str(error) if error else None,
    )
