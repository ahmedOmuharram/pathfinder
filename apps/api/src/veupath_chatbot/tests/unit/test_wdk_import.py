"""Unit tests for WDK import: fetch_and_convert and graph reconstruction.

Covers:
- fetch_and_convert: WDK → AST conversion via mocked StrategyAPI
- Graph reconstruction: linear chains, nested trees, parameter preservation
- Metadata: name, description, record_type, is_saved, display_name
- Serialization: to_dict round-trip
"""

from unittest.mock import AsyncMock, MagicMock

from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKSearchConfig,
    WDKSearchResponse,
    WDKStep,
    WDKStepTree,
    WDKStrategyDetails,
)
from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.services.strategies.wdk_sync import fetch_and_convert

# ── Helpers ────────────────────────────────────────────────────────────


def _wdk_step(
    step_id: int,
    search_name: str,
    params: dict[str, str] | None = None,
    *,
    custom_name: str | None = None,
    display_name: str = "",
) -> WDKStep:
    """Build a minimal WDKStep for use in fake strategy payloads."""
    return WDKStep(
        id=step_id,
        search_name=search_name,
        search_config=WDKSearchConfig(parameters=params or {}),
        custom_name=custom_name,
        display_name=display_name,
    )


def _make_wdk_strategy(
    step_tree: WDKStepTree,
    steps: dict[str, WDKStep],
    *,
    record_class_name: str = "gene",
    name: str = "Test Strategy",
    description: str = "",
    is_saved: bool = False,
) -> WDKStrategyDetails:
    """Build a complete WDKStrategyDetails model."""
    return WDKStrategyDetails(
        strategy_id=1,
        name=name,
        root_step_id=step_tree.step_id,
        record_class_name=record_class_name,
        step_tree=step_tree,
        steps=steps,
        description=description,
        is_saved=is_saved,
    )


def _mock_api(wdk_strategy: WDKStrategyDetails) -> AsyncMock:
    """Create a mock StrategyAPI whose get_strategy returns the given model."""
    _empty_response = WDKSearchResponse.model_validate({
        "searchData": {"urlSegment": "_stub"},
        "validation": {"level": "DISPLAYABLE", "isValid": True},
    })
    api = AsyncMock()
    api.get_strategy = AsyncMock(return_value=wdk_strategy)
    api.client = MagicMock()
    api.client.get_search_details_with_params = AsyncMock(
        return_value=_empty_response,
    )
    api.client.get_search_details = AsyncMock(return_value=_empty_response)
    return api


# ── fetch_and_convert: single step tree → AST ─────────────────────────


class TestFetchAndConvertSingleStep:
    """Single WDK step tree converts to AST with 1 step."""

    async def test_single_leaf_step(self) -> None:
        wdk = _make_wdk_strategy(
            step_tree=WDKStepTree(step_id=1),
            steps={"1": _wdk_step(1, "GenesByTextSearch", {"text_expression": "kinase"})},
            name="Kinase Search",
            is_saved=True,
        )
        api = _mock_api(wdk)

        ast, is_saved, _ = await fetch_and_convert(api, 1)

        assert ast.record_type == "gene"
        assert ast.name == "Kinase Search"
        assert ast.root.search_name == "GenesByTextSearch"
        assert ast.root.parameters == {"text_expression": "kinase"}
        assert ast.root.primary_input is None
        assert ast.root.secondary_input is None
        assert ast.root.infer_kind() == "search"
        assert is_saved is True
        assert len(ast.get_all_steps()) == 1

    async def test_single_step_unsaved(self) -> None:
        wdk = _make_wdk_strategy(
            step_tree=WDKStepTree(step_id=10),
            steps={"10": _wdk_step(10, "GenesByGoTerm", {"GoTerm": "GO:0006915"})},
            is_saved=False,
        )
        api = _mock_api(wdk)

        ast, is_saved, _ = await fetch_and_convert(api, 10)

        assert is_saved is False
        assert ast.root.search_name == "GenesByGoTerm"

    async def test_single_step_id_is_string(self) -> None:
        """AST step IDs are always strings (from the WDK int step ID)."""
        wdk = _make_wdk_strategy(
            step_tree=WDKStepTree(step_id=99),
            steps={"99": _wdk_step(99, "GenesByLocation")},
        )
        api = _mock_api(wdk)

        ast, _, _ = await fetch_and_convert(api, 99)

        assert ast.root.id == "99"
        assert isinstance(ast.root.id, str)


