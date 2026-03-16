"""Download endpoint for AI-generated export files."""

import io

from fastapi import APIRouter, HTTPException
from starlette.responses import StreamingResponse

from veupath_chatbot.services.export import get_export_service

router = APIRouter(prefix="/api/v1/exports", tags=["exports"])


@router.get("/{export_id}")
async def download_export(export_id: str) -> StreamingResponse:
    """Serve a previously generated export file.

    Export IDs are uuid4 tokens with a 10-minute TTL. No auth required.
    """
    svc = get_export_service()
    result = await svc.get_export(export_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Export not found or expired")
    content, filename, content_type = result
    return StreamingResponse(
        io.BytesIO(content),
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
