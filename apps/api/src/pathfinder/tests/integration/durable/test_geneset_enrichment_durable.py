from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from pathfinder.ai.tools.durable import TaskProgressEmitter
from pathfinder.jobs.impls import geneset_enrichment_impl, register_all_tools
from pathfinder.jobs.impls.geneset_enrichment_impl import (
    run_gene_set_enrichment_impl,
)
from pathfinder.jobs.registry import TOOL_REGISTRY
from pathfinder.jobs.runner import run_durable_task
from pathfinder.persistence.models import (
    BackgroundTask,
    Conversation,
    GeneSetRow,
    TaskProgress,
    User,
)
from pathfinder.persistence.repositories.background_tasks import (
    BackgroundTaskRepository,
)
from pathfinder.persistence.session import async_session_factory
from pathfinder.services.gene_sets.types import GeneSet


async def _seed_user_chat(user_id: UUID, conversation_id: UUID) -> None:
    async with async_session_factory() as session:
        session.add(User(id=user_id))
        await session.flush()
        session.add(
            Conversation(id=conversation_id, user_id=user_id, site_id="plasmodb", name="")
        )
        await session.commit()


async def _seed_gene_set(
    gene_set_id: str, user_id: UUID, gene_ids: list[str]
) -> None:
    async with async_session_factory() as session:
        session.add(
            GeneSetRow(
                id=gene_set_id,
                user_id=user_id,
                site_id="plasmodb",
                name="test gene set",
                gene_ids=gene_ids,
                source="paste",
                wdk_step_id=5,
                record_type="transcript",
            )
        )
        await session.commit()


class _FakeContext:
    def __init__(self, site_id: str) -> None:
        self.site_id = site_id


async def _fake_run_enrichment(
    gene_set: GeneSet, analysis_types: list[str]
) -> dict[str, Any]:
    return {
        "analysisTypesRun": list(analysis_types),
        "totalSignificantTerms": 3,
        "enrichmentResults": [],
        "geneSetId": gene_set.id,
        "geneSetName": gene_set.name,
        "geneCount": len(gene_set.gene_ids),
    }


def test_geneset_enrichment_registered_in_registry() -> None:
    register_all_tools()
    assert "geneset_enrichment" in TOOL_REGISTRY
    assert TOOL_REGISTRY["geneset_enrichment"] is run_gene_set_enrichment_impl


@pytest.mark.asyncio
async def test_geneset_enrichment_impl_emits_progress(
    db_cleaner: None,
    patch_app_db_engine: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del db_cleaner, patch_app_db_engine

    monkeypatch.setattr(
        geneset_enrichment_impl,
        "run_enrichment_for_gene_set",
        _fake_run_enrichment,
    )

    user_id = uuid4()
    conversation_id = uuid4()
    task_id = uuid4()
    gs_id = uuid4().hex[:12]
    await _seed_user_chat(user_id, conversation_id)
    await _seed_gene_set(gs_id, user_id, ["PF3D7_1", "PF3D7_2"])

    async with async_session_factory() as session:
        session.add(
            BackgroundTask(
                id=task_id,
                conversation_id=conversation_id,
                user_id=user_id,
                tool_name="geneset_enrichment",
                status="running",
                args={},
                estimated_duration_seconds=120,
            )
        )
        await session.commit()

    progress = TaskProgressEmitter(
        task_id=task_id,
        conversation_id=conversation_id,
        session_factory=async_session_factory,
    )

    result = await run_gene_set_enrichment_impl(
        context=_FakeContext(site_id="plasmodb"),
        task_id=task_id,
        progress=progress,
        memory_store=None,
        gene_set_id=gs_id,
        enrichment_types=["go_function", "pathway"],
    )

    assert isinstance(result, dict)
    assert result["geneSetId"] == gs_id
    assert result["analysisTypesRun"] == ["go_function", "pathway"]

    async with async_session_factory() as session:
        rows = list(
            (
                await session.execute(
                    select(TaskProgress)
                    .where(TaskProgress.task_id == task_id)
                    .order_by(TaskProgress.id)
                )
            ).scalars()
        )
    assert len(rows) >= 2
    assert rows[0].percent <= rows[-1].percent
    assert rows[-1].percent == 1.0


@pytest.mark.asyncio
async def test_geneset_enrichment_impl_missing_gene_set(
    db_cleaner: None,
    patch_app_db_engine: None,
) -> None:
    del db_cleaner, patch_app_db_engine
    user_id = uuid4()
    conversation_id = uuid4()
    task_id = uuid4()
    await _seed_user_chat(user_id, conversation_id)

    async with async_session_factory() as session:
        session.add(
            BackgroundTask(
                id=task_id,
                conversation_id=conversation_id,
                user_id=user_id,
                tool_name="geneset_enrichment",
                status="running",
                args={},
                estimated_duration_seconds=120,
            )
        )
        await session.commit()

    progress = TaskProgressEmitter(
        task_id=task_id,
        conversation_id=conversation_id,
        session_factory=async_session_factory,
    )

    with pytest.raises(LookupError, match="does not exist"):
        await run_gene_set_enrichment_impl(
            context=_FakeContext(site_id="plasmodb"),
            task_id=task_id,
            progress=progress,
            memory_store=None,
            gene_set_id="nope",
        )


@pytest.mark.asyncio
async def test_run_durable_task_wiring_geneset_enrichment(
    db_cleaner: None,
    patch_app_db_engine: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del db_cleaner, patch_app_db_engine

    monkeypatch.setattr(
        geneset_enrichment_impl,
        "run_enrichment_for_gene_set",
        _fake_run_enrichment,
    )
    register_all_tools()

    user_id = uuid4()
    conversation_id = uuid4()
    gs_id = uuid4().hex[:12]
    await _seed_user_chat(user_id, conversation_id)
    await _seed_gene_set(gs_id, user_id, ["a", "b", "c"])

    repo = BackgroundTaskRepository(session_factory=async_session_factory)
    task_id = await repo.create(
        conversation_id=conversation_id,
        user_id=user_id,
        tool_name="geneset_enrichment",
        args={
            "args": [],
            "kwargs": {"gene_set_id": gs_id, "enrichment_types": ["word"]},
        },
        estimated_duration_seconds=120,
    )

    await run_durable_task(
        tool_name="geneset_enrichment",
        task_id=str(task_id),
        thread_id=str(conversation_id),
        args={
            "args": [],
            "kwargs": {"gene_set_id": gs_id, "enrichment_types": ["word"]},
        },
    )

    t = await repo.get(task_id=task_id)
    assert t is not None
    assert t.status in ("complete", "resuming", "result_ready")
    assert t.result is not None
    assert t.result["geneSetId"] == gs_id
