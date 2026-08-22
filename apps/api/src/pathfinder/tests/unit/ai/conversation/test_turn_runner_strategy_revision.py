"""Every assistant turn is stamped with the strategy state it described.

Without the stamp a transcript reporting "2,862 transcripts at fold-change 1"
keeps reading as current after the threshold is edited to 2 and the strategy
returns 587. The stamp is the only thing the UI can compare against the live
revision to mark those numbers historical.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from pathfinder.ai.conversation import turn_runner
from pathfinder.ai.graph.stream_events import strategy_revision_event
from pathfinder.domain.strategy.revision import strategy_revision
from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.persistence.models import Conversation, ConversationStrategy


@dataclass
class _StubWriter:
    turn_id: UUID
    chunks: list[dict[str, Any]] = field(default_factory=list)

    async def write(self, chunk: dict[str, Any]) -> int:
        self.chunks.append(chunk)
        return len(self.chunks)


def _ast(fold_change: str = "1") -> StrategyAst:
    return StrategyAst.model_validate(
        {
            "recordType": "transcript",
            "root": {
                "id": "step_a",
                "searchName": "GenesByRNASeqEvidence",
                "parameters": {
                    "fold_change": {"type": "string", "value": fold_change},
                },
            },
        },
    )


def _conversation(ast: StrategyAst | None) -> Conversation:
    now = datetime.now(UTC)
    conversation = Conversation(
        id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        name="Gametocyte markers",
        created_at=now,
        updated_at=now,
    )
    conversation.strategy = ConversationStrategy(
        conversation_id=conversation.id,
        is_saved=False,
        step_count=1,
        gene_set_auto_imported=False,
        imported_saved_strategy_ids=[],
        estimated_size=None,
        strategy_ast=(
            ast.model_dump(by_alias=True, exclude_none=True, mode="json")
            if ast is not None
            else {}
        ),
    )
    return conversation


def _install_conversation(
    monkeypatch: pytest.MonkeyPatch,
    conversation: Conversation | None,
) -> None:
    class _Session:
        async def __aenter__(self) -> _Session:
            return self

        async def __aexit__(self, *_exc: object) -> None:
            return None

    class _Repo:
        def __init__(self, _session: _Session) -> None:
            return None

        async def get_by_id(self, _conversation_id: UUID) -> Conversation | None:
            return conversation

    monkeypatch.setattr(turn_runner, "async_session_factory", _Session)
    monkeypatch.setattr(turn_runner, "ConversationRepository", _Repo)


def test_event_payload_carries_the_revision() -> None:
    chunk = strategy_revision_event(revision="abc123")
    assert chunk.type == "data-strategy-revision"
    assert chunk.data == {"revision": "abc123"}
    # Persisted, not transient: the stamp must survive a page reload.
    assert chunk.transient is not True


async def test_turn_is_stamped_with_the_live_strategy_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_conversation(monkeypatch, _conversation(_ast("2")))
    writer = _StubWriter(turn_id=uuid4())

    await turn_runner._emit_strategy_revision(
        writer=writer,
        conversation_id=uuid4(),
    )

    assert writer.chunks == [
        {
            "type": "data-strategy-revision",
            "data": {"revision": strategy_revision(_ast("2"))},
        },
    ]


async def test_a_turn_with_no_strategy_is_not_stamped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_conversation(monkeypatch, _conversation(None))
    writer = _StubWriter(turn_id=uuid4())

    await turn_runner._emit_strategy_revision(writer=writer, conversation_id=uuid4())

    assert writer.chunks == []


async def test_a_missing_conversation_is_not_stamped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_conversation(monkeypatch, None)
    writer = _StubWriter(turn_id=uuid4())

    await turn_runner._emit_strategy_revision(writer=writer, conversation_id=uuid4())

    assert writer.chunks == []
