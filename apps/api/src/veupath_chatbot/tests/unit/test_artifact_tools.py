"""Tests for ArtifactToolsMixin — planning artifacts, titles, reasoning."""

from veupath_chatbot.ai.tools.planner.artifact_tools import ArtifactToolsMixin


class _TestableTools(ArtifactToolsMixin):
    """Concrete subclass for testing."""


class TestSavePlanningArtifact:
    async def test_returns_artifact_with_all_fields(self) -> None:
        tools = _TestableTools()
        result = await tools.save_planning_artifact(
            title="My Plan",
            summary_markdown="## Summary\nDo this.",
            assumptions=["assumption 1", "assumption 2"],
            parameters={"param1": "value1"},
            proposed_strategy_plan={"steps": [{"search": "GenesByTaxon"}]},
        )

        artifact = result["planningArtifact"]
        assert isinstance(artifact, dict)
        assert artifact["title"] == "My Plan"
        assert artifact["summaryMarkdown"] == "## Summary\nDo this."
        assert artifact["assumptions"] == ["assumption 1", "assumption 2"]
        assert artifact["parameters"] == {"param1": "value1"}
        assert artifact["proposedStrategyPlan"] == {
            "steps": [{"search": "GenesByTaxon"}]
        }
        assert artifact["id"].startswith("plan_")
        assert len(artifact["id"]) == len("plan_") + 12
        assert "createdAt" in artifact

    async def test_defaults_for_optional_fields(self) -> None:
        tools = _TestableTools()
        result = await tools.save_planning_artifact(
            title="Minimal",
            summary_markdown="Just a summary",
        )

        artifact = result["planningArtifact"]
        assert artifact["title"] == "Minimal"
        assert artifact["summaryMarkdown"] == "Just a summary"
        assert artifact["assumptions"] == []
        assert artifact["parameters"] == {}
        assert artifact["proposedStrategyPlan"] is None

    async def test_empty_title_defaults_to_new_conversation(self) -> None:
        tools = _TestableTools()
        result = await tools.save_planning_artifact(
            title="",
            summary_markdown="content",
        )

        artifact = result["planningArtifact"]
        assert artifact["title"] == "New Conversation"

    async def test_whitespace_only_title_defaults_to_new_conversation(self) -> None:
        tools = _TestableTools()
        result = await tools.save_planning_artifact(
            title="   ",
            summary_markdown="content",
        )

        artifact = result["planningArtifact"]
        assert artifact["title"] == "New Conversation"

    async def test_empty_summary_becomes_empty_string(self) -> None:
        tools = _TestableTools()
        result = await tools.save_planning_artifact(
            title="Title",
            summary_markdown="",
        )

        artifact = result["planningArtifact"]
        assert artifact["summaryMarkdown"] == ""

    async def test_each_call_generates_unique_id(self) -> None:
        tools = _TestableTools()
        r1 = await tools.save_planning_artifact(title="A", summary_markdown="x")
        r2 = await tools.save_planning_artifact(title="B", summary_markdown="y")

        assert r1["planningArtifact"]["id"] != r2["planningArtifact"]["id"]

    async def test_created_at_is_iso_format(self) -> None:
        tools = _TestableTools()
        result = await tools.save_planning_artifact(title="T", summary_markdown="s")

        ts = result["planningArtifact"]["createdAt"]
        assert isinstance(ts, str)
        # ISO format contains "T" separator and ends with timezone offset
        assert "T" in ts


class TestSetConversationTitle:
    async def test_returns_title(self) -> None:
        tools = _TestableTools()
        result = await tools.set_conversation_title(title="Malaria Gene Analysis")
        assert result == {"conversationTitle": "Malaria Gene Analysis"}

    async def test_strips_whitespace(self) -> None:
        tools = _TestableTools()
        result = await tools.set_conversation_title(title="  Trimmed  ")
        assert result == {"conversationTitle": "Trimmed"}

    async def test_empty_title_returns_error(self) -> None:
        tools = _TestableTools()
        result = await tools.set_conversation_title(title="")
        assert result == {"error": "title_required"}

    async def test_whitespace_only_title_returns_error(self) -> None:
        tools = _TestableTools()
        result = await tools.set_conversation_title(title="   ")
        assert result == {"error": "title_required"}


class TestReportReasoning:
    async def test_returns_reasoning(self) -> None:
        tools = _TestableTools()
        result = await tools.report_reasoning(
            reasoning="The user wants genes upregulated in gametocytes."
        )
        assert result == {
            "reasoning": "The user wants genes upregulated in gametocytes."
        }

    async def test_strips_whitespace(self) -> None:
        tools = _TestableTools()
        result = await tools.report_reasoning(reasoning="  some reasoning  ")
        assert result == {"reasoning": "some reasoning"}

    async def test_empty_reasoning_returns_error(self) -> None:
        tools = _TestableTools()
        result = await tools.report_reasoning(reasoning="")
        assert result == {"error": "reasoning_required"}

    async def test_whitespace_only_reasoning_returns_error(self) -> None:
        tools = _TestableTools()
        result = await tools.report_reasoning(reasoning="   ")
        assert result == {"error": "reasoning_required"}
