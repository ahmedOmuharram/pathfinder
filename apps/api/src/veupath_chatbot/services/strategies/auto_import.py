"""Auto-import gene sets for WDK-linked strategy projections.

When strategies are synced from WDK, eligible projections automatically
get a gene set created and linked. Once imported (or once the user deletes
the auto-imported gene set), the projection is marked so re-syncs don't
recreate it.
"""

from uuid import UUID

from veupath_chatbot.persistence.models import StreamProjection
from veupath_chatbot.persistence.repositories.stream import StreamRepository
from veupath_chatbot.persistence.session import async_session_factory
from veupath_chatbot.platform.errors import AppError, InternalError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.services.gene_sets import GeneSet, GeneSetService
from veupath_chatbot.services.gene_sets.store import get_gene_set_store

logger = get_logger(__name__)


def _is_eligible(proj: StreamProjection) -> bool:
    """Check if a projection is eligible for gene set auto-import.

    Eligible when:
    - Has a WDK strategy ID (is a WDK-linked strategy)
    - Has not been auto-imported before (one-way latch)
    - Does not already have a linked gene set
    """
    return (
        proj.wdk_strategy_id is not None
        and not proj.gene_set_auto_imported
        and proj.gene_set_id is None
    )


async def auto_import_gene_sets(
    projections: list[StreamProjection],
    *,
    stream_repo: StreamRepository,
    gene_set_service: GeneSetService,
    site_id: str,
    user_id: UUID,
) -> list[GeneSet]:
    """Create gene sets for eligible strategy projections.

    For each eligible projection (has wdk_strategy_id, not yet imported,
    no existing gene set), creates a gene set and links it to the projection.

    Returns the list of newly created gene sets.
    """
    created: list[GeneSet] = []

    # Track WDK strategy IDs we've already processed in this batch
    # to prevent concurrent background tasks from creating duplicates.
    seen_wdk_ids: set[int] = set()

    for proj in projections:
        if not _is_eligible(proj):
            continue

        wdk_id = proj.wdk_strategy_id
        if wdk_id is None:
            msg = "wdk_id must not be None (guaranteed by _is_eligible)"
            raise InternalError(detail=msg)

        # Skip if already processed in this batch.
        if wdk_id in seen_wdk_ids:
            continue
        seen_wdk_ids.add(wdk_id)

        # Skip if a gene set already exists for this WDK strategy (from a
        # concurrent background task or previous partial import).
        existing = gene_set_service.find_by_wdk_strategy(user_id, wdk_id)
        if existing:
            # Link to the existing gene set instead of creating a new one.
            await stream_repo.update_projection(
                proj.stream_id,
                gene_set_id=existing.id,
                gene_set_id_set=True,
                gene_set_auto_imported=True,
            )
            continue

        try:
            gs = await gene_set_service.create(
                user_id=user_id,
                name=proj.name or f"WDK Strategy {wdk_id}",
                site_id=site_id,
                gene_ids=[],
                source="strategy",
                wdk_strategy_id=wdk_id,
                record_type=proj.record_type,
            )
            # Ensure gene set row exists in DB before setting the FK.
            await gene_set_service.flush(gs.id)
            await stream_repo.update_projection(
                proj.stream_id,
                gene_set_id=gs.id,
                gene_set_id_set=True,
                gene_set_auto_imported=True,
            )
            created.append(gs)
            logger.info(
                "Auto-imported gene set for strategy",
                gene_set_id=gs.id,
                wdk_strategy_id=wdk_id,
                gene_count=len(gs.gene_ids),
            )
        except (AppError, ValueError, TypeError, KeyError, RuntimeError) as exc:
            logger.warning(
                "Failed to auto-import gene set for strategy",
                wdk_strategy_id=wdk_id,
                error=str(exc),
            )

    return created


async def background_auto_import_gene_sets(
    *,
    site_id: str,
    user_id: UUID,
) -> None:
    """Run gene-set auto-import in a background task with its own DB session.

    This avoids blocking the sync-wdk response while WDK API calls
    resolve gene IDs for each eligible strategy.
    """
    async with async_session_factory() as session:
        try:
            repo = StreamRepository(session)
            projections = await repo.list_projections(user_id, site_id)
            gene_set_svc = GeneSetService(get_gene_set_store())
            await auto_import_gene_sets(
                projections,
                stream_repo=repo,
                gene_set_service=gene_set_svc,
                site_id=site_id,
                user_id=user_id,
            )
            await session.commit()
        except (AppError, ValueError, TypeError, KeyError, RuntimeError) as e:
            await session.rollback()
            logger.warning(
                "Background gene set auto-import failed",
                site_id=site_id,
                error=str(e),
            )
