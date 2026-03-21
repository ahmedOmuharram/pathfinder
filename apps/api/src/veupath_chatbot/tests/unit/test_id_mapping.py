"""Unit tests for services.strategies.engine.id_mapping.IdMappingMixin."""

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.session import StrategySession
from veupath_chatbot.integrations.veupathdb.discovery import SearchCatalog
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKSearch
from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.services.strategies.engine.helpers import StrategyToolsHelpers

_PATCH_TARGET = (
    "veupath_chatbot.services.strategies.engine.id_mapping.get_discovery_service"
)


def _make_session(site_id: str = "plasmodb") -> StrategySession:
    session = StrategySession(site_id)
    session.create_graph("Test", graph_id="g1")
    return session


def _make_mixin(session: StrategySession | None = None) -> StrategyToolsHelpers:
    if session is None:
        session = _make_session()
    return StrategyToolsHelpers(session)


def _make_catalog(
    record_types: list,
    searches: dict[str, list] | None = None,
) -> SearchCatalog:
    """Build a SearchCatalog pre-populated with test data.

    ``record_types`` is the raw list (strings or dicts) returned by
    ``catalog.get_record_types()``.

    ``searches`` maps record-type name -> list of search dicts.  Raw dicts
    are validated into ``WDKSearch`` models so ``SearchCatalog.find_search``
    and related methods work correctly.
    """
    catalog = SearchCatalog.__new__(SearchCatalog)
    catalog.site_id = "plasmodb"
    catalog._record_types = record_types
    catalog._searches = {
        rt: [WDKSearch.model_validate(s) for s in sl]
        for rt, sl in (searches or {}).items()
    }
    catalog._search_details = {}
    catalog._loaded = True
    return catalog


@contextmanager
def _patch_catalog(catalog: SearchCatalog) -> Iterator[None]:
    """Patch get_discovery_service so get_catalog returns *catalog*."""
    mock_discovery = MagicMock()
    mock_discovery.get_catalog = AsyncMock(return_value=catalog)
    with patch(_PATCH_TARGET, return_value=mock_discovery):
        yield


# -- _infer_record_type ---------------------------------------------------


class TestInferRecordType:
    def test_returns_graph_record_type(self) -> None:
        session = _make_session()
        graph = session.get_graph("g1")
        assert graph is not None
        graph.record_type = "gene"
        mixin = _make_mixin(session)
        step = PlanStepNode(search_name="S1", parameters={}, id="s1")
        assert mixin._infer_record_type(step) == "gene"

    def test_returns_none_when_no_graph(self) -> None:
        session = StrategySession("plasmodb")
        mixin = StrategyToolsHelpers(session)
        step = PlanStepNode(search_name="S1", parameters={}, id="s1")
        assert mixin._infer_record_type(step) is None

    def test_returns_none_when_graph_has_no_record_type(self) -> None:
        session = _make_session()
        graph = session.get_graph("g1")
        assert graph is not None
        graph.record_type = None
        mixin = _make_mixin(session)
        step = PlanStepNode(search_name="S1", parameters={}, id="s1")
        assert mixin._infer_record_type(step) is None


# -- _resolve_record_type -------------------------------------------------


