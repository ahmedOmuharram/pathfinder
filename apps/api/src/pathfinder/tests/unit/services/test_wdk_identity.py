"""The guest-identity seam: without a browser-supplied WDK token, every
container (api, worker) used to drift into its own ephemeral WDK guest via
its cookie jar, so strategies created during a chat turn (worker) returned
403 when edited through the api. ``ensure_wdk_identity`` converges all
components on ONE durable guest token persisted per PathFinder user.
"""

from collections.abc import AsyncGenerator, Generator
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pathfinder.persistence.repositories.user import UserRepository
from pathfinder.platform.context import veupathdb_auth_token_ctx
from pathfinder.services import wdk_identity


@pytest.fixture
async def session(
    session_maker: async_sessionmaker[AsyncSession],
    db_cleaner: None,
) -> AsyncGenerator[AsyncSession]:
    del db_cleaner
    async with session_maker() as s:
        yield s


@pytest.fixture(autouse=True)
def clean_ctx() -> Generator[None]:
    token = veupathdb_auth_token_ctx.set(None)
    yield
    veupathdb_auth_token_ctx.reset(token)


async def test_noop_when_browser_token_present(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    veupathdb_auth_token_ctx.set("real-user-token")

    async def explode(site_id: str) -> str | None:
        msg = "must not mint when a token is already present"
        raise AssertionError(msg)

    monkeypatch.setattr(wdk_identity, "mint_guest_token", explode)
    await wdk_identity.ensure_wdk_identity(session, uuid4())
    assert veupathdb_auth_token_ctx.get() == "real-user-token"


async def test_reuses_persisted_guest_token(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = UserRepository(session)
    user = await repo.create()
    await repo.set_wdk_guest_token(user.id, "persisted-guest-token")
    await session.commit()

    async def explode(site_id: str) -> str | None:
        msg = "must not mint when a persisted token exists"
        raise AssertionError(msg)

    monkeypatch.setattr(wdk_identity, "mint_guest_token", explode)
    await wdk_identity.ensure_wdk_identity(session, user.id)
    assert veupathdb_auth_token_ctx.get() == "persisted-guest-token"


async def test_mints_and_persists_when_missing(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = UserRepository(session)
    user = await repo.create()
    await session.commit()

    async def fake_mint(site_id: str) -> str | None:
        return "fresh-guest-token"

    monkeypatch.setattr(wdk_identity, "mint_guest_token", fake_mint)
    await wdk_identity.ensure_wdk_identity(session, user.id)

    assert veupathdb_auth_token_ctx.get() == "fresh-guest-token"
    refetched = await repo.get_by_id(user.id)
    assert refetched is not None
    assert refetched.wdk_guest_token == "fresh-guest-token"


async def test_mint_failure_leaves_ctx_unset(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = UserRepository(session)
    user = await repo.create()
    await session.commit()

    async def failing_mint(site_id: str) -> str | None:
        return None

    monkeypatch.setattr(wdk_identity, "mint_guest_token", failing_mint)
    await wdk_identity.ensure_wdk_identity(session, user.id)

    assert veupathdb_auth_token_ctx.get() is None
    refetched = await repo.get_by_id(user.id)
    assert refetched is not None
    assert refetched.wdk_guest_token is None


async def test_unknown_user_is_a_noop(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_mint(site_id: str) -> str | None:
        return "fresh-guest-token"

    monkeypatch.setattr(wdk_identity, "mint_guest_token", fake_mint)
    await wdk_identity.ensure_wdk_identity(session, uuid4())
    assert veupathdb_auth_token_ctx.get() is None
