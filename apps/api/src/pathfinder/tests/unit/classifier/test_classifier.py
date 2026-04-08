"""Unit tests for rule-based request classifier."""

from unittest.mock import MagicMock

from pathfinder.ai.orchestration.classifier import (
    ClassificationResult,
    Intent,
    classify_request,
)


def _mock_graph(step_count: int = 1) -> MagicMock:
    """Create a mock StrategyGraph with the given number of steps."""
    graph = MagicMock()
    graph.steps = {f"step_{i}": MagicMock() for i in range(1, step_count + 1)}
    return graph


def _empty_graph() -> MagicMock:
    """Mock graph with no steps (empty strategy)."""
    graph = MagicMock()
    graph.steps = {}
    return graph


class TestNewStrategy:
    def test_creation_keywords_without_graph(self) -> None:
        result = classify_request("Find malaria genes in P. falciparum")
        assert result is not None
        assert result.intent == Intent.NEW_STRATEGY
        assert result.confidence == 0.85
        assert len(result.reasoning) > 0

    def test_creation_keywords_with_empty_graph(self) -> None:
        result = classify_request(
            "Search for kinase genes", graph=_empty_graph()
        )
        assert result is not None
        assert result.intent == Intent.NEW_STRATEGY

    def test_identify_genes(self) -> None:
        result = classify_request("Identify genes involved in drug resistance")
        assert result is not None
        assert result.intent == Intent.NEW_STRATEGY


class TestExtendStrategy:
    def test_extension_keywords_with_graph(self) -> None:
        result = classify_request(
            "Also add genes by GO term", graph=_mock_graph()
        )
        assert result is not None
        assert result.intent == Intent.EXTEND_STRATEGY
        assert result.confidence == 0.80
        assert len(result.reasoning) > 0

    def test_additionally_keyword(self) -> None:
        result = classify_request(
            "Additionally filter by expression data", graph=_mock_graph()
        )
        assert result is not None
        assert result.intent == Intent.EXTEND_STRATEGY

    def test_narrow_down_keyword(self) -> None:
        result = classify_request(
            "Narrow down to genes in chromosome 7", graph=_mock_graph()
        )
        assert result is not None
        assert result.intent == Intent.EXTEND_STRATEGY


class TestEditStrategy:
    def test_change_organism_with_graph(self) -> None:
        result = classify_request(
            "Change the organism to P. vivax", graph=_mock_graph()
        )
        assert result is not None
        assert result.intent == Intent.EDIT_STRATEGY
        assert 0.70 <= result.confidence <= 0.90
        assert len(result.reasoning) > 0

    def test_step_reference_with_edit(self) -> None:
        result = classify_request(
            "change step_1 organism", graph=_mock_graph()
        )
        assert result is not None
        assert result.intent == Intent.EDIT_STRATEGY
        assert result.confidence == 0.85
        assert "step reference" in result.reasoning.lower()

    def test_modify_parameter_with_graph(self) -> None:
        result = classify_request(
            "Modify the p-value threshold", graph=_mock_graph()
        )
        assert result is not None
        assert result.intent == Intent.EDIT_STRATEGY


class TestQuestion:
    def test_interrogative_question(self) -> None:
        result = classify_request("What does PF3D7_1133400 do?")
        assert result is not None
        assert result.intent == Intent.QUESTION
        assert result.confidence == 0.85
        assert "interrogative" in result.reasoning.lower()

    def test_short_greeting(self) -> None:
        result = classify_request("hello")
        assert result is not None
        assert result.intent == Intent.QUESTION
        assert result.confidence == 0.60
        assert "short" in result.reasoning.lower()

    def test_explain_query(self) -> None:
        result = classify_request("Explain the GO enrichment results")
        assert result is not None
        assert result.intent == Intent.QUESTION


class TestPlanApproval:
    def test_yes_with_pending_plan(self) -> None:
        result = classify_request("yes", has_pending_plan=True)
        assert result is not None
        assert result.intent == Intent.EDIT_STRATEGY
        assert result.confidence == 0.95
        assert "approval" in result.reasoning.lower()

    def test_looks_good_with_pending_plan(self) -> None:
        result = classify_request("looks good", has_pending_plan=True)
        assert result is not None
        assert result.intent == Intent.EDIT_STRATEGY
        assert result.confidence == 0.95

    def test_go_ahead_with_pending_plan(self) -> None:
        result = classify_request("go ahead!", has_pending_plan=True)
        assert result is not None
        assert result.intent == Intent.EDIT_STRATEGY


class TestPlanRevision:
    def test_revise_with_pending_plan(self) -> None:
        result = classify_request(
            "revise the parameters", has_pending_plan=True
        )
        assert result is not None
        assert result.intent == Intent.EDIT_STRATEGY
        assert result.confidence == 0.90
        assert "revision" in result.reasoning.lower()

    def test_no_wait_with_pending_plan(self) -> None:
        result = classify_request(
            "no, change the organism first", has_pending_plan=True
        )
        assert result is not None
        assert result.intent == Intent.EDIT_STRATEGY
        assert result.confidence == 0.90

    def test_actually_with_pending_plan(self) -> None:
        result = classify_request(
            "actually, use a different search", has_pending_plan=True
        )
        assert result is not None
        assert result.intent == Intent.EDIT_STRATEGY


class TestAmbiguousFallthrough:
    def test_creation_keywords_with_existing_graph(self) -> None:
        """Ambiguous: could be extend or new. Falls through to LLM."""
        result = classify_request("kinase genes", graph=_mock_graph())
        # "kinase genes" is 2 words, no creation keywords → short-message fallback
        assert result is None or result.intent == Intent.QUESTION

    def test_find_genes_with_existing_graph_is_ambiguous(self) -> None:
        """'Find genes' with existing graph is ambiguous (new vs extend)."""
        result = classify_request(
            "Find genes expressed in the liver", graph=_mock_graph()
        )
        assert result is None


class TestEdgeCases:
    def test_empty_message(self) -> None:
        result = classify_request("")
        assert result is not None
        assert result.intent == Intent.QUESTION
        assert result.confidence == 0.60

    def test_whitespace_only(self) -> None:
        result = classify_request("   ")
        assert result is not None
        assert result.intent == Intent.QUESTION

    def test_result_is_pydantic_model(self) -> None:
        result = classify_request("What is malaria?")
        assert result is not None
        assert isinstance(result, ClassificationResult)
        assert isinstance(result.intent, Intent)

    def test_no_graph_no_creation_long_message(self) -> None:
        """Long message without creation or question patterns -> None."""
        result = classify_request(
            "The parasites colonize red blood cells during the erythrocytic cycle"
        )
        assert result is None
