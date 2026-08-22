"""``get_strategy_gene_ids`` serves only the caller's own conversation."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.persistence.models import ConversationStrategyView
from pathfinder.platform.errors import NotFoundError
from pathfinder.platform.principal import DEFAULT_APPLICATION_ID
from pathfinder.services import eval as eval_service

_OWNER = UUID(int=1)
_INTRUDER = UUID(int=2)


@pytest.fixture
def session() -> AsyncSession:
    """An unbound session; the repository under test is faked, so it is unused."""
    return AsyncSession()


@dataclass
class _Conversation:
    user_id: UUID
    strategy_view: ConversationStrategyView = field(
        default_factory=ConversationStrategyView,
    )
    application_id: str = DEFAULT_APPLICATION_ID


@dataclass
class _Repo:
    """Stands in for the conversation repository."""

    conversation: _Conversation | None

    def __call__(self, session: AsyncSession) -> _Repo:
        del session
        return self

    async def get_by_id(self, conversation_id: UUID) -> _Conversation | None:
        del conversation_id
        return self.conversation


def _wire(monkeypatch: pytest.MonkeyPatch, conversation: _Conversation | None) -> None:
    monkeypatch.setattr(eval_service, "ConversationRepository", _Repo(conversation))


async def test_another_users_conversation_is_not_found(
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
) -> None:
    _wire(
        monkeypatch,
        _Conversation(
            user_id=_OWNER,
            strategy_view=ConversationStrategyView(wdk_strategy_id=4242),
        ),
    )

    with pytest.raises(NotFoundError) as raised:
        await eval_service.get_strategy_gene_ids(
            session,
            uuid4(),
            "plasmodb",
            _INTRUDER,
        )

    assert raised.value.status == 404


async def test_missing_conversation_is_not_found(
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
) -> None:
    _wire(monkeypatch, None)

    with pytest.raises(NotFoundError) as raised:
        await eval_service.get_strategy_gene_ids(
            session,
            uuid4(),
            "plasmodb",
            _OWNER,
        )

    assert raised.value.status == 404


async def test_owner_without_a_wdk_link_keeps_the_wire_shape(
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
) -> None:
    _wire(monkeypatch, _Conversation(user_id=_OWNER))

    result = await eval_service.get_strategy_gene_ids(
        session,
        uuid4(),
        "plasmodb",
        _OWNER,
    )

    assert result.gene_ids == []
    assert result.error == "No WDK strategy linked"
    assert result.estimated_size is None
    assert result.model_dump(by_alias=True, exclude_none=True) == {
        "geneIds": [],
        "error": "No WDK strategy linked",
    }


def test_a_populated_result_serializes_to_the_documented_wire_shape() -> None:
    result = eval_service.StrategyGeneIdsResult(
        gene_ids=["PF3D7_0100100", "PF3D7_0100200"],
        estimated_size=2,
    )

    assert result.model_dump(by_alias=True, exclude_none=True) == {
        "geneIds": ["PF3D7_0100100", "PF3D7_0100200"],
        "estimatedSize": 2,
    }
