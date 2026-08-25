"""Internal: exposes stream-part payload models in the OpenAPI schema.

These models aren't used by any real endpoint - this module only exists
so they appear under components/schemas for type generation on the frontend.
Transitive types (GraphNode, GraphEdge) are auto-included via $ref from
their parent schemas and do not need explicit entries.
Every installed assistant registers its parts, so the spec carries the union.
"""

from assistant_core.conversation.stream_parts.core_parts import STREAM_PARTS
from assistant_core.platform.pydantic_base import CamelModel
from fastapi import APIRouter

from pathfinder.assistants.registry import get_assistant_registry

for _spec in get_assistant_registry().specs():
    if _spec.register_stream_parts is not None:
        _spec.register_stream_parts(STREAM_PARTS)

StreamPartsSchemaIndex = STREAM_PARTS.schema_index_model()

router = APIRouter(prefix="/api/v1/internal/stream-parts", tags=["internal"])


@router.get(
    "/schemas",
    response_model=StreamPartsSchemaIndex,
    include_in_schema=True,
)
async def stream_parts_schemas() -> CamelModel:
    """Stream-part payload schemas - for OpenAPI generation only."""
    return StreamPartsSchemaIndex()
