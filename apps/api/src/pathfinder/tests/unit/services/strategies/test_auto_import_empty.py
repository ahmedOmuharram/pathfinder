"""Auto-import must not latch a conversation whose strategy returned nothing.

``gene_set_auto_imported`` is a one-way latch. If an empty result set it, the
conversation would never get a gene set even after the strategy is fixed and
re-built. Skipping without latching keeps the next build free to import.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pathfinder.persistence.models import Conversation
from pathfinder.persistence.repositories.conversation import ConversationUpdate
from pathfinder.services.gene_sets.operations import EmptyGeneSetError
from pathfinder.services.gene_sets.types import GeneSet
from pathfinder.services.gene_sets.wdk_helpers import GeneSetWdkContext
from pathfinder.services.strategies.auto_import import auto_import_gene_sets


@dataclass
class _StubRepo:
    updates: list[tuple[UUID, ConversationUpdate]] = field(default_factory=list)

    async def update_conversation(
        self,
        conversation_id: UUID,
        upd: ConversationUpdate,
    ) -> None:
        self.updates.append((conversation_id, upd))


@dataclass
class _StubGeneSetService:
    resolved: list[str]
    created: list[GeneSet] = field(default_factory=list)

    def find_by_wdk_strategy(
        self,
        _user_id: UUID,
        _wdk_strategy_id: int,
    ) -> GeneSet | None:
        return None

    async def create(
        self,
        *,
        user_id: UUID,
        name: str,
        site_id: str,
        gene_ids: list[str],
        source: str,
        wdk: GeneSetWdkContext | None = None,
    ) -> GeneSet:
        del gene_ids, wdk
        if not self.resolved:
            raise EmptyGeneSetError(name)
        gs = GeneSet(
            id=str(uuid4()),
            name=name,
            site_id=site_id,
            gene_ids=self.resolved,
            source="strategy",
            user_id=user_id,
        )
        self.created.append(gs)
        return gs

    async def flush(self, _gene_set_id: str) -> None:
        return None


def _conversation() -> Conversation:
    now = datetime.now(UTC)
    return Conversation(
        id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        name="Gametocyte markers",
        wdk_strategy_id=330517023,
        gene_set_id=None,
        gene_set_auto_imported=False,
        is_saved=False,
        step_count=1,
        imported_saved_strategy_ids=[],
        created_at=now,
        updated_at=now,
    )


async def _run(
    conversation: Conversation,
    resolved: list[str],
) -> tuple[_StubRepo, list[GeneSet]]:
    repo = _StubRepo()
    svc = _StubGeneSetService(resolved=resolved)
    created = await auto_import_gene_sets(
        [conversation],
        conv_repo=repo,  # type: ignore[arg-type]
        gene_set_service=svc,  # type: ignore[arg-type]
        site_id="plasmodb",
        user_id=conversation.user_id,
    )
    return repo, created


async def test_empty_result_creates_nothing_and_does_not_latch() -> None:
    repo, created = await _run(_conversation(), [])

    assert created == []
    assert repo.updates == []


async def test_non_empty_result_imports_and_latches() -> None:
    conversation = _conversation()
    repo, created = await _run(conversation, ["PF3D7_0100100"])

    assert len(created) == 1
    assert len(repo.updates) == 1
    conversation_id, upd = repo.updates[0]
    assert conversation_id == conversation.id
    assert upd.gene_set_auto_imported is True
    assert upd.gene_set_id == created[0].id
