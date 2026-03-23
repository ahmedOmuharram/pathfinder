"""Gene set business logic.

All domain operations on gene sets live here. The transport layer
(HTTP router) delegates to this module for create, delete, list,
set operations, enrichment, and step-results access.
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

from veupath_chatbot.integrations.veupathdb.factory import (
    get_strategy_api,
)
from veupath_chatbot.integrations.veupathdb.strategy_api.api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKDatasetConfigIdList,
    WDKDatasetIdListContent,
    WDKStrategyDetails,
)
from veupath_chatbot.platform.errors import (
    AppError,
    InternalError,
    NotFoundError,
    ValidationError,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.enrichment.service import EnrichmentService
from veupath_chatbot.services.enrichment.types import (
    EnrichmentAnalysisType,
    EnrichmentResult,
)
from veupath_chatbot.services.gene_sets.store import GeneSetStore
from veupath_chatbot.services.gene_sets.types import GeneSet, GeneSetSource
from veupath_chatbot.services.wdk.helpers import extract_record_ids
from veupath_chatbot.services.wdk.step_results import StepResultsService

logger = get_logger(__name__)

SetOperation = Literal["intersect", "union", "minus"]


@dataclass
class GeneSetWdkContext:
    """Optional WDK-related context for gene set creation."""

    wdk_strategy_id: int | None = None
    wdk_step_id: int | None = None
    search_name: str | None = None
    record_type: str | None = None
    parameters: dict[str, str] | None = None


# ---------------------------------------------------------------------------
# WDK helpers (async, take an API instance)
# ---------------------------------------------------------------------------


async def _build_enrichment_params_from_gene_ids(
    site_id: str,
    gene_ids: list[str],
) -> tuple[str, JSONObject, str]:
    """Create a WDK dataset from gene IDs and return enrichment parameters.

    Returns ``(search_name, parameters, record_type)`` suitable for passing
    to ``EnrichmentService.run_batch()``.  Uses the ``GeneByLocusTag`` search
    (transcript record type) with a temporary WDK dataset.
    """
    api = get_strategy_api(site_id)
    config = WDKDatasetConfigIdList(
        source_type="idList",
        source_content=WDKDatasetIdListContent(ids=gene_ids),
    )
    dataset_id = await api.create_dataset(config)
    return (
        "GeneByLocusTag",
        {"ds_gene_ids": str(dataset_id)},
        "transcript",
    )


async def resolve_root_step_id(api: StrategyAPI, *, strategy_id: int) -> int | None:
    """Get the root step ID from a WDK strategy."""
    strategy = await api.get_strategy(strategy_id)
    return strategy.root_step_id


async def fetch_gene_ids_from_step(api: StrategyAPI, *, step_id: int) -> list[str]:
    """Fetch all gene IDs from a WDK step via the standard report endpoint."""
    answer = await api.get_step_answer(
        step_id,
        attributes=["primary_key"],
        pagination={"offset": 0, "numRecords": -1},
    )
    return extract_record_ids(answer.records)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


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

    async def _resolve_wdk_context(
        self,
        site_id: str,
        gene_ids: list[str],
        ctx: GeneSetWdkContext,
    ) -> tuple[list[str], GeneSetWdkContext, int]:
        """Resolve gene IDs and search context from a WDK strategy.

        Returns ``(gene_ids, updated_ctx, step_count)``.
        """
        wdk_strategy_id = ctx.wdk_strategy_id
        if gene_ids or wdk_strategy_id is None:
            return gene_ids, ctx, 1

        api = get_strategy_api(site_id)
        wdk_step_id = ctx.wdk_step_id
        search_name = ctx.search_name
        record_type = ctx.record_type
        parameters = ctx.parameters
        step_count = 1

        wdk_step_id = await self._resolve_root_step(api, wdk_strategy_id, wdk_step_id)
        gene_ids = await self._fetch_step_genes(api, wdk_step_id)
        step_count = await self._count_strategy_steps(api, wdk_strategy_id)

        if wdk_step_id is not None and search_name is None and step_count == 1:
            (
                search_name,
                record_type,
                parameters,
            ) = await self._extract_step_search_context(api, wdk_step_id, record_type)

        updated = GeneSetWdkContext(
            wdk_strategy_id=wdk_strategy_id,
            wdk_step_id=wdk_step_id,
            search_name=search_name,
            record_type=record_type,
            parameters=parameters,
        )
        return gene_ids, updated, step_count

    async def _resolve_root_step(
        self, api: StrategyAPI, strategy_id: int, step_id: int | None
    ) -> int | None:
        if step_id is not None:
            return step_id
        try:
            resolved = await resolve_root_step_id(api, strategy_id=strategy_id)
        except AppError as exc:
            logger.warning(
                "Failed to resolve root step from strategy",
                strategy_id=strategy_id,
                error=str(exc),
            )
            return step_id
        else:
            logger.info(
                "Resolved root step from strategy",
                strategy_id=strategy_id,
                step_id=resolved,
            )
            return resolved

    async def _fetch_step_genes(
        self, api: StrategyAPI, step_id: int | None
    ) -> list[str]:
        if step_id is None:
            return []
        try:
            gene_ids = await fetch_gene_ids_from_step(api, step_id=step_id)
        except AppError as exc:
            logger.warning(
                "Failed to fetch gene IDs from WDK step",
                step_id=step_id,
                error=str(exc),
            )
            return []
        else:
            logger.info(
                "Fetched gene IDs from WDK step",
                step_id=step_id,
                gene_count=len(gene_ids),
            )
            return gene_ids

    async def _count_strategy_steps(self, api: StrategyAPI, strategy_id: int) -> int:
        try:
            strategy = await api.get_strategy(strategy_id)
            return len(strategy.steps)
        except AppError as exc:
            logger.warning(
                "Failed to count strategy steps",
                strategy_id=strategy_id,
                error=str(exc),
            )
            return 1

    async def _extract_step_search_context(
        self,
        api: StrategyAPI,
        step_id: int,
        record_type: str | None,
    ) -> tuple[str | None, str | None, dict[str, str] | None]:
        """Extract searchName, recordType, parameters from a WDK step."""
        search_name: str | None = None
        parameters: dict[str, str] | None = None
        try:
            step = await api.find_step(step_id)
            sn = step.search_name
            if not sn.startswith("boolean_question_"):
                search_name = sn
                parameters = dict(step.search_config.parameters)
            if not record_type:
                rcn = step.record_class_name
                if rcn:
                    record_type = (
                        rcn.split(".")[-1].replace("RecordClass", "").lower()
                        if "." in rcn
                        else "transcript"
                    )
            logger.info(
                "Extracted search context from WDK step",
                step_id=step_id,
                search_name=search_name,
                has_params=parameters is not None,
            )
        except AppError as exc:
            logger.warning(
                "Failed to extract search context from step",
                step_id=step_id,
                error=str(exc),
            )
        return search_name, record_type, parameters

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
        gene_ids, ctx, step_count = await self._resolve_wdk_context(
            site_id, gene_ids, ctx
        )

        # Deduplicate gene IDs while preserving order
        seen: set[str] = set()
        unique_gene_ids: list[str] = []
        for gid in gene_ids:
            if gid not in seen:
                seen.add(gid)
                unique_gene_ids.append(gid)

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
        enrichment_params: JSONObject | None = None
        if gs.parameters:
            params: JSONObject = {}
            params.update(gs.parameters)
            enrichment_params = params

        # Paste gene sets have gene IDs but no WDK step or search.
        # Create a temporary WDK dataset so enrichment can run via GeneByLocusTag.
        if step_id is None and not search_name and gs.gene_ids:
            (
                search_name,
                enrichment_params,
                record_type,
            ) = await _build_enrichment_params_from_gene_ids(gs.site_id, gs.gene_ids)

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
