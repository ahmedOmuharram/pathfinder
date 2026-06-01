"""Download endpoint for AI-generated export files."""

import io
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from pathfinder.services.export import get_export_service
from pathfinder.transport.http.deps import CurrentUser

router = APIRouter(prefix="/api/v1/exports", tags=["exports"])


@router.get("/{export_id}")
async def download_export(export_id: UUID, user_id: CurrentUser) -> StreamingResponse:
    """Serve a previously generated export file.

    Export IDs are uuid4 tokens with a 10-minute TTL. Requires the
    authenticated user to own the export row.
    """
    svc = get_export_service()
    stored = await svc.get_export(export_id=export_id, user_id=user_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Export not found or expired")
    return StreamingResponse(
        io.BytesIO(stored.data),
        media_type=stored.content_type,
        headers={"Content-Disposition": f'attachment; filename="{stored.filename}"'},
    )
