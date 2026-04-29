"""Integration test for spec §G.1 — durable task fired from inside a
specialist mode resumes back into the same specialist node, NOT the
supervisor.

Architecture context (per recap):
    ``Conversation.specialist_mode`` is the source of truth for routing.
    It lives on the conversation row, not in the LangGraph checkpoint —
    so any code path that completes the durable task and re-runs a turn
    must still see ``specialist_mode != None`` and route via
    ``specialist_router`` to the validate / research node.

This test:

  1. Seeds a Conversation with an active validate ``specialist_mode``.
  2. Inserts a ``background_tasks`` row that simulates the durable
     ``run_control_tests_on_step`` having completed (the worker would
     transition status to ``complete`` and write a result blob).
  3. Asserts the conversation row's ``specialist_mode`` is unchanged.
  4. Asserts ``_build_turn_input`` loads the same ``SpecialistMode``
     into ``PipelineState`` for the next turn (the dispatcher's normal
     path).
  5. Asserts ``specialist_router(state)`` returns ``"validate"`` — so
     the resumed graph re-enters the validate node, not the supervisor.

Driving this through the actual procrastinate worker would add I/O
plumbing (WDK + export service mocks). The bug-class we care about is
purely the routing contract — that contract is owned by the conversation
row + ``_build_turn_input`` + ``specialist_router``, all of which we
exercise directly here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from pathfinder.ai.conversation._turn_helpers import _build_turn_input
from pathfinder.ai.conversation.request_body import ChatRequestBody
from pathfinder.ai.graph.builder import specialist_router
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.specialists.types import (
    SpecialistMode,
    ValidateContext,
)
from pathfinder.persistence.models import (
    BackgroundTask,
    Conversation,
    User,
)
from pathfinder.persistence.repositories.conversation import (
    ConversationRepository,
)
from pathfinder.persistence.session import async_session_factory


def _build_validate_specialist_mode(model_id: str) -> dict[str, Any]:
    mode = SpecialistMode(
        kind="validate",
        entered_at=datetime.now(UTC),
        model_id=model_id,
        context=ValidateContext(strategy_name="resume-test"),
    )
    return mode.model_dump(by_alias=True, mode="json")


async def _seed_conversation_with_specialist(
    user_id: UUID, conversation_id: UUID, *, model_id: str,
) -> None:
    async with async_session_factory() as session:
        session.add(User(id=user_id))
        await session.flush()
        session.add(
            Conversation(
                id=conversation_id,
                user_id=user_id,
                site_id="plasmodb",
                name="resume-test",
                step_count=1,
                specialist_mode=_build_validate_specialist_mode(model_id),
            ),
        )
        await session.commit()


async def _simulate_completed_durable_task(
    *, user_id: UUID, conversation_id: UUID,
) -> UUID:
    """Insert a ``background_tasks`` row in terminal state ``complete``.

    Mirrors the post-resume database state without invoking the worker
    (the worker test lives at ``test_control_tests_durable.py``).
    """
    task_id = uuid4()
    async with async_session_factory() as session:
        session.add(
            BackgroundTask(
                id=task_id,
                conversation_id=conversation_id,
                user_id=user_id,
                tool_name="run_control_tests_on_step",
                status="complete",
                args={
                    "args": [],
                    "kwargs": {
                        "wdk_step_id": 7,
                        "positive_controls": ["g1"],
                        "negative_controls": [],
                    },
                },
                result={"stepId": 7, "positiveIntersection": 1},
                estimated_duration_seconds=10,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            ),
        )
        await session.commit()
    return task_id


def _build_request_body(conversation_id: UUID) -> ChatRequestBody:
    return ChatRequestBody.model_validate({
        "id": str(conversation_id),
        "conversationId": str(conversation_id),
        "siteId": "plasmodb",
        "mode": "chat",
        "experimentId": None,
        "messages": [
            {
                "id": str(uuid4()),
                "role": "user",
                "parts": [{"type": "text", "text": "next turn"}],
            },
        ],
    })


@pytest.mark.asyncio
async def test_specialist_mode_survives_durable_completion_and_routes_back(
    db_cleaner: None,
    patch_app_db_engine: None,
) -> None:
    del db_cleaner, patch_app_db_engine

    user_id = uuid4()
    conversation_id = uuid4()
    model_id = "anthropic:claude-sonnet-4-6"

    await _seed_conversation_with_specialist(
        user_id, conversation_id, model_id=model_id,
    )
    await _simulate_completed_durable_task(
        user_id=user_id, conversation_id=conversation_id,
    )

    # 1. Conversation.specialist_mode is unchanged after the durable task.
    async with async_session_factory() as session:
        rows = list(
            (
                await session.execute(
                    select(Conversation).where(
                        Conversation.id == conversation_id,
                    ),
                )
            )
            .scalars()
            .all(),
        )
        assert len(rows) == 1
        conv = rows[0]
        assert conv.specialist_mode is not None
        assert conv.specialist_mode["kind"] == "validate"
        assert conv.specialist_mode["modelId"] == model_id

    # 2. The dispatcher's _build_turn_input loads it back into state.
    body = _build_request_body(conversation_id)
    async with async_session_factory() as session:
        loaded = await ConversationRepository(session).get_by_id(
            conversation_id,
        )
    assert loaded is not None
    turn_input = _build_turn_input(
        body, user_id,
        turn_message_id=uuid4(),
        turn_start_event_id=0,
        conversation=loaded,
    )
    assert turn_input["specialist_mode"] is not None

    state = PipelineState.model_validate(turn_input)

    # 3. specialist_router routes to the specialist's kind, not supervisor.
    assert state.specialist_mode is not None
    assert state.specialist_mode.kind == "validate"
    assert specialist_router(state) == "validate"
