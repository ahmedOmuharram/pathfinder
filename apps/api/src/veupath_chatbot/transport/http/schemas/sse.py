"""Transport-only SSE event schemas that depend on chat response types.

Most SSE event schemas live in ``platform.event_schemas`` so that
services, AI, and platform layers can import them without depending on
transport.  This module keeps only the types that reference transport-
layer chat schemas (CitationResponse, PlanningArtifactResponse).
"""

from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.transport.http.schemas.chat import (
    CitationResponse,
    PlanningArtifactResponse,
)


class CitationsEventData(CamelModel):
    """Payload for ``citations`` SSE events."""

    citations: list[CitationResponse] | None = None


class PlanningArtifactEventData(CamelModel):
    """Payload for ``planning_artifact`` SSE events."""

    planning_artifact: PlanningArtifactResponse | None = None