# ── fetch_and_convert: combined step tree → AST ───────────────────────


class TestFetchAndConvertCombine:
    """Combined WDK step tree converts to AST with combine node."""

    async def test_two_step_combine(self) -> None:
        wdk = _make_wdk_strategy(
            step_tree=WDKStepTree(
                step_id=3,
                primary_input=WDKStepTree(step_id=1),
                secondary_input=WDKStepTree(step_id=2),
            ),
            steps={
                "1": _wdk_step(1, "GenesByTextSearch", {"text_expression": "kinase"}),
                "2": _wdk_step(2, "GenesByGoTerm", {"GoTerm": "GO:0006915"}),
                "3": _wdk_step(3, "BooleanQuestion", {"bq_operator": "INTERSECT"}),
            },
            name="Combined Search",
        )
        api = _mock_api(wdk)

        ast, _, _ = await fetch_and_convert(api, 3)

        assert ast.root.infer_kind() == "combine"
        assert ast.root.operator == CombineOp.INTERSECT
        assert ast.root.primary_input is not None
        assert ast.root.secondary_input is not None
        assert ast.root.primary_input.search_name == "GenesByTextSearch"
        assert ast.root.secondary_input.search_name == "GenesByGoTerm"
        assert len(ast.get_all_steps()) == 3

    async def test_combine_with_union(self) -> None:
        wdk = _make_wdk_strategy(
            step_tree=WDKStepTree(
                step_id=3,
                primary_input=WDKStepTree(step_id=1),
                secondary_input=WDKStepTree(step_id=2),
            ),
            steps={
                "1": _wdk_step(1, "GenesByTextSearch"),
                "2": _wdk_step(2, "GenesByLocation"),
                "3": _wdk_step(3, "BooleanQuestion", {"bq_operator": "UNION"}),
            },
        )
        api = _mock_api(wdk)

        ast, _, _ = await fetch_and_convert(api, 3)

        assert ast.root.operator == CombineOp.UNION

    async def test_combine_with_minus(self) -> None:
        wdk = _make_wdk_strategy(
            step_tree=WDKStepTree(
                step_id=3,
                primary_input=WDKStepTree(step_id=1),
                secondary_input=WDKStepTree(step_id=2),
            ),
            steps={
                "1": _wdk_step(1, "S1"),
                "2": _wdk_step(2, "S2"),
                "3": _wdk_step(3, "BooleanQuestion", {"bq_operator": "MINUS"}),
            },
        )
        api = _mock_api(wdk)

        ast, _, _ = await fetch_and_convert(api, 3)

        assert ast.root.operator == CombineOp.MINUS


# ── fetch_and_convert: parameters preserved ───────────────────────────


