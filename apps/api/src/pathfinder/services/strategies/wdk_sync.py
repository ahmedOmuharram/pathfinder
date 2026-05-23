"""WDK sync: fetch WDK strategies and sync into the ``chats`` table.

- ``fetch_and_convert`` — fetch WDK strategy, convert to AST, normalize params
- ``sync_to_chat`` — full sync flow: fetch + upsert
- ``upsert_chat`` — create-or-update a chat from WDK strategy data
- ``upsert_summary_chat`` — create-or-update from list summary data
- ``plan_needs_detail_fetch`` — check if a chat needs WDK detail fetch
- ``lazy_fetch_wdk_detail`` — lazy-load full WDK detail for summary-only chats
- ``sync_is_saved_to_wdk`` — sync isSaved flag from chat to WDK
"""

from dataclasses import dataclass, field
from uuid import UUID

from pathfinder.domain.strategy.ast import walk_step_tree
from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.integrations.veupathdb.strategy_api import StrategyAPI
from pathfinder.integrations.veupathdb.wdk_models import WDKStrategySummary
from pathfinder.persistence.models import Conversation
from pathfinder.persistence.repositories import (
    ConversationRepository,
    ConversationUpdate,
)
from pathfinder.platform.errors import AppError, InternalError
from pathfinder.platform.logging import get_logger
from pathfinder.services.wdk import get_strategy_api

from .wdk_conversion import (
    build_snapshot_from_wdk,
    canonicalize_synced_parameters,
)

logger = get_logger(__name__)


@dataclass
class WdkChatSpec:
    """Data needed to upsert a WDK strategy chat.

    Bundles the strategy-specific fields for :func:`upsert_chat` so the
    signature stays within the six-argument limit.
    """

    wdk_id: int
    name: str
    strategy_ast: StrategyAst
    record_type: str | None
    is_saved: bool
    step_count: int = field(default=0)


def plan_needs_detail_fetch(conversation: Conversation) -> bool:
    """Check if a WDK-linked chat needs its full detail fetched from WDK.

    Returns True when the chat has a ``wdk_strategy_id`` but no plan data
    (i.e. it was synced with summary data only and the user is now opening it).
    Local strategies (no ``wdk_strategy_id``) never need a WDK fetch.
    """
    if conversation.wdk_strategy_id is None:
        return False
    ast = conversation.strategy_ast
    if not ast:
        return True
    return "root" not in ast


async def fetch_and_convert(
    api: StrategyAPI,
    wdk_id: int,
) -> tuple[StrategyAst, bool]:
    """Fetch a WDK strategy and convert to internal plan payload.

    Normalizes parameters best-effort (failures are logged and swallowed).
    Step counts and WDK step ID mappings are stored on the payload directly.

    :returns: Tuple of (StrategyAst, is_saved).
    """
    wdk_strategy = await api.get_strategy(wdk_id)

    payload, wire_by_step_id = build_snapshot_from_wdk(wdk_strategy)

    try:
        await canonicalize_synced_parameters(payload, api, wire_by_step_id)
    except AppError as exc:
        logger.warning(
            "Parameter normalization failed, storing raw values",
            wdk_id=wdk_id,
            error=str(exc),
        )

    return payload, wdk_strategy.is_saved


async def sync_to_chat(
    *,
    wdk_id: int,
    site_id: str,
    api: StrategyAPI,
    conv_repo: ConversationRepository,
    user_id: UUID,
) -> Conversation:
    """Fetch a single WDK strategy and upsert into the chats table.

    Shared by ``open_strategy`` and ``sync_all_wdk_strategies``.
    """
    payload, is_saved = await fetch_and_convert(api, wdk_id)
    name = payload.name or f"WDK Strategy {wdk_id}"

    return await upsert_chat(
        conv_repo=conv_repo,
        user_id=user_id,
        site_id=site_id,
        spec=WdkChatSpec(
            wdk_id=wdk_id,
            name=name,
            strategy_ast=payload,
            record_type=payload.record_type,
            is_saved=is_saved,
            step_count=len(walk_step_tree(payload.root)),
        ),
    )


async def upsert_chat(
    *,
    conv_repo: ConversationRepository,
    user_id: UUID,
    site_id: str,
    spec: WdkChatSpec,
) -> Conversation:
    """Upsert a WDK strategy into the chats table (create or update)."""
    existing = await conv_repo.get_by_wdk_strategy_id(user_id, spec.wdk_id)
    if existing:
        await conv_repo.update_conversation(
            existing.id,
            ConversationUpdate(
                name=spec.name,
                strategy_ast=spec.strategy_ast,
                record_type=spec.record_type,
                wdk_strategy_id=spec.wdk_id,
                wdk_strategy_id_set=True,
                is_saved=spec.is_saved,
                is_saved_set=True,
                step_count=spec.step_count,
            ),
        )
        conversation = await conv_repo.get_by_id(existing.id)
    else:
        created = await conv_repo.create(
            user_id=user_id,
            site_id=site_id,
            name=spec.name,
        )
        await conv_repo.update_conversation(
            created.id,
            ConversationUpdate(
                strategy_ast=spec.strategy_ast,
                record_type=spec.record_type,
                wdk_strategy_id=spec.wdk_id,
                wdk_strategy_id_set=True,
                is_saved=spec.is_saved,
                is_saved_set=True,
                step_count=spec.step_count,
            ),
        )
        conversation = await conv_repo.get_by_id(created.id)

    if conversation is None:
        msg = f"Conversation disappeared for WDK strategy {spec.wdk_id}"
        raise InternalError(detail=msg)
    return conversation


