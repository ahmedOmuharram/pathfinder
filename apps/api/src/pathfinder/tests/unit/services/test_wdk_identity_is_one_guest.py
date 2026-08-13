"""A request with no credential is answered as a brand new guest.

WDK never rejects it, so one token must be minted once and reused. Minting
per request makes every request a different person.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.platform.context import veupathdb_auth_token_ctx
from pathfinder.services import wdk_identity

_USER = UUID(int=1)
_SESSION = AsyncSession()


@dataclass
class _User:
    wdk_guest_token: str | None = None


@dataclass
class _Repo:
    """Stands in for the user repository, counting the writes."""

    user: _User
    writes: list[str] = field(default_factory=list)

    def __call__(self, session: AsyncSession) -> _Repo:
        del session
        return self

    async def get_by_id(self, user_id: UUID) -> _User:
        del user_id
        return self.user

    async def set_wdk_guest_token(self, user_id: UUID, token: str) -> None:
        del user_id
        self.user.wdk_guest_token = token
        self.writes.append(token)


@dataclass
class _Mint:
    """Counts how often WDK was asked for a new guest."""

    calls: int = 0

    async def __call__(self, site_id: str) -> str:
        del site_id
        self.calls += 1
        return f"guest-token-{self.calls}"


@pytest.fixture(autouse=True)
def _clear_token() -> None:
    veupathdb_auth_token_ctx.set(None)


def _wire(monkeypatch: pytest.MonkeyPatch, user: _User) -> tuple[_Repo, _Mint]:
    repo = _Repo(user)
    mint = _Mint()
    monkeypatch.setattr(wdk_identity, "UserRepository", repo)
    monkeypatch.setattr(wdk_identity, "mint_guest_token", mint)
    return repo, mint


class TestOneIdentityPerUser:
    @pytest.mark.asyncio
    async def test_the_first_call_mints_and_persists(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo, mint = _wire(monkeypatch, _User())

        await wdk_identity.ensure_wdk_identity(_SESSION, _USER)

        assert mint.calls == 1
        assert repo.writes == ["guest-token-1"]

    @pytest.mark.asyncio
    async def test_the_second_call_does_not_mint_again(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A second mint would be a second guest, owning none of the first's work.
        _, mint = _wire(monkeypatch, _User())

        await wdk_identity.ensure_wdk_identity(_SESSION, _USER)
        veupathdb_auth_token_ctx.set(None)
        await wdk_identity.ensure_wdk_identity(_SESSION, _USER)

        assert mint.calls == 1

    @pytest.mark.asyncio
    async def test_both_calls_carry_the_same_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _wire(monkeypatch, _User())

        await wdk_identity.ensure_wdk_identity(_SESSION, _USER)
        first = veupathdb_auth_token_ctx.get()
        veupathdb_auth_token_ctx.set(None)
        await wdk_identity.ensure_wdk_identity(_SESSION, _USER)

        assert veupathdb_auth_token_ctx.get() == first

    @pytest.mark.asyncio
    async def test_a_persisted_token_is_reused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _, mint = _wire(monkeypatch, _User(wdk_guest_token="stored-token"))

        await wdk_identity.ensure_wdk_identity(_SESSION, _USER)

        assert mint.calls == 0
        assert veupathdb_auth_token_ctx.get() == "stored-token"


class TestARealLoginIsNotReplaced:
    @pytest.mark.asyncio
    async def test_a_request_token_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, mint = _wire(monkeypatch, _User())
        veupathdb_auth_token_ctx.set("real-user-token")

        await wdk_identity.ensure_wdk_identity(_SESSION, uuid4())

        assert mint.calls == 0
        assert veupathdb_auth_token_ctx.get() == "real-user-token"
