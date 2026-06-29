"""Gene set business logic.

All domain operations on gene sets live here. The transport layer
(HTTP router) delegates to this module for create, delete, list,
set operations, enrichment, and step-results access.
"""

from uuid import UUID, uuid4

from pathfinder.domain.parameters.values import ParamValue
from pathfinder.integrations.veupathdb.factory import (
    get_strategy_api,
)
from pathfinder.integrations.veupathdb.wdk_models import (
    WDKStrategyDetails,
)
from pathfinder.platform.errors import (
    InternalError,
    NotFoundError,
    ValidationError,
)
from pathfinder.platform.logging import get_logger
from pathfinder.services.enrichment.service import EnrichmentService
from pathfinder.services.enrichment.types import (
    EnrichmentAnalysisType,
    EnrichmentResult,
)
from pathfinder.services.gene_sets.store import GeneSetStore
from pathfinder.services.gene_sets.types import GeneSet, GeneSetSource
from pathfinder.services.gene_sets.wdk_helpers import (
    GeneSetWdkContext,
    build_enrichment_params_from_gene_ids,
    resolve_wdk_context,
)
from pathfinder.services.wdk.step_results import StepResultsService

logger = get_logger(__name__)


def _dedup_ordered(gene_ids: list[str]) -> list[str]:
    """Gene IDs with duplicates removed, preserving first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for gid in gene_ids:
        if gid not in seen:
            seen.add(gid)
            out.append(gid)
    return out


class GeneSetService:
    """Orchestrates all gene-set domain operations.

    Depends on the gene-set store and (lazily) on WDK APIs.
    The transport layer should instantiate this once per request
    or hold a singleton.
    """

    def __init__(self, store: GeneSetStore) -> None:
        self._store = store

    # -- Persistence ----------------------------------------------------------

    async def flush(self, gene_set_id: str) -> None:
        """Ensure a gene set is persisted to the database.

        The default save path is fire-and-forget. Call this when you need
        the row to exist in the DB immediately (e.g., before setting an FK).
        """
        entity = self._store.get(gene_set_id)
        if entity is not None:
            await self._store._persist(entity)

    # -- Lookup / ownership ---------------------------------------------------

    async def get_for_user(self, user_id: UUID, gene_set_id: str) -> GeneSet:
        """Retrieve a gene set, raising NotFoundError if not found or wrong owner."""
        gs = await self._store.aget(gene_set_id)
        if gs is None or gs.user_id != user_id:
            msg = f"Gene set not found: {gene_set_id}"
            raise NotFoundError(detail=msg)
        return gs

    # -- CRUD -----------------------------------------------------------------

    async def create(
        self,
        *,
        user_id: UUID,
        name: str,
        site_id: str,
        gene_ids: list[str],
        source: GeneSetSource,
        wdk: GeneSetWdkContext | None = None,
    ) -> GeneSet:
        """Create a gene set, auto-resolving from WDK if needed."""
        ctx = wdk or GeneSetWdkContext()
        gene_ids, ctx, step_count = await resolve_wdk_context(site_id, gene_ids, ctx)
        unique_gene_ids = _dedup_ordered(gene_ids)

        gs = GeneSet(
            id=str(uuid4()),
            name=name,
            site_id=site_id,
            gene_ids=unique_gene_ids,
            source=source,
            user_id=user_id,
            wdk_strategy_id=ctx.wdk_strategy_id,
            wdk_step_id=ctx.wdk_step_id,
            search_name=ctx.search_name,
            record_type=ctx.record_type,
            parameters=ctx.parameters,
            step_count=step_count,
        )
        self._store.save(gs)
        logger.info(
            "Gene set created",
            gene_set_id=gs.id,
            name=gs.name,
            gene_count=len(gs.gene_ids),
        )
        return gs

    async def resync_strategy(
        self, gene_set_id: str, *, wdk_strategy_id: int, site_id: str
    ) -> GeneSet | None:
        """Re-resolve a strategy-linked gene set from the (possibly rebuilt) WDK
        strategy, replacing its stored snapshot. Passes NO step id so the CURRENT
        root step is resolved — a rebuild can create a new root under the same
        strategy id — which fixes a set left stale after a re-run changed the
        result. Returns the updated set, or ``None`` if it no longer exists."""
        gs = await self._store.aget(gene_set_id)
        if gs is None:
            return None
        gene_ids, ctx, step_count = await resolve_wdk_context(
            site_id,
            [],
            GeneSetWdkContext(
                wdk_strategy_id=wdk_strategy_id, record_type=gs.record_type
            ),
        )
        gs.gene_ids = _dedup_ordered(gene_ids)
        gs.wdk_strategy_id = ctx.wdk_strategy_id
        gs.wdk_step_id = ctx.wdk_step_id
        gs.step_count = step_count
        self._store.save(gs)
        logger.info(
            "Re-synced strategy gene set",
            gene_set_id=gs.id,
            gene_count=len(gs.gene_ids),
        )
        return gs

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        site_id: str | None = None,
    ) -> list[GeneSet]:
        """List gene sets for a user, optionally filtered by site."""
        return await self._store.alist_for_user(user_id, site_id=site_id)

    def find_by_wdk_strategy(
        self, user_id: UUID, wdk_strategy_id: int
    ) -> GeneSet | None:
        """Find an existing gene set for a WDK strategy (cache lookup)."""
        for gs in self._store._cache.values():
            if gs.user_id == user_id and gs.wdk_strategy_id == wdk_strategy_id:
                return gs
        return None

    async def delete(self, user_id: UUID, gene_set_id: str) -> None:
        """Delete a gene set, raising NotFoundError if not found or wrong owner."""
        await self.get_for_user(user_id, gene_set_id)
        if not self._store.delete(gene_set_id):
            msg = f"Gene set not found: {gene_set_id}"
            raise NotFoundError(detail=msg)
        logger.info("Gene set deleted", gene_set_id=gene_set_id)

    # -- Set operations -------------------------------------------------------

    async def perform_set_operation(
        self,
        *,
        user_id: UUID,
        set_a_id: str,
        set_b_id: str,
        operation: str,
        name: str,
    ) -> GeneSet:
        """Perform a set operation (intersect, union, minus) between two gene sets."""
        set_a = await self.get_for_user(user_id, set_a_id)
        set_b = await self.get_for_user(user_id, set_b_id)

        ids_a = set(set_a.gene_ids)
        ids_b = set(set_b.gene_ids)

        match operation:
            case "intersect":
                result_ids = ids_a & ids_b
            case "union":
                result_ids = ids_a | ids_b
            case "minus":
                result_ids = ids_a - ids_b
            case _:
                msg = f"Invalid operation: must be 'intersect', 'union', or 'minus', got '{operation}'"
                raise ValidationError(detail=msg)

        gs = GeneSet(
            id=str(uuid4()),
            name=name,
            site_id=set_a.site_id,
            gene_ids=sorted(result_ids),
            source="derived",
            user_id=user_id,
            parent_set_ids=[set_a.id, set_b.id],
            operation=operation,
        )
        self._store.save(gs)
        logger.info(
            "Gene set derived via set operation",
            gene_set_id=gs.id,
            operation=operation,
            gene_count=len(gs.gene_ids),
        )
        return gs

    # -- Enrichment -----------------------------------------------------------

    async def run_enrichment(
        self,
        user_id: UUID,
        gene_set_id: str,
        enrichment_types: list[EnrichmentAnalysisType],
    ) -> list[EnrichmentResult]:
        """Run enrichment analysis on a gene set."""
        gs = await self.get_for_user(user_id, gene_set_id)

        step_id = gs.wdk_step_id
        search_name = gs.search_name
        record_type = gs.record_type or "transcript"
        enrichment_params: dict[str, ParamValue] | None = (
            dict(gs.parameters) if gs.parameters else None
        )

        # Paste gene sets have gene IDs but no WDK step or search.
        # Create a temporary WDK dataset so enrichment can run via GeneByLocusTag.
        if step_id is None and not search_name and gs.gene_ids:
            (
                search_name,
                enrichment_params,
                record_type,
            ) = await build_enrichment_params_from_gene_ids(gs.site_id, gs.gene_ids)

        svc = EnrichmentService()
        results, errors = await svc.run_batch(
            site_id=gs.site_id,
            analysis_types=enrichment_types,
            step_id=step_id,
            search_name=search_name,
            record_type=record_type,
            parameters=enrichment_params,
        )

        if not results and errors:
            msg = "Enrichment analysis failed: " + "; ".join(errors)
            raise InternalError(detail=msg)
        return results

    # -- Step results access --------------------------------------------------

    async def get_step_results_service(
        self, user_id: UUID, gene_set_id: str
    ) -> StepResultsService:
        """Get a StepResultsService for a gene set.

        Raises ValidationError if the gene set has no associated WDK step.
        """
        gs = await self.get_for_user(user_id, gene_set_id)
        if not gs.wdk_step_id:
            msg = (
                "No WDK strategy: this gene set has no associated WDK strategy "
                "for result browsing."
            )
            raise ValidationError(detail=msg)
        api = get_strategy_api(gs.site_id)
        return StepResultsService(
            api, step_id=gs.wdk_step_id, record_type=gs.record_type or "transcript"
        )

    async def get_strategy_tree(
        self, user_id: UUID, gene_set_id: str
    ) -> tuple[GeneSet, WDKStrategyDetails]:
        """Get the WDK strategy tree for a gene set.

        Returns the gene set and the strategy tree dict.
        Raises ValidationError if no WDK strategy is associated.
        """
        gs = await self.get_for_user(user_id, gene_set_id)
        if not gs.wdk_strategy_id:
            msg = "No WDK strategy: this gene set has no associated WDK strategy."
            raise ValidationError(detail=msg)
        if not gs.wdk_step_id:
            msg = (
                "No WDK strategy: this gene set has no associated WDK strategy "
                "for result browsing."
            )
            raise ValidationError(detail=msg)
        api = get_strategy_api(gs.site_id)
        svc = StepResultsService(
            api, step_id=gs.wdk_step_id, record_type=gs.record_type or "transcript"
        )
        tree = await svc.get_strategy(gs.wdk_strategy_id)
        return gs, tree