class TestResolveRecordType:
    @pytest.mark.asyncio
    async def test_returns_none_for_none_input(self) -> None:
        mixin = _make_mixin()
        assert await mixin._resolve_record_type(None) is None

    @pytest.mark.asyncio
    async def test_returns_empty_string_for_empty_input(self) -> None:
        """Empty string is falsy, so _resolve_record_type returns it unchanged."""
        mixin = _make_mixin()
        result = await mixin._resolve_record_type("")
        assert result == ""

    @pytest.mark.asyncio
    async def test_exact_match_string_record_type(self) -> None:
        catalog = _make_catalog(["gene", "transcript"])
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            result = await mixin._resolve_record_type("gene")
            assert result == "gene"

    @pytest.mark.asyncio
    async def test_case_insensitive_match(self) -> None:
        catalog = _make_catalog(["gene", "transcript"])
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            result = await mixin._resolve_record_type("GENE")
            assert result == "gene"

    @pytest.mark.asyncio
    async def test_match_by_url_segment_in_dict(self) -> None:
        catalog = _make_catalog(
            [{"urlSegment": "gene", "name": "Gene", "displayName": "Genes"}]
        )
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            result = await mixin._resolve_record_type("gene")
            assert result == "gene"

    @pytest.mark.asyncio
    async def test_match_by_name_in_dict(self) -> None:
        catalog = _make_catalog(
            [{"urlSegment": "gene", "name": "Gene", "displayName": "Genes"}]
        )
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            # Matching by the "name" field when urlSegment doesn't match
            result = await mixin._resolve_record_type("Gene")
            assert result == "gene"  # Should return urlSegment

    @pytest.mark.asyncio
    async def test_match_by_display_name_single(self) -> None:
        catalog = _make_catalog(
            [
                {"urlSegment": "gene", "name": "Gene", "displayName": "Genes"},
                {
                    "urlSegment": "transcript",
                    "name": "Transcript",
                    "displayName": "EST",
                },
            ]
        )
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            result = await mixin._resolve_record_type("Genes")
            assert result == "gene"

    @pytest.mark.asyncio
    async def test_no_match_returns_original(self) -> None:
        catalog = _make_catalog(["gene", "transcript"])
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            result = await mixin._resolve_record_type("nonexistent")
            assert result == "nonexistent"

    @pytest.mark.asyncio
    async def test_whitespace_trimmed(self) -> None:
        catalog = _make_catalog(["gene"])
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            result = await mixin._resolve_record_type("  gene  ")
            assert result == "gene"

    @pytest.mark.asyncio
    async def test_dict_without_url_segment_falls_back_to_name(self) -> None:
        catalog = _make_catalog([{"name": "Gene"}])
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            result = await mixin._resolve_record_type("Gene")
            assert result == "Gene"

    @pytest.mark.asyncio
    async def test_non_string_non_dict_entries_skipped(self) -> None:
        catalog = _make_catalog([42, None, True, "gene"])
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            result = await mixin._resolve_record_type("gene")
            assert result == "gene"

    @pytest.mark.asyncio
    async def test_ambiguous_display_name_returns_original(self) -> None:
        """When multiple record types share the same displayName, return the input."""
        catalog = _make_catalog(
            [
                {"urlSegment": "gene", "name": "Gene", "displayName": "Records"},
                {
                    "urlSegment": "transcript",
                    "name": "Transcript",
                    "displayName": "Records",
                },
            ]
        )
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            result = await mixin._resolve_record_type("Records")
            # Multiple display matches -> fallback to original input
            assert result == "Records"


# -- _find_record_type_for_search ---------------------------------------