class TestFetchAndConvertParameters:
    """Step parameters are preserved in AST after conversion."""

    async def test_leaf_parameters_preserved(self) -> None:
        params = {
            "text_expression": "kinase",
            "text_fields": "product,gene_name",
            "min_score": "0.5",
        }
        wdk = _make_wdk_strategy(
            step_tree=WDKStepTree(step_id=1),
            steps={"1": _wdk_step(1, "GenesByTextSearch", params)},
        )
        api = _mock_api(wdk)

        ast, _, _ = await fetch_and_convert(api, 1)

        assert ast.root.parameters["text_expression"] == "kinase"
        assert ast.root.parameters["text_fields"] == "product,gene_name"
        assert ast.root.parameters["min_score"] == "0.5"

    async def test_empty_parameters(self) -> None:
        wdk = _make_wdk_strategy(
            step_tree=WDKStepTree(step_id=1),
            steps={"1": _wdk_step(1, "GenesByTextSearch", {})},
        )
        api = _mock_api(wdk)

        ast, _, _ = await fetch_and_convert(api, 1)

        assert ast.root.parameters == {}

    async def test_combine_children_have_their_own_parameters(self) -> None:
        wdk = _make_wdk_strategy(
            step_tree=WDKStepTree(
                step_id=3,
                primary_input=WDKStepTree(step_id=1),
                secondary_input=WDKStepTree(step_id=2),
            ),
            steps={
                "1": _wdk_step(1, "GenesByTextSearch", {"text_expression": "kinase"}),
                "2": _wdk_step(2, "GenesByGoTerm", {"GoTerm": "GO:0006915"}),
                "3": _wdk_step(3, "BooleanQuestion", {"bq_operator": "INTERSECT"}),
            },
        )
        api = _mock_api(wdk)

        ast, _, _ = await fetch_and_convert(api, 3)

        left = ast.root.primary_input
        right = ast.root.secondary_input
        assert left is not None
        assert right is not None
        assert left.parameters == {"text_expression": "kinase"}
        assert right.parameters == {"GoTerm": "GO:0006915"}


# ── Graph reconstruction: linear chain ─────────────────────────────────


class TestGraphReconstructionLinearChain:
    """Linear chain A->B->C via primaryInput produces correct tree."""

    async def test_linear_three_step_chain(self) -> None:
        """Chain: step3(transform) <- step2(transform) <- step1(leaf)."""
        wdk = _make_wdk_strategy(
            step_tree=WDKStepTree(
                step_id=3,
                primary_input=WDKStepTree(
                    step_id=2,
                    primary_input=WDKStepTree(step_id=1),
                ),
            ),
            steps={
                "1": _wdk_step(1, "GenesByTextSearch", {"text_expression": "kinase"}),
                "2": _wdk_step(2, "GenesByOrthologs", {"organism": "Pf3D7"}),
                "3": _wdk_step(3, "GenesByRNASeqEvidence", {"threshold": "10"}),
            },
        )
        api = _mock_api(wdk)

        ast, _, _ = await fetch_and_convert(api, 3)

        # Root should be step3 (transform)
        assert ast.root.search_name == "GenesByRNASeqEvidence"
        assert ast.root.infer_kind() == "transform"
        assert ast.root.primary_input is not None

        # Middle should be step2 (transform)
        mid = ast.root.primary_input
        assert mid.search_name == "GenesByOrthologs"
        assert mid.infer_kind() == "transform"
        assert mid.primary_input is not None

        # Leaf should be step1 (search)
        leaf = mid.primary_input
        assert leaf.search_name == "GenesByTextSearch"
        assert leaf.infer_kind() == "search"
        assert leaf.primary_input is None

        # Total steps
        assert len(ast.get_all_steps()) == 3


# ── Graph reconstruction: nested tree ──────────────────────────────────


