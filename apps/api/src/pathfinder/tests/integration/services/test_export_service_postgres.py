from __future__ import annotations

from uuid import uuid4

import pytest

from pathfinder.persistence.models import User
from pathfinder.platform.db import async_session_factory
from pathfinder.services.export.service import ExportService


@pytest.mark.asyncio
async def test_store_and_retrieve_postgres_export(
    db_cleaner: None, patch_app_db_engine: None
) -> None:
    del db_cleaner, patch_app_db_engine
    user_id = uuid4()
    async with async_session_factory() as session:
        session.add(User(id=user_id))
        await session.commit()

    svc = ExportService(session_factory=async_session_factory)
    export_id = await svc.store(
        user_id=user_id,
        filename="out.tsv",
        content_type="text/tab-separated-values",
        data=b"col1\tcol2\nx\ty\n",
    )
    fetched = await svc.get_export(export_id=export_id, user_id=user_id)
    assert fetched is not None
    assert fetched.filename == "out.tsv"
    assert fetched.data == b"col1\tcol2\nx\ty\n"