class TestResolveRecordTypeForSearch:
    @pytest.mark.asyncio
    async def test_no_search_name_returns_resolved_record_type(self) -> None:
        catalog = _make_catalog(["gene"])
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            result = await mixin._find_record_type_for_search("gene", None)
            assert result == "gene"

    @pytest.mark.asyncio
    async def test_search_found_in_resolved_record_type(self) -> None:
        catalog = _make_catalog(
            ["gene"],
            {
                "gene": [
                    {"urlSegment": "GenesByTextSearch", "name": "GenesByTextSearch"}
                ]
            },
        )
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            result = await mixin._find_record_type_for_search(
                "gene", "GenesByTextSearch"
            )
            assert result == "gene"

    @pytest.mark.asyncio
    async def test_search_not_found_falls_back_to_other_record_types(self) -> None:
        catalog = _make_catalog(
            ["gene", "transcript"],
            {
                "gene": [],
                "transcript": [
                    {"urlSegment": "TranscriptSearch", "name": "TranscriptSearch"}
                ],
            },
        )
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            result = await mixin._find_record_type_for_search(
                "gene", "TranscriptSearch"
            )
            assert result == "transcript"

    @pytest.mark.asyncio
    async def test_require_match_returns_none_when_not_found(self) -> None:
        catalog = _make_catalog(["gene"], {"gene": []})
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            result = await mixin._find_record_type_for_search(
                "gene", "NonexistentSearch", require_match=True
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_no_fallback_returns_resolved(self) -> None:
        catalog = _make_catalog(["gene"], {"gene": []})
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            result = await mixin._find_record_type_for_search(
                "gene", "NonexistentSearch", allow_fallback=False
            )
            assert result == "gene"

    @pytest.mark.asyncio
    async def test_no_fallback_require_match_returns_none(self) -> None:
        catalog = _make_catalog(["gene"], {"gene": []})
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            result = await mixin._find_record_type_for_search(
                "gene", "X", require_match=True, allow_fallback=False
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_search_not_in_catalog_returns_resolved(self) -> None:
        """When the catalog has no matching search, return resolved (no require_match)."""
        catalog = _make_catalog(["gene"], {"gene": []})
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            result = await mixin._find_record_type_for_search(
                "gene", "GenesByTextSearch"
            )
            # Catalog has no searches, so fallback returns resolved
            assert result == "gene"

    @pytest.mark.asyncio
    async def test_none_record_type_with_search_name(self) -> None:
        catalog = _make_catalog(
            ["gene"],
            {
                "gene": [
                    {"urlSegment": "GenesByTextSearch", "name": "GenesByTextSearch"}
                ]
            },
        )
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            result = await mixin._find_record_type_for_search(None, "GenesByTextSearch")
            # Falls back to global catalog lookup
            assert result == "gene"


# -- _find_record_type_hint ------------------------------------------------


class TestFindRecordTypeHint:
    @pytest.mark.asyncio
    async def test_finds_record_type_for_search(self) -> None:
        catalog = _make_catalog(
            ["gene", "transcript"],
            {
                "gene": [
                    {"urlSegment": "GenesByTextSearch", "name": "GenesByTextSearch"}
                ]
            },
        )
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            result = await mixin._find_record_type_hint("GenesByTextSearch")
            assert result == "gene"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        catalog = _make_catalog(["gene"], {"gene": []})
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            result = await mixin._find_record_type_hint("NonexistentSearch")
            assert result is None

    @pytest.mark.asyncio
    async def test_excludes_specified_record_type(self) -> None:
        catalog = _make_catalog(
            ["gene", "transcript"],
            {
                "gene": [{"urlSegment": "SharedSearch", "name": "SharedSearch"}],
                "transcript": [{"urlSegment": "SharedSearch", "name": "SharedSearch"}],
            },
        )
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            result = await mixin._find_record_type_hint("SharedSearch", exclude="gene")
            assert result == "transcript"

    @pytest.mark.asyncio
    async def test_handles_discovery_exception(self) -> None:
        mock_discovery = MagicMock()
        mock_discovery.get_catalog = AsyncMock(side_effect=WDKError(detail="fail"))
        with patch(_PATCH_TARGET, return_value=mock_discovery):
            mixin = _make_mixin()
            result = await mixin._find_record_type_hint("AnySearch")
            assert result is None

    @pytest.mark.asyncio
    async def test_skips_empty_record_type_names(self) -> None:
        """Catalog keyed by name; empty names won't appear as keys."""
        catalog = _make_catalog(
            [{"urlSegment": "", "name": ""}, "gene"],
            {
                "gene": [
                    {"urlSegment": "GenesByTextSearch", "name": "GenesByTextSearch"}
                ]
            },
        )
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            result = await mixin._find_record_type_hint("GenesByTextSearch")
            assert result == "gene"

    @pytest.mark.asyncio
    async def test_handles_dict_record_type_entries(self) -> None:
        catalog = _make_catalog(
            [{"urlSegment": "gene", "name": "Gene"}],
            {
                "gene": [
                    {"urlSegment": "GenesByTextSearch", "name": "GenesByTextSearch"}
                ]
            },
        )
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            result = await mixin._find_record_type_hint("GenesByTextSearch")
            assert result == "gene"

    @pytest.mark.asyncio
    async def test_only_excluded_record_type_returns_none(self) -> None:
        """When the only match is the excluded record type, return None."""
        catalog = _make_catalog(
            ["gene"],
            {"gene": [{"urlSegment": "GeneSearch", "name": "GeneSearch"}]},
        )
        with _patch_catalog(catalog):
            mixin = _make_mixin()
            result = await mixin._find_record_type_hint("GeneSearch", exclude="gene")
            assert result is None