class TestGraphReconstructionNestedTree:
    """Nested tree structures are preserved through conversion."""

    async def test_combine_of_combine_and_leaf(self) -> None:
        """Tree: combine(combine(S1, S2), S3).

        Step 5 = UNION of (step 3 INTERSECT) and step 4.
        """
        wdk = _make_wdk_strategy(
            step_tree=WDKStepTree(
                step_id=5,
                primary_input=WDKStepTree(
                    step_id=3,
                    primary_input=WDKStepTree(step_id=1),
                    secondary_input=WDKStepTree(step_id=2),
                ),
                secondary_input=WDKStepTree(step_id=4),
            ),
            steps={
                "1": _wdk_step(1, "GenesByTextSearch"),
                "2": _wdk_step(2, "GenesByGoTerm"),
                "3": _wdk_step(3, "BooleanQuestion", {"bq_operator": "INTERSECT"}),
                "4": _wdk_step(4, "GenesByLocation"),
                "5": _wdk_step(5, "BooleanQuestion", {"bq_operator": "UNION"}),
            },
            name="Nested Strategy",
        )
        api = _mock_api(wdk)

        ast, _, _ = await fetch_and_convert(api, 5)

        # Root is UNION combine
        assert ast.root.infer_kind() == "combine"
        assert ast.root.operator == CombineOp.UNION

        # Primary input is INTERSECT combine
        left = ast.root.primary_input
        assert left is not None
        assert left.infer_kind() == "combine"
        assert left.operator == CombineOp.INTERSECT
        assert left.primary_input is not None
        assert left.secondary_input is not None
        assert left.primary_input.search_name == "GenesByTextSearch"
        assert left.secondary_input.search_name == "GenesByGoTerm"

        # Secondary input is a leaf
        right = ast.root.secondary_input
        assert right is not None
        assert right.infer_kind() == "search"
        assert right.search_name == "GenesByLocation"

        assert len(ast.get_all_steps()) == 5

    async def test_transform_on_combine(self) -> None:
        """Tree: transform(combine(S1, S2)).

        Step 4 transforms the result of combining S1 and S2.
        """
        wdk = _make_wdk_strategy(
            step_tree=WDKStepTree(
                step_id=4,
                primary_input=WDKStepTree(
                    step_id=3,
                    primary_input=WDKStepTree(step_id=1),
                    secondary_input=WDKStepTree(step_id=2),
                ),
            ),
            steps={
                "1": _wdk_step(1, "GenesByTextSearch"),
                "2": _wdk_step(2, "GenesByGoTerm"),
                "3": _wdk_step(3, "BooleanQuestion", {"bq_operator": "INTERSECT"}),
                "4": _wdk_step(4, "GenesByOrthologs", {"organism": "Pf3D7"}),
            },
        )
        api = _mock_api(wdk)

        ast, _, _ = await fetch_and_convert(api, 4)

        # Root is a transform
        assert ast.root.infer_kind() == "transform"
        assert ast.root.search_name == "GenesByOrthologs"

        # Its input is a combine
        inner = ast.root.primary_input
        assert inner is not None
        assert inner.infer_kind() == "combine"
        assert inner.operator == CombineOp.INTERSECT

        assert len(ast.get_all_steps()) == 4


# ── fetch_and_convert: metadata & edge cases ──────────────────────────


