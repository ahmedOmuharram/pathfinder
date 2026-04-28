from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from pathfinder.persistence.models import User
from pathfinder.persistence.session import async_session_factory
from pathfinder.services.user_preferences import (
    UnknownModelError,
    set_specialist_default,
)

VALID_HAIKU = "anthropic:claude-haiku-4-5"
VALID_SONNET = "anthropic:claude-sonnet-4-6"


async def _read_defaults(user_id: UUID) -> dict[str, str]:
    async with async_session_factory() as session:
        raw = await session.scalar(
            select(User.specialist_model_defaults).where(User.id == user_id),
        )
    return dict(raw) if raw else {}


@pytest.mark.asyncio
async def test_set_specialist_default_persists_value(
    db_cleaner: None, patch_app_db_engine: None,
) -> None:
    del db_cleaner, patch_app_db_engine
    user_id = uuid4()
    async with async_session_factory() as session:
        session.add(User(id=user_id))
        await session.commit()

    async with async_session_factory() as session:
        await set_specialist_default(
            session,
            user_id=user_id,
            command="validate",
            model_id=VALID_SONNET,
        )
        await session.commit()

    assert await _read_defaults(user_id) == {"validate": VALID_SONNET}


@pytest.mark.asyncio
async def test_set_specialist_default_overwrites_existing(
    db_cleaner: None, patch_app_db_engine: None,
) -> None:
    del db_cleaner, patch_app_db_engine
    user_id = uuid4()
    async with async_session_factory() as session:
        session.add(User(id=user_id))
        await session.commit()

    async with async_session_factory() as session:
        await set_specialist_default(
            session, user_id=user_id, command="validate", model_id=VALID_HAIKU,
        )
        await set_specialist_default(
            session, user_id=user_id, command="research", model_id=VALID_HAIKU,
        )
        await set_specialist_default(
            session, user_id=user_id, command="validate", model_id=VALID_SONNET,
        )
        await session.commit()

    assert await _read_defaults(user_id) == {
        "validate": VALID_SONNET,
        "research": VALID_HAIKU,
    }


@pytest.mark.asyncio
async def test_set_specialist_default_rejects_unknown_model(
    db_cleaner: None, patch_app_db_engine: None,
) -> None:
    del db_cleaner, patch_app_db_engine
    user_id = uuid4()
    async with async_session_factory() as session:
        session.add(User(id=user_id))
        await session.commit()

    async with async_session_factory() as session:
        with pytest.raises(UnknownModelError):
            await set_specialist_default(
                session,
                user_id=user_id,
                command="optimize",
                model_id="nonsense:model",
            )
