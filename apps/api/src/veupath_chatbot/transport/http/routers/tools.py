"""Tools endpoint — returns the list of AI tools available to the agent."""

from typing import TypedDict

from fastapi import APIRouter

from veupath_chatbot.ai.agents.executor import PathfinderAgent
from veupath_chatbot.ai.agents.factory import create_engine

router = APIRouter(prefix="/api/v1", tags=["tools"])


class _ToolItem(TypedDict):
    name: str
    description: str


class ToolListResponse(TypedDict):
    tools: list[_ToolItem]


@router.get("/tools")
async def list_tools() -> ToolListResponse:
    """Return the list of AI tools registered on the agent."""
    # Build a throwaway agent to inspect its function registry.
    engine = create_engine()
    agent = PathfinderAgent(
        engine=engine,
        site_id="veupathdb",
        disable_rag=True,
    )
    tools: list[_ToolItem] = [
        _ToolItem(name=fn.name, description=fn.desc or "")
        for fn in agent.functions.values()
    ]
    return {"tools": tools}
