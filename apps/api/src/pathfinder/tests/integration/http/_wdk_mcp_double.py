"""A stand-in for veupathdb-wdk-mcp, served over HTTP for one test module.

It answers under the served server's own tool names and annotations, so the
path a declaration takes to reach the agent is exercised over a socket. The
served server's live behaviour is proven by its own integration lane.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from socket import socket
from typing import Any

import uvicorn
from fastmcp import FastMCP
from mcp.types import ToolAnnotations

RECORD_TYPES = ["transcript", "organism"]
SEARCH_NAMES = ["GenesByMolecularWeight", "GenesByTaxon"]
CONTROL_TEST_RESULT = "2 of 2 positive controls returned"

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
ADDITIVE_WRITE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    openWorldHint=False,
)


async def list_record_types(site_id: str) -> list[str]:
    """Report the record types one site serves.

    Args:
        site_id: VEuPathDB site, for example 'plasmodb'.
    """
    del site_id
    return RECORD_TYPES


async def search_for_searches(site_id: str, query: str) -> list[str]:
    """Report the searches whose subject matches a query.

    Args:
        site_id: VEuPathDB site, for example 'plasmodb'.
        query: What the searches should be about.
    """
    del site_id, query
    return SEARCH_NAMES


async def run_control_tests_on_search(
    site_id: str,
    target_search_name: str,
    target_parameters: dict[str, Any],
    positive_controls: list[str] | None = None,
    negative_controls: list[str] | None = None,
    record_type: str = "transcript",
) -> str:
    """Intersect a search's results with known control genes.

    Args:
        site_id: VEuPathDB site, for example 'plasmodb'.
        target_search_name: WDK search urlSegment to test.
        target_parameters: Parameter values, each in its typed shape.
        positive_controls: Gene ids the search should return.
        negative_controls: Gene ids the search should not return.
        record_type: Record type. Gene searches are 'transcript'.
    """
    del site_id, target_search_name, target_parameters
    del positive_controls, negative_controls, record_type
    return CONTROL_TEST_RESULT


ANNOTATIONS: dict[str, ToolAnnotations] = {
    "list_record_types": READ,
    "search_for_searches": READ,
    "run_control_tests_on_search": ADDITIVE_WRITE,
}


def build_double() -> FastMCP[None]:
    """The three tools site help declares, under the names the server serves."""
    server: FastMCP[None] = FastMCP(name="veupathdb-wdk-mcp-double")
    for tool in (list_record_types, search_for_searches, run_control_tests_on_search):
        server.tool(tool, annotations=ANNOTATIONS[tool.__name__])
    return server


class _AnnouncingServer(uvicorn.Server):
    """Announces the moment its socket is bound and its app has started."""

    def __init__(self, config: uvicorn.Config) -> None:
        super().__init__(config)
        self.ready = asyncio.Event()

    async def startup(self, sockets: list[socket] | None = None) -> None:
        await super().startup(sockets=sockets)
        self.ready.set()

    @contextmanager
    def capture_signals(self) -> Iterator[None]:
        """An in-process test server must not install process signal handlers."""
        yield


@asynccontextmanager
async def served_double() -> AsyncIterator[str]:
    """Serve the double on a port the operating system picks. Yields its URL."""
    app = build_double().http_app(path="/mcp", stateless_http=True)
    server = _AnnouncingServer(
        uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"),
    )
    task = asyncio.create_task(server.serve())
    try:
        await server.ready.wait()
        port = server.servers[0].sockets[0].getsockname()[1]
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        server.should_exit = True
        await task
