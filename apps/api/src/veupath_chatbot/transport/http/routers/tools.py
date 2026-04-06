"""Tools endpoint — returns the list of AI tools available to the agent."""

from typing import TypedDict

from fastapi import APIRouter

from veupath_chatbot.ai.tools.toolsets import (
    discovery,
    execution,
    planning,
    verification,
)

router = APIRouter(prefix="/api/v1", tags=["tools"])


class _ToolItem(TypedDict):
    name: str
    description: str


class ToolListResponse(TypedDict):
    tools: list[_ToolItem]


@router.get("/tools")
async def list_tools() -> ToolListResponse:
    """Return the list of AI tools registered across all agent phases."""
    seen: set[str] = set()
    tools: list[_ToolItem] = []

    for module in (discovery, planning, execution, verification):
        toolset = module.build_toolset()
        for name, tool_def in toolset.tools.items():
            if name not in seen:
                seen.add(name)
                tools.append(
                    _ToolItem(
                        name=name,
                        description=tool_def.description or "",
                    )
                )

    return {"tools": tools}
