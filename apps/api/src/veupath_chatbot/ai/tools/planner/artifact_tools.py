"""Tools for planning artifacts, conversation titles, and reasoning.

Provides :class:`ArtifactToolsMixin` with tools for saving planning
artifacts, setting conversation titles, and reporting reasoning.
"""

from datetime import UTC, datetime
from typing import Annotated, cast
from uuid import uuid4

from kani import AIParam, ai_function

from veupath_chatbot.platform.types import JSONArray, JSONObject


class ArtifactToolsMixin:
    """Kani tool mixin for planning artifact management."""

    @ai_function()
    async def save_planning_artifact(
        self,
        title: Annotated[str, AIParam(desc="Short title for the plan")],
        summary_markdown: Annotated[
            str,
            AIParam(desc="Main planning output in markdown (actionable, structured)"),
        ],
        assumptions: Annotated[
            list[str] | None, AIParam(desc="Optional list of assumptions/constraints")
        ] = None,
        parameters: Annotated[
            JSONObject | None,
            AIParam(desc="Chosen/considered parameters (free-form JSON)"),
        ] = None,
        proposed_strategy_plan: Annotated[
            JSONObject | None,
            AIParam(
                desc=(
                    "Optional proposed strategy plan payload that can be "
                    "applied during execution."
                )
            ),
        ] = None,
    ) -> JSONObject:
        """Publish a reusable planning artifact (persisted to the conversation)."""
        artifact: JSONObject = {
            "id": f"plan_{uuid4().hex[:12]}",
            "title": (title or "").strip() or "New Conversation",
            "summaryMarkdown": summary_markdown or "",
            "assumptions": cast("JSONArray", assumptions or []),
            "parameters": cast("JSONObject", parameters or {}),
            "proposedStrategyPlan": proposed_strategy_plan,
            "createdAt": datetime.now(UTC).isoformat(),
        }
        return {"planningArtifact": artifact}

    @ai_function()
    async def set_conversation_title(
        self,
        title: Annotated[str, AIParam(desc="Short conversation title")],
    ) -> JSONObject:
        """Update the conversation title."""
        t = (title or "").strip()
        if not t:
            return {"error": "title_required"}
        return {"conversationTitle": t}

    @ai_function()
    async def report_reasoning(
        self,
        reasoning: Annotated[
            str, AIParam(desc="Model reasoning text to show in Thinking tab")
        ],
    ) -> JSONObject:
        """Publish reasoning text to the Thinking tab."""
        r = (reasoning or "").strip()
        if not r:
            return {"error": "reasoning_required"}
        return {"reasoning": r}
