"""Tests for ai.tools.strategy_tools.discovery_ops -- explain_operator and keyword search."""

import pytest

from veupath_chatbot.ai.tools.strategy_tools.discovery_ops import StrategyDiscoveryOps
from veupath_chatbot.domain.strategy.session import StrategySession


def _make_discovery_ops() -> StrategyDiscoveryOps:
    session = StrategySession("plasmodb")
    session.create_graph("test", graph_id="g1")
    ops = StrategyDiscoveryOps.__new__(StrategyDiscoveryOps)
    ops.session = session
    return ops


# -- explain_operator (pure function, no external calls) --


async def test_explain_intersect():
    ops = _make_discovery_ops()
    result = await ops.explain_operator("INTERSECT")
    assert "both" in result.lower()


async def test_explain_union():
    ops = _make_discovery_ops()
    result = await ops.explain_operator("UNION")
    assert "either" in result.lower()


async def test_explain_minus():
    ops = _make_discovery_ops()
    result = await ops.explain_operator("MINUS")
    assert "left" in result.lower()
    assert "not" in result.lower()


async def test_explain_rminus():
    ops = _make_discovery_ops()
    result = await ops.explain_operator("RMINUS")
    assert "right" in result.lower()


async def test_explain_colocate():
    ops = _make_discovery_ops()
    result = await ops.explain_operator("COLOCATE")
    assert "genomic" in result.lower() or "near" in result.lower()


async def test_explain_case_insensitive():
    ops = _make_discovery_ops()
    result = await ops.explain_operator("intersect")
    assert "both" in result.lower()


async def test_explain_alias():
    ops = _make_discovery_ops()
    result = await ops.explain_operator("AND")
    assert "both" in result.lower()


async def test_explain_invalid_raises():
    ops = _make_discovery_ops()
    with pytest.raises(ValueError, match="Unknown operator"):
        await ops.explain_operator("INVALID_OP")


# -- search_searches_by_keywords validation (no external calls needed for error paths) --


async def test_search_by_keywords_empty_keywords():
    ops = _make_discovery_ops()
    result = await ops.search_searches_by_keywords(keywords="")
    assert result["ok"] is False
    assert result["code"] == "VALIDATION_ERROR"
    assert "No keywords" in str(result["message"])


async def test_search_by_keywords_empty_list():
    ops = _make_discovery_ops()
    result = await ops.search_searches_by_keywords(keywords=[])
    assert result["ok"] is False
    assert "No keywords" in str(result["message"])


async def test_search_by_keywords_string_tokenized():
    """Keywords provided as a single string should be tokenized."""
    ops = _make_discovery_ops()
    result = await ops.search_searches_by_keywords(keywords="!!!@@@")
    assert result["ok"] is False
    assert "No keywords" in str(result["message"])
