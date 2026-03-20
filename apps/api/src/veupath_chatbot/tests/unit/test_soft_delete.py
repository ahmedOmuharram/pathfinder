"""Unit tests for soft-delete (dismiss/restore) repository operations."""

from uuid import UUID

import pytest

from veupath_chatbot.persistence.repositories.stream import (
    ProjectionUpdate,
    StreamRepository,
)


class TestDismissProjection:
    @pytest.mark.asyncio
    async def test_dismiss_sets_dismissed_at(
        self,
        stream_repo: StreamRepository,
        user_id: UUID,
    ) -> None:
        """Dismissing a projection sets dismissed_at to a non-null datetime."""
        stream = await stream_repo.create(
            user_id=user_id, site_id="plasmodb", name="Test"
        )
        await stream_repo.update_projection(
            stream.id,
            ProjectionUpdate(wdk_strategy_id=100, wdk_strategy_id_set=True),
        )

        await stream_repo.dismiss(stream.id)

        proj = await stream_repo.get_projection(stream.id)
        assert proj is not None
        assert proj.dismissed_at is not None

    @pytest.mark.asyncio
    async def test_dismiss_is_idempotent(
        self,
        stream_repo: StreamRepository,
        user_id: UUID,
    ) -> None:
        """Dismissing twice doesn't fail."""
        stream = await stream_repo.create(
            user_id=user_id, site_id="plasmodb", name="Test"
        )
        await stream_repo.dismiss(stream.id)
        await stream_repo.dismiss(stream.id)

        proj = await stream_repo.get_projection(stream.id)
        assert proj is not None
        assert proj.dismissed_at is not None


class TestRestoreProjection:
    @pytest.mark.asyncio
    async def test_restore_clears_dismissed_at(
        self,
        stream_repo: StreamRepository,
        user_id: UUID,
    ) -> None:
        """Restoring a dismissed projection clears dismissed_at."""
        stream = await stream_repo.create(
            user_id=user_id, site_id="plasmodb", name="Test"
        )
        await stream_repo.dismiss(stream.id)
        await stream_repo.restore(stream.id)

        proj = await stream_repo.get_projection(stream.id)
        assert proj is not None
        assert proj.dismissed_at is None

    @pytest.mark.asyncio
    async def test_restore_resets_plan(
        self,
        stream_repo: StreamRepository,
        user_id: UUID,
    ) -> None:
        """Restoring resets plan to {} for lazy re-fetch from WDK."""
        stream = await stream_repo.create(
            user_id=user_id, site_id="plasmodb", name="Test"
        )
        await stream_repo.update_projection(
            stream.id,
            ProjectionUpdate(
                plan={"root": {"searchName": "test"}},
                wdk_strategy_id=100,
                wdk_strategy_id_set=True,
            ),
        )
        await stream_repo.dismiss(stream.id)
        await stream_repo.restore(stream.id)

        proj = await stream_repo.get_projection(stream.id)
        assert proj is not None
        assert proj.plan == {}

    @pytest.mark.asyncio
    async def test_restore_resets_message_count(
        self,
        stream_repo: StreamRepository,
        user_id: UUID,
    ) -> None:
        """Restoring resets message_count to 0."""
        stream = await stream_repo.create(
            user_id=user_id, site_id="plasmodb", name="Test"
        )
        await stream_repo.dismiss(stream.id)
        await stream_repo.restore(stream.id)

        proj = await stream_repo.get_projection(stream.id)
        assert proj is not None
        assert proj.message_count == 0


class TestListProjectionsExcludesDismissed:
    @pytest.mark.asyncio
    async def test_list_excludes_dismissed(
        self,
        stream_repo: StreamRepository,
        user_id: UUID,
    ) -> None:
        """list_projections excludes dismissed strategies by default."""
        s1 = await stream_repo.create(
            user_id=user_id, site_id="plasmodb", name="Active"
        )
        s2 = await stream_repo.create(
            user_id=user_id, site_id="plasmodb", name="Dismissed"
        )
        await stream_repo.dismiss(s2.id)

        projections = await stream_repo.list_projections(user_id, "plasmodb")
        ids = {p.stream_id for p in projections}
        assert s1.id in ids
        assert s2.id not in ids

    @pytest.mark.asyncio
    async def test_list_dismissed_only(
        self,
        stream_repo: StreamRepository,
        user_id: UUID,
    ) -> None:
        """list_dismissed_projections returns only dismissed strategies."""
        s1 = await stream_repo.create(
            user_id=user_id, site_id="plasmodb", name="Active"
        )
        s2 = await stream_repo.create(
            user_id=user_id, site_id="plasmodb", name="Dismissed"
        )
        await stream_repo.dismiss(s2.id)

        dismissed = await stream_repo.list_dismissed_projections(user_id, "plasmodb")
        ids = {p.stream_id for p in dismissed}
        assert s2.id in ids
        assert s1.id not in ids
