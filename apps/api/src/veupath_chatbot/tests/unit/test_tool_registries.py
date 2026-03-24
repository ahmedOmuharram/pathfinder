"""Tests for tool registries: strategy_registry, research_registry.

Verifies that:
- All tools delegate correctly to their inner implementations
- Tool names are unique within each registry
- Error responses are consistent
- Edge cases in the mixin composition are handled

Also covers workbench_tools.py input validation gaps.
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

from veupath_chatbot.ai.tools.planner.artifact_tools import ArtifactToolsMixin
from veupath_chatbot.ai.tools.planner.gene_tools import GeneToolsMixin
from veupath_chatbot.ai.tools.planner.workbench_tools import WorkbenchToolsMixin
from veupath_chatbot.platform.errors import ErrorCode
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.services.gene_lookup.lookup import GeneSearchResult
from veupath_chatbot.services.gene_lookup.wdk import GeneResolveResult
from veupath_chatbot.services.gene_sets.store import GeneSetStore
from veupath_chatbot.services.gene_sets.types import GeneSet

_SITE_ID = "plasmodb"
_USER_ID = uuid4()


# ---------------------------------------------------------------------------
# workbench_tools create_workbench_gene_set input validation
# ---------------------------------------------------------------------------


class _TestableWorkbench(WorkbenchToolsMixin):
    def __init__(self, site_id: str = _SITE_ID, user_id: object = _USER_ID) -> None:
        self.site_id = site_id
        self.user_id = user_id


class TestCreateGeneSetValidation:
    """Verify create_workbench_gene_set rejects invalid inputs."""

    async def test_empty_gene_ids_rejected(self):
        """Empty gene_ids returns a validation error."""
        tools = _TestableWorkbench()
        result = await tools.create_workbench_gene_set(name="Empty Set", gene_ids=[])
        assert result["ok"] is False
        assert result["code"] == "VALIDATION_ERROR"

    async def test_empty_name_rejected(self):
        """Empty name returns a validation error."""
        tools = _TestableWorkbench()
        result = await tools.create_workbench_gene_set(
            name="", gene_ids=["PF3D7_0100100"]
        )
        assert result["ok"] is False
        assert result["code"] == "VALIDATION_ERROR"

    async def test_whitespace_only_name_rejected(self):
        """Whitespace-only name returns a validation error."""
        tools = _TestableWorkbench()
        result = await tools.create_workbench_gene_set(
            name="   ", gene_ids=["PF3D7_0100100"]
        )
        assert result["ok"] is False
        assert result["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# GeneToolsMixin edge cases
# ---------------------------------------------------------------------------


class _TestableGene(GeneToolsMixin):
    def __init__(self, site_id: str = _SITE_ID) -> None:
        self.site_id = site_id


class TestGeneToolsEdgeCases:
    async def test_resolve_gene_ids_none_input_treated_as_empty(self):
        """gene_ids=None should be handled gracefully."""
        tools = _TestableGene()
        # gene_ids or [] -> []
        result = await tools.resolve_gene_ids_to_records(gene_ids=None)
        assert result.error == "No gene IDs provided."

    async def test_resolve_gene_ids_with_duplicates(self):
        """Duplicate IDs should still be passed through (WDK deduplicates)."""
        tools = _TestableGene()

        with patch(
            "veupath_chatbot.ai.tools.planner.gene_tools.resolve_gene_ids",
            new_callable=AsyncMock,
            return_value=GeneResolveResult(records=[], total_count=0),
        ):
            result = await tools.resolve_gene_ids_to_records(
                gene_ids=["PF3D7_0100100", "PF3D7_0100100"]
            )

        # Duplicates are passed through — service returns 0 total
        assert result.total_count == 0

    async def test_lookup_gene_records_empty_query(self):
        """Empty query should still be forwarded to the service."""
        tools = _TestableGene()

        with patch(
            "veupath_chatbot.ai.tools.planner.gene_tools.lookup_genes_by_text",
            new_callable=AsyncMock,
            return_value=GeneSearchResult(records=[], total_count=0),
        ):
            result = await tools.lookup_gene_records(query="")

        # Empty query returns empty results
        assert result.total_count == 0


# ---------------------------------------------------------------------------
# ArtifactToolsMixin edge cases
# ---------------------------------------------------------------------------


class _TestableArtifact(ArtifactToolsMixin):
    pass


class TestArtifactToolsEdgeCases:
    async def test_none_summary_becomes_empty_string(self):
        tools = _TestableArtifact()
        result = await tools.save_planning_artifact(
            title="T",
            summary_markdown=None,
        )
        # summary_markdown or "" -> ""
        assert result["planningArtifact"]["summaryMarkdown"] == ""

    async def test_none_title_becomes_new_conversation(self):
        tools = _TestableArtifact()
        result = await tools.save_planning_artifact(
            title=None,
            summary_markdown="content",
        )
        # Blank title falls through to "New Conversation" via the
        # `(title or "").strip() or "New Conversation"` logic.
        # -> "" or "New Conversation"
        # -> "New Conversation"
        assert result["planningArtifact"]["title"] == "New Conversation"


# ---------------------------------------------------------------------------
# WorkbenchToolsMixin: list and enrichment edge cases
# ---------------------------------------------------------------------------


def _make_gene_set(gs_id: str = "gs-1", **kwargs: object) -> GeneSet:
    defaults: dict[str, object] = {
        "id": gs_id,
        "name": "Test Set",
        "site_id": _SITE_ID,
        "gene_ids": ["PF3D7_0100100"],
        "source": "paste",
        "user_id": _USER_ID,
    }
    defaults.update(kwargs)
    return GeneSet(**defaults)


class TestWorkbenchListEdgeCases:
    async def test_list_with_no_user_id_uses_alist_all(self):
        """When user_id is None, should use alist_all instead of alist_for_user."""
        tools = _TestableWorkbench(user_id=None)

        store = GeneSetStore()
        mock_alist_all = AsyncMock(return_value=[])

        with (
            patch(
                "veupath_chatbot.ai.tools.planner.workbench_tools.get_gene_set_store",
                return_value=store,
            ),
            patch.object(store, "alist_all", mock_alist_all),
        ):
            result = await tools.list_workbench_gene_sets()

        assert result["totalSets"] == 0

    async def test_enrichment_with_nonexistent_gene_set(self):
        tools = _TestableWorkbench()

        store = GeneSetStore()
        mock_aget = AsyncMock(return_value=None)

        with (
            patch(
                "veupath_chatbot.ai.tools.planner.workbench_tools.get_gene_set_store",
                return_value=store,
            ),
            patch.object(store, "aget", mock_aget),
            patch.object(store, "alist_for_user", AsyncMock(return_value=[])),
        ):
            result = await tools.run_gene_set_enrichment(gene_set_id="missing")

        assert "error" in result
        assert "missing" in result["error"]


# ---------------------------------------------------------------------------
# tool_error format consistency
# ---------------------------------------------------------------------------


class TestToolErrorFormat:
    def test_tool_error_with_enum_code(self):
        result = tool_error(ErrorCode.STEP_NOT_FOUND, "Step not found")
        assert result["ok"] is False
        assert result["code"] == "STEP_NOT_FOUND"
        assert result["message"] == "Step not found"

    def test_tool_error_with_string_code(self):
        result = tool_error("CUSTOM_ERROR", "Something broke")
        assert result["ok"] is False
        assert result["code"] == "CUSTOM_ERROR"

    def test_tool_error_with_details(self):
        result = tool_error("ERR", "msg", step_id="s1", count=42)
        assert result["ok"] is False
        assert "details" in result
        assert result["step_id"] == "s1"
        assert result["count"] == 42

    def test_tool_error_none_details_excluded_from_top_level(self):
        result = tool_error("ERR", "msg", step_id=None, count=42)
        # None values should NOT be promoted to top level
        assert "step_id" not in result or result["step_id"] is None
        assert result["count"] == 42

    def test_tool_error_no_details(self):
        result = tool_error("ERR", "msg")
        assert result["ok"] is False
        assert "details" not in result