async def upsert_summary_chat(
    wdk_item: WDKStrategySummary,
    *,
    conv_repo: ConversationRepository,
    user_id: UUID,
    site_id: str,
) -> Conversation | None:
    """Create or update a chat from WDK list summary data only.

    Unlike ``sync_to_chat``, this does NOT fetch the full strategy detail
    from WDK. It only stores metadata available from the list endpoint.
    The ``plan`` field is left empty for new chats / preserved for existing
    ones. Full plan data is fetched lazily on first GET.
    """
    wdk_id = wdk_item.strategy_id
    name = wdk_item.name or f"WDK Strategy {wdk_id}"
    record_type = (
        wdk_item.record_class_name.strip() if wdk_item.record_class_name else None
    )
    is_saved = wdk_item.is_saved
    estimated_size = wdk_item.estimated_size
    step_count = wdk_item.leaf_and_transform_step_count

    existing = await conv_repo.get_by_wdk_strategy_id(user_id, wdk_id)
    if existing and existing.dismissed_at is not None:
        # Strategy was dismissed by user — don't re-import or update it.
        return existing
    if existing:
        await conv_repo.update_conversation(
            existing.id,
            ConversationUpdate(
                name=name,
                record_type=record_type,
                wdk_strategy_id=wdk_id,
                wdk_strategy_id_set=True,
                is_saved=is_saved,
                is_saved_set=True,
                step_count=step_count,
                estimated_size=estimated_size,
                estimated_size_set=True,
                touch_updated_at=False,
            ),
        )
        return await conv_repo.get_by_id(existing.id)

    created = await conv_repo.create(
        user_id=user_id,
        site_id=site_id,
        name=name,
    )
    await conv_repo.update_conversation(
        created.id,
        ConversationUpdate(
            record_type=record_type,
            wdk_strategy_id=wdk_id,
            wdk_strategy_id_set=True,
            is_saved=is_saved,
            is_saved_set=True,
            step_count=step_count,
            estimated_size=estimated_size,
            estimated_size_set=True,
        ),
    )
    return await conv_repo.get_by_id(created.id)


async def lazy_fetch_wdk_detail(
    *,
    conversation: Conversation,
    conv_repo: ConversationRepository,
) -> Conversation:
    """Fetch full WDK strategy detail for a summary-only chat.

    If the chat has a ``wdk_strategy_id`` but no plan data (created during
    sync-wdk to avoid N+1), fetches the full detail from WDK now and updates
    the chat. Returns the updated chat, or the original if no fetch was
    needed or the fetch failed.
    """
    site_id = conversation.site_id
    wdk_id = conversation.wdk_strategy_id
    if not plan_needs_detail_fetch(conversation) or not site_id or wdk_id is None:
        return conversation

    try:
        api = get_strategy_api(site_id)
        payload, is_saved = await fetch_and_convert(api, wdk_id)
        await conv_repo.update_conversation(
            conversation.id,
            ConversationUpdate(
                strategy_ast=payload,
                record_type=payload.record_type,
                step_count=len(walk_step_tree(payload.root)),
                is_saved=is_saved,
                is_saved_set=True,
                touch_updated_at=False,
            ),
        )
        updated = await conv_repo.get_by_id(conversation.id)
        if updated is not None:
            return updated
    except (AppError, RuntimeError) as exc:
        logger.warning(
            "Lazy WDK detail fetch failed",
            conversation_id=str(conversation.id),
            wdk_id=wdk_id,
            error=str(exc),
        )

    return conversation


async def sync_is_saved_to_wdk(*, conversation: Conversation) -> None:
    """Sync the isSaved flag from a chat to WDK.

    No-op if the chat has no wdk_strategy_id or site_id.
    Failures are logged and swallowed (non-critical sync).
    """
    wdk_id = conversation.wdk_strategy_id
    if not wdk_id:
        return

    site_id = conversation.site_id
    if not site_id:
        return

    try:
        api = get_strategy_api(site_id)
        await api.set_saved(wdk_id, is_saved=conversation.is_saved)
    except AppError as exc:
        logger.warning(
            "Failed to sync isSaved to WDK",
            conversation_id=str(conversation.id),
            wdk_id=wdk_id,
            error=str(exc),
        )