class TestFetchAndConvertEdgeCases:
    """Edge cases for fetch_and_convert: missing name, normalization failures."""

    async def test_empty_name_defaults_none(self) -> None:
        """An empty name string becomes None in the AST."""
        wdk = _make_wdk_strategy(
            step_tree=WDKStepTree(step_id=1),
            steps={"1": _wdk_step(1, "GenesByTextSearch")},
            name="",
        )
        api = _mock_api(wdk)

        ast, _, _ = await fetch_and_convert(api, 1)

        assert ast.name is None

    async def test_description_preserved(self) -> None:
        wdk = _make_wdk_strategy(
            step_tree=WDKStepTree(step_id=1),
            steps={"1": _wdk_step(1, "GenesByTextSearch")},
            description="A useful description",
        )
        api = _mock_api(wdk)

        ast, _, _ = await fetch_and_convert(api, 1)

        assert ast.description == "A useful description"

    async def test_normalization_failure_is_swallowed(self) -> None:
        """If parameter normalization fails, the raw values survive."""
        wdk = _make_wdk_strategy(
            step_tree=WDKStepTree(step_id=1),
            steps={"1": _wdk_step(1, "GenesByTextSearch", {"text": "kinase"})},
        )
        api = _mock_api(wdk)
        # Make the normalization path raise
        api.client.get_search_details_with_params = AsyncMock(
            side_effect=WDKError(detail="boom")
        )
        api.client.get_search_details = AsyncMock(side_effect=WDKError(detail="boom"))

        # Should not raise -- normalization failures are logged and swallowed
        ast, _, _ = await fetch_and_convert(api, 1)

        assert ast.root.parameters == {"text": "kinase"}

    async def test_api_get_strategy_called_with_wdk_id(self) -> None:
        wdk = _make_wdk_strategy(
            step_tree=WDKStepTree(step_id=1),
            steps={"1": _wdk_step(1, "S1")},
        )
        api = _mock_api(wdk)

        await fetch_and_convert(api, 42)

        api.get_strategy.assert_awaited_once_with(42)

    async def test_record_type_from_strategy(self) -> None:
        wdk = _make_wdk_strategy(
            step_tree=WDKStepTree(step_id=1),
            steps={"1": _wdk_step(1, "TranscriptsByTextSearch")},
            record_class_name="transcript",
        )
        api = _mock_api(wdk)

        ast, _, _ = await fetch_and_convert(api, 1)

        assert ast.record_type == "transcript"

    async def test_display_name_from_custom_name(self) -> None:
        """customName in step info takes precedence over displayName."""
        wdk = _make_wdk_strategy(
            step_tree=WDKStepTree(step_id=1),
            steps={
                "1": _wdk_step(
                    1,
                    "GenesByTextSearch",
                    custom_name="My Custom Step",
                    display_name="Text Search",
                ),
            },
        )
        api = _mock_api(wdk)

        ast, _, _ = await fetch_and_convert(api, 1)

        assert ast.root.display_name == "My Custom Step"

    async def test_display_name_fallback(self) -> None:
        """If customName is absent, displayName is used."""
        wdk = _make_wdk_strategy(
            step_tree=WDKStepTree(step_id=1),
            steps={
                "1": _wdk_step(
                    1,
                    "GenesByTextSearch",
                    display_name="Text Search",
                ),
            },
        )
        api = _mock_api(wdk)

        ast, _, _ = await fetch_and_convert(api, 1)

        assert ast.root.display_name == "Text Search"


# ── fetch_and_convert: to_dict round-trip ──────────────────────────────


class TestFetchAndConvertToDict:
    """Verify that the AST produced by fetch_and_convert serializes properly."""

    async def test_to_dict_has_required_keys(self) -> None:
        wdk = _make_wdk_strategy(
            step_tree=WDKStepTree(step_id=1),
            steps={"1": _wdk_step(1, "GenesByTextSearch", {"text": "kinase"})},
            name="My Strategy",
        )
        api = _mock_api(wdk)

        ast, _, _ = await fetch_and_convert(api, 1)
        plan = ast.to_dict()

        assert "recordType" in plan
        assert "root" in plan
        assert plan["recordType"] == "gene"
        root = plan["root"]
        assert isinstance(root, dict)
        assert root["searchName"] == "GenesByTextSearch"
        assert root["parameters"] == {"text": "kinase"}

    async def test_combine_to_dict_has_operator(self) -> None:
        wdk = _make_wdk_strategy(
            step_tree=WDKStepTree(
                step_id=3,
                primary_input=WDKStepTree(step_id=1),
                secondary_input=WDKStepTree(step_id=2),
            ),
            steps={
                "1": _wdk_step(1, "S1"),
                "2": _wdk_step(2, "S2"),
                "3": _wdk_step(3, "BooleanQuestion", {"bq_operator": "UNION"}),
            },
        )
        api = _mock_api(wdk)

        ast, _, _ = await fetch_and_convert(api, 3)
        plan = ast.to_dict()

        root = plan["root"]
        assert isinstance(root, dict)
        assert root.get("operator") == "UNION"
        assert "primaryInput" in root
        assert "secondaryInput" in root
