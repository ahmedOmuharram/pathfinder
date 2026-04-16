from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from pathfinder.persistence.repositories.checkpoint_label import (
    CheckpointLabelRepository,
)
from pathfinder.transport.http.deps import (
    CurrentUser,
    get_checkpoint_label_repo,
)
from pathfinder.transport.http.schemas.checkpoints import (
    LabelRequest,
    LabelRow,
)

router = APIRouter(prefix="/api/v1/chats", tags=["labels"])

LabelRepo = Annotated[
    CheckpointLabelRepository, Depends(get_checkpoint_label_repo)
]


@router.get("/{chat_id}/labels", response_model=list[LabelRow])
async def list_labels(
    chat_id: UUID,
    user_id: CurrentUser,
    repo: LabelRepo,
) -> list[LabelRow]:
    rows = await repo.list_for_thread(
        thread_id=str(chat_id), user_id=user_id
    )
    return [
        LabelRow(
            checkpoint_id=r.checkpoint_id,
            label=r.label,
            pinned=r.pinned,
        )
        for r in rows
    ]


@router.put(
    "/{chat_id}/labels/{checkpoint_id}",
    response_model=LabelRow,
)
async def set_label(
    chat_id: UUID,
    checkpoint_id: str,
    body: LabelRequest,
    user_id: CurrentUser,
    repo: LabelRepo,
) -> LabelRow:
    row = await repo.set_label(
        thread_id=str(chat_id),
        checkpoint_id=checkpoint_id,
        user_id=user_id,
        label=body.label,
        pinned=body.pinned,
    )
    return LabelRow(
        checkpoint_id=row.checkpoint_id,
        label=row.label,
        pinned=row.pinned,
    )


@router.delete(
    "/{chat_id}/labels/{checkpoint_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_label(
    chat_id: UUID,
    checkpoint_id: str,
    user_id: CurrentUser,
    repo: LabelRepo,
) -> Response:
    await repo.delete_label(
        thread_id=str(chat_id),
        checkpoint_id=checkpoint_id,
        user_id=user_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
