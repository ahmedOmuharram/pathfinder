"""Duplicating a conversation must carry the strategy over, not just messages.

The earlier ``duplicate`` copied messages + events but left the new
conversation's ``strategy_ast`` empty. A duplicate is only useful if it brings
the strategy (topology + params); WDK step ids are dropped so the copy
re-syncs as its own fresh WDK strategy rather than sharing the source's steps.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from pathfinder.persistence.models import Conversation, User
from pathfinder.persistence.repositories.conversation import ConversationRepository
from pathfinder.persistence.repositories.message import MessagesRepository
from pathfinder.platform.db import async_session_factory
from pathfinder.services.conversations.service import ConversationService

_AST = {
    "root": {
        "id": "kinases",
        "searchName": "GenesByText",
        "parameters": {"text_expression": {"type": "string", "value": "kinase"}},
    },
    "wdkStepIds": {"kinases": 9999},
}


@pytest.mark.asyncio
async def test_duplicate_copies_strategy_dropping_wdk_ids(
    db_cleaner: None,
    patch_app_db_engine: None,
) -> None:
    del db_cleaner, patch_app_db_engine
    user_id = uuid4()
    conv_id = uuid4()

    async with async_session_factory() as session:
        session.add(User(id=user_id))
        await session.flush()
        repo = ConversationRepository(session)
        conv = await repo.create(
            user_id=user_id,
            site_id="plasmodb",
            conversation_id=conv_id,
            name="Kinase strategy",
        )
        conv.strategy_ast = dict(_AST)
        conv.wdk_strategy_id = 555
        await MessagesRepository(session).insert_message(
            message_id=uuid4(),
            conversation_id=conv_id,
            role="user",
            metadata={},
        )
        await session.commit()

    async with async_session_factory() as session:
        dup = await ConversationService(session).duplicate(conv_id, user_id)

    assert dup.id != conv_id
    assert dup.name == "Copy of Kinase strategy"

    async with async_session_factory() as session:
        new = await session.scalar(
            select(Conversation).where(Conversation.id == dup.id),
        )
        assert new is not None
        root = new.strategy_ast.get("root")
        assert isinstance(root, dict)
        assert root.get("id") == "kinases"
        assert root.get("searchName") == "GenesByText"
        params = root.get("parameters")
        assert isinstance(params, dict)
        text_expr = params.get("text_expression")
        assert isinstance(text_expr, dict)
        assert text_expr.get("value") == "kinase"
        assert "wdkStepIds" not in new.strategy_ast
        assert new.wdk_strategy_id is None

        original = await session.scalar(
            select(Conversation).where(Conversation.id == conv_id),
        )
        assert original is not None
        assert original.wdk_strategy_id == 555
