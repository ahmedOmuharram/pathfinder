"""Every caller of the embedding API answers when the API does not.

An unreachable embedding API costs a ranking, never a call. Each test names the
documented fallback: lexical token overlap for the strategies, tree order for
the phyletic codes.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

import pytest
from assistant_core.embeddings.embedder import EmbeddingUnavailableError
from pydantic_ai import RunContext

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone import catalog as catalog_tools
from pathfinder.domain.parameters.phyletic import PhyleticNode, PhyleticTree
from pathfinder.integrations.veupathdb.wdk_models import WDKStrategySummary
from pathfinder.mcp import server as mcp_server
from pathfinder.services.catalog import param_phyletic, public_strategy_search

_UNREACHABLE = EmbeddingUnavailableError(batch_size=1, cause="no route to host")

_STRATEGIES = [
    WDKStrategySummary(
        strategy_id=1,
        name="Vaccine antigens",
        root_step_id=1,
        description="surface proteins",
    ),
    WDKStrategySummary(
        strategy_id=2,
        name="Kinase inhibitors",
        root_step_id=2,
        description="drug targets",
    ),
]


async def _refuse(*args: object, **kwargs: object) -> list[dict[str, Any]]:
    del args, kwargs
    raise _UNREACHABLE


class _StrategyApi:
    async def list_public_strategies(self) -> list[WDKStrategySummary]:
        return list(_STRATEGIES)


@pytest.mark.asyncio
async def test_the_mcp_tool_falls_back_to_lexical_ranking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        mcp_server.wdk, "get_strategy_api", lambda _site: _StrategyApi()
    )
    monkeypatch.setattr(
        public_strategy_search, "rank_public_strategies_semantic", _refuse
    )

    found = await mcp_server.search_example_plans("plasmodb", "vaccine", limit=3)

    assert [row["name"] for row in found] == ["Vaccine antigens"]


class _Deps:
    site_id = "plasmodb"


class _Ctx:
    deps = _Deps()


def _agent_ctx() -> RunContext[AgentDeps]:
    return cast("RunContext[AgentDeps]", _Ctx())


@pytest.mark.asyncio
async def test_the_agent_tool_falls_back_to_lexical_ranking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(catalog_tools, "get_strategy_api", lambda _site: _StrategyApi())
    monkeypatch.setattr(catalog_tools, "rank_public_strategies_semantic", _refuse)

    found = await catalog_tools.search_example_plans(_agent_ctx(), "vaccine", limit=3)

    assert [row["name"] for row in found] == ["Vaccine antigens"]


class _RefusingEmbedder:
    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        del texts
        raise _UNREACHABLE

    async def embed_query(self, text: str) -> list[float]:
        del text
        raise _UNREACHABLE


@pytest.mark.asyncio
async def test_the_phyletic_ranking_falls_back_to_tree_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(param_phyletic, "get_embedder", _RefusingEmbedder)
    candidates = [("hsap", "Homo sapiens", True), ("pfal", "P. falciparum", True)]

    ranked = await param_phyletic._rank_by_semantic_similarity("mammal", candidates)

    assert ranked == candidates


@pytest.mark.asyncio
async def test_the_phyletic_matches_still_describe_the_tree_without_the_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The tool answers with the whole tree rather than raising at the model."""
    monkeypatch.setattr(param_phyletic, "get_embedder", _RefusingEmbedder)
    tree = PhyleticTree(
        roots=[
            PhyleticNode(
                code="MAMM",
                label="Mammals",
                depth=1,
                children=[
                    PhyleticNode(code="hsap", label="Homo sapiens", depth=2),
                ],
            ),
        ],
    )

    matches = await param_phyletic._match_phyletic_entries(tree, "mammal")

    assert [match["code"] for match in matches] == ["MAMM", "hsap"]
