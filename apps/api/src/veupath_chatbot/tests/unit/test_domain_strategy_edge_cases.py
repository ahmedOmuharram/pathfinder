"""Edge-case and bug-hunting tests for domain/strategy."""

from typing import Literal, cast

import pytest
from pydantic import ValidationError as PydanticValidationError

from veupath_chatbot.domain.strategy.ast import (
    PlanStepNode,
    StepAnalysis,
    StepFilter,
    StepReport,
    StrategyAST,
)
from veupath_chatbot.domain.strategy.explain import explain_operation
from veupath_chatbot.domain.strategy.metadata import derive_graph_metadata
from veupath_chatbot.domain.strategy.ops import (
    ColocationParams,
    CombineOp,
    get_wdk_operator,
    parse_op,
)
from veupath_chatbot.domain.strategy.session import (
    StrategyGraph,
    StrategySession,
)
from veupath_chatbot.domain.strategy.validate import (
    StrategyValidator,
    ValidationResult,
    validate_strategy,
)
from veupath_chatbot.tests.fixtures.builders import make_combine, make_leaf


def _leaf(step_id: str = "s1", search_name: str = "S1") -> PlanStepNode:
    return make_leaf(step_id, name=search_name)


def _combine(
    left: PlanStepNode,
    right: PlanStepNode,
    step_id: str = "c1",
    op: CombineOp = CombineOp.INTERSECT,
) -> PlanStepNode:
    return make_combine(step_id, left, right, operator=op)


# ===========================================================================
# 1. AST edge cases
# ===========================================================================


class TestModelValidateEdgeCases:
    def test_empty_string_search_name_accepted(self) -> None:
        """Empty search_name is accepted by model_validate (caught by validate_strategy)."""
        ast = StrategyAST.model_validate(
            {"recordType": "gene", "root": {"searchName": ""}}
        )
        assert ast.root.search_name == ""

    def test_non_string_search_name_raises(self) -> None:
        with pytest.raises(PydanticValidationError):
            StrategyAST.model_validate(
                {"recordType": "gene", "root": {"searchName": 42}}
            )

    def test_parameters_as_list_raises(self) -> None:
        with pytest.raises(PydanticValidationError):
            StrategyAST.model_validate(
                {
                    "recordType": "gene",
                    "root": {"searchName": "S1", "parameters": [1, 2, 3]},
                }
            )

    def test_non_string_record_type_raises(self) -> None:
        with pytest.raises(PydanticValidationError):
            StrategyAST.model_validate(
                {"recordType": 42, "root": {"searchName": "S1"}}
            )

    def test_root_is_list_raises(self) -> None:
        with pytest.raises(PydanticValidationError):
            StrategyAST.model_validate(
                {"recordType": "gene", "root": [{"searchName": "S1"}]}
            )

    def test_root_is_string_raises(self) -> None:
        with pytest.raises(PydanticValidationError):
            StrategyAST.model_validate(
                {"recordType": "gene", "root": "not_a_dict"}
            )

    def test_invalid_operator_string(self) -> None:
        """Invalid operator string should raise PydanticValidationError."""
        with pytest.raises(PydanticValidationError):
            StrategyAST.model_validate(
                {
                    "recordType": "gene",
                    "root": {
                        "searchName": "bool",
                        "primaryInput": {"searchName": "S1"},
                        "secondaryInput": {"searchName": "S2"},
                        "operator": "INVALID_OP",
                    },
                }
            )

    def test_operator_without_secondary_input(self) -> None:
        """Operator present but no secondary input -> valid transform, not combine."""
        ast = StrategyAST.model_validate(
            {
                "recordType": "gene",
                "root": {
                    "searchName": "T1",
                    "primaryInput": {"searchName": "S1"},
                    # operator is set but secondaryInput is absent
                    "operator": "INTERSECT",
                },
            }
        )
        # operator is parsed but secondary is None, so no combine check triggers
        assert ast.root.operator == CombineOp.INTERSECT
        assert ast.root.infer_kind() == "transform"

    def test_null_parameters_raises(self) -> None:
        """parameters: null is rejected by Pydantic (dict field, not Optional)."""
        with pytest.raises(PydanticValidationError):
            StrategyAST.model_validate(
                {
                    "recordType": "gene",
                    "root": {"searchName": "S1", "parameters": None},
                }
            )

    def test_deeply_nested_tree(self) -> None:
        """Multi-level nested tree should parse correctly."""
        data = {
            "recordType": "gene",
            "root": {
                "searchName": "bool",
                "primaryInput": {
                    "searchName": "bool2",
                    "primaryInput": {"searchName": "S1"},
                    "secondaryInput": {"searchName": "S2"},
                    "operator": "UNION",
                },
                "secondaryInput": {"searchName": "S3"},
                "operator": "INTERSECT",
            },
        }
        ast = StrategyAST.model_validate(data)
        assert ast.root.infer_kind() == "combine"
        assert ast.root.primary_input is not None
        assert ast.root.primary_input.infer_kind() == "combine"
        steps = ast.get_all_steps()
        assert len(steps) == 5  # S1, S2, bool2, S3, root


class TestStrategyASTEdgeCases:
    def test_get_all_steps_single_node(self) -> None:
        root = _leaf("s1")
        ast = StrategyAST(record_type="gene", root=root)
        assert len(ast.get_all_steps()) == 1

    def test_get_step_by_id_root(self) -> None:
        root = _leaf("root")
        ast = StrategyAST(record_type="gene", root=root)
        assert ast.get_step_by_id("root") is root

    def test_secondary_without_primary_rejected(self) -> None:
        """secondary_input without primary_input is rejected by model validator."""
        with pytest.raises(PydanticValidationError, match="primaryInput"):
            PlanStepNode(
                search_name="S1",
                secondary_input=_leaf("s2"),
            )


# ===========================================================================
# 2. Parse helpers edge cases
# ===========================================================================


class TestParseFiltersEdgeCases:
    def test_non_list_input(self) -> None:
        assert StepFilter.from_list("not a list") == []
        assert StepFilter.from_list(42) == []
        assert StepFilter.from_list(None) == []

    def test_skips_items_without_name(self) -> None:
        raw = [{"value": 5}, {"name": "f1", "value": 10}]
        filters = StepFilter.from_list(raw)
        assert len(filters) == 1
        assert filters[0].name == "f1"

    def test_empty_string_name_skipped(self) -> None:
        raw = [{"name": "", "value": 5}]
        assert StepFilter.from_list(raw) == []

    def test_disabled_field_parsed(self) -> None:
        raw = [{"name": "f1", "value": 1, "disabled": True}]
        filters = StepFilter.from_list(raw)
        assert filters[0].disabled is True

    def test_disabled_defaults_false(self) -> None:
        raw = [{"name": "f1", "value": 1}]
        filters = StepFilter.from_list(raw)
        assert filters[0].disabled is False


class TestParseAnalysesEdgeCases:
    def test_non_list_input(self) -> None:
        assert StepAnalysis.from_list("not a list") == []
        assert StepAnalysis.from_list(None) == []

    def test_skips_items_without_analysis_type(self) -> None:
        raw = [{"parameters": {}}, {"analysisType": "enrichment"}]
        analyses = StepAnalysis.from_list(raw)
        assert len(analyses) == 1

    def test_snake_case_analysis_type(self) -> None:
        raw = [{"analysis_type": "go_enrichment", "parameters": {}}]
        analyses = StepAnalysis.from_list(raw)
        assert analyses[0].analysis_type == "go_enrichment"

    def test_custom_name_camel_and_snake(self) -> None:
        raw1 = [{"analysisType": "e", "customName": "Custom"}]
        raw2 = [{"analysisType": "e", "custom_name": "Custom"}]
        assert StepAnalysis.from_list(raw1)[0].custom_name == "Custom"
        assert StepAnalysis.from_list(raw2)[0].custom_name == "Custom"

    def test_non_dict_parameters_defaults_empty(self) -> None:
        raw = [{"analysisType": "e", "parameters": "not_a_dict"}]
        analyses = StepAnalysis.from_list(raw)
        assert analyses[0].parameters == {}


class TestParseReportsEdgeCases:
    def test_non_list_input(self) -> None:
        assert StepReport.from_list(42) == []
        assert StepReport.from_list(None) == []

    def test_missing_report_name_defaults(self) -> None:
        raw = [{"config": {"format": "csv"}}]
        reports = StepReport.from_list(raw)
        assert reports[0].report_name == "standard"

    def test_non_dict_config_defaults_empty(self) -> None:
        raw = [{"reportName": "tabular", "config": "not_a_dict"}]
        reports = StepReport.from_list(raw)
        assert reports[0].config == {}


class TestParseColocationParamsEdgeCases:
    def test_non_dict_input(self) -> None:
        assert ColocationParams.from_json("not_a_dict") is None
        assert ColocationParams.from_json(42) is None
        assert ColocationParams.from_json(None) is None

    def test_float_values_truncated(self) -> None:
        result = ColocationParams.from_json({"upstream": 100.9, "downstream": 50.1})
        assert result is not None
        assert result.upstream == 100  # int() truncates
        assert result.downstream == 50

    def test_non_numeric_defaults_zero(self) -> None:
        result = ColocationParams.from_json({"upstream": "not_a_number"})
        assert result is not None
        assert result.upstream == 0

    def test_invalid_strand_defaults_both(self) -> None:
        result = ColocationParams.from_json({"strand": "invalid"})
        assert result is not None
        assert result.strand == "both"

    def test_missing_fields_use_defaults(self) -> None:
        result = ColocationParams.from_json({})
        assert result is not None
        assert result.upstream == 0
        assert result.downstream == 0
        assert result.strand == "both"


# ===========================================================================
# 3. Ops edge cases
# ===========================================================================


class TestParseOpEdgeCases:
    def test_mixed_case_with_underscores(self) -> None:
        assert parse_op("Left_Minus") == CombineOp.MINUS

    def test_hyphen_normalization(self) -> None:
        assert parse_op("left-minus") == CombineOp.MINUS

    def test_space_normalization(self) -> None:
        assert parse_op("right minus") == CombineOp.RMINUS

    def test_multiple_spaces_and_hyphens(self) -> None:
        """'left - minus' normalizes to 'LEFT___MINUS' which is NOT in aliases.

        This is expected: the normalization replaces each hyphen/space with '_'
        but does not collapse consecutive underscores.
        """
        with pytest.raises(ValueError, match="Unknown operator"):
            parse_op("left - minus")

    def test_only_whitespace_raises(self) -> None:
        with pytest.raises(ValueError, match="<empty>"):
            parse_op("   \t\n   ")

    def test_none_string_raises(self) -> None:
        """parse_op("") should raise since the raw string is empty."""
        with pytest.raises(ValueError, match="<empty>"):
            parse_op("")


class TestGetWdkOperatorEdgeCases:
    def test_all_non_colocate_ops(self) -> None:
        for op in CombineOp:
            if op == CombineOp.COLOCATE:
                continue
            result = get_wdk_operator(op)
            assert isinstance(result, str)
            assert result == op.value


class TestColocationParamsEdgeCases:
    def test_very_large_distances(self) -> None:
        params = ColocationParams(upstream=10**9, downstream=10**9)
        assert params.check_errors() == []

    def test_zero_distances(self) -> None:
        params = ColocationParams(upstream=0, downstream=0)
        assert params.check_errors() == []

    def test_all_strands_valid(self) -> None:
        for strand in ("same", "opposite", "both"):
            params = ColocationParams(
                strand=cast("Literal['same', 'opposite', 'both']", strand)
            )
            assert params.check_errors() == []


# ===========================================================================
# 4. Explain edge cases
# ===========================================================================


class TestExplainEdgeCases:
    def test_all_ops_return_non_empty(self) -> None:
        for op in CombineOp:
            result = explain_operation(op)
            assert len(result) > 0


# ===========================================================================
# 5. Metadata edge cases
# ===========================================================================


class TestMetadataEdgeCases:
    def test_unicode_goal(self) -> None:
        name, desc = derive_graph_metadata("Find genes in Plasmodium \u00e9t\u00e9")
        assert "\u00e9t\u00e9" in desc
        assert "\u00e9t\u00e9" in name

    def test_exactly_77_chars(self) -> None:
        """77 chars should not be truncated."""
        goal = "A" * 77
        name, _ = derive_graph_metadata(goal)
        assert name == goal

    def test_exactly_78_chars(self) -> None:
        """78 chars should not be truncated (< 80)."""
        goal = "A" * 78
        name, _ = derive_graph_metadata(goal)
        assert name == goal

    def test_exactly_81_chars_truncated(self) -> None:
        """81 chars should be truncated to 80."""
        goal = "A" * 81
        name, _ = derive_graph_metadata(goal)
        assert len(name) <= 80
        assert name.endswith("...")

    def test_only_whitespace(self) -> None:
        name, desc = derive_graph_metadata("   \t\n   ")
        assert name == "Strategy Draft"
        assert desc == ""

    def test_multiline_goal_collapsed(self) -> None:
        name, _desc = derive_graph_metadata("line1\n  line2\t  line3")
        assert "\n" not in name
        assert "\t" not in name


# ===========================================================================
# 6. Session edge cases
# ===========================================================================


class TestStrategyGraphEdgeCases:
    def test_add_step_with_nonexistent_input_id(self) -> None:
        """Adding a combine step whose input IDs are not in roots doesn't crash."""
        graph = StrategyGraph("g1", "Test", "site")
        left = _leaf("orphan_left")
        right = _leaf("orphan_right")
        combine = _combine(left, right, step_id="c1")
        # orphan_left and orphan_right are NOT added to graph
        graph.add_step(combine)
        # combine is added and becomes root; orphans are not removed from roots
        # (they were never in roots)
        assert "c1" in graph.roots
        assert "c1" in graph.steps

    def test_recompute_roots_with_circular_references(self) -> None:
        """Circular references should not crash recompute_roots."""
        graph = StrategyGraph("g1", "Test", "site")
        node_a = _leaf("a")
        node_b = _leaf("b")
        # Create circular reference
        node_a.primary_input = node_b
        node_b.primary_input = node_a
        graph.steps = {"a": node_a, "b": node_b}
        # recompute_roots looks at direct references, not transitive
        # a references b, b references a -> both are referenced -> no roots
        graph.recompute_roots()
        assert graph.roots == set()

    def test_save_history_without_strategy(self) -> None:
        """save_history with no current_strategy is a no-op."""
        graph = StrategyGraph("g1", "Test", "site")
        graph.save_history("test")
        assert len(graph.history) == 0

    def test_undo_with_one_history_entry(self) -> None:
        """Cannot undo with only one history entry."""
        graph = StrategyGraph("g1", "Test", "site")
        root = _leaf("s1")
        graph.current_strategy = StrategyAST(record_type="gene", root=root)
        graph.save_history("initial")
        assert graph.undo() is False

    def test_undo_with_zero_history(self) -> None:
        graph = StrategyGraph("g1", "Test", "site")
        assert graph.undo() is False

    def test_get_step_returns_none_for_empty_graph(self) -> None:
        graph = StrategyGraph("g1", "Test", "site")
        assert graph.get_step("anything") is None


class TestStrategySessionEdgeCases:
    def test_create_graph_returns_same_graph_with_new_name(self) -> None:
        session = StrategySession("site")
        g1 = session.create_graph("First")
        g2 = session.create_graph("Second")
        assert g1 is g2
        assert g2.name == "Second"

    def test_create_graph_same_name_returns_same(self) -> None:
        session = StrategySession("site")
        g1 = session.create_graph("Same")
        g2 = session.create_graph("Same")
        assert g1 is g2

    def test_add_graph_replaces_when_same_id(self) -> None:
        session = StrategySession("site")
        g1 = StrategyGraph("g1", "First", "site")
        g2 = StrategyGraph("g1", "Second", "site")
        session.add_graph(g1)
        session.add_graph(g2)
        assert session.graph is g2

    def test_add_graph_ignores_different_id(self) -> None:
        session = StrategySession("site")
        g1 = StrategyGraph("g1", "First", "site")
        g2 = StrategyGraph("g2", "Second", "site")
        session.add_graph(g1)
        session.add_graph(g2)
        assert session.graph is g1

    def test_get_graph_with_no_graph_returns_none(self) -> None:
        session = StrategySession("site")
        assert session.get_graph(None) is None
        assert session.get_graph("any") is None


# ===========================================================================
# 7. Validation edge cases
# ===========================================================================


class TestValidationEdgeCases:
    def test_none_root_strategy(self) -> None:
        """Strategy with root=None should be rejected by Pydantic validation."""
        with pytest.raises(PydanticValidationError):
            StrategyAST(record_type="gene", root=None)

    def test_empty_record_type_and_empty_search_name(self) -> None:
        """Multiple simultaneous errors should all be reported."""
        strategy = StrategyAST(
            record_type="",
            root=PlanStepNode(search_name="", parameters={}),
        )
        result = validate_strategy(strategy)
        assert not result.valid
        codes = {e.code for e in result.errors}
        assert "MISSING_RECORD_TYPE" in codes
        assert "MISSING_SEARCH_NAME" in codes

    def test_deep_tree_all_nodes_validated(self) -> None:
        """Validator should recurse into deeply nested trees."""
        # Build a combine(combine(search, search_empty_name), search) tree
        s1 = PlanStepNode(search_name="S1", parameters={})
        s_bad = PlanStepNode(search_name="", parameters={})
        inner = _combine(s1, s_bad, step_id="inner", op=CombineOp.INTERSECT)
        s3 = PlanStepNode(search_name="S3", parameters={})
        outer = _combine(inner, s3, step_id="outer", op=CombineOp.UNION)
        strategy = StrategyAST(record_type="gene", root=outer)
        result = validate_strategy(strategy)
        assert not result.valid
        # The empty searchName error should be in the secondary of the inner combine
        assert any(
            e.code == "MISSING_SEARCH_NAME" and "secondaryInput" in e.path
            for e in result.errors
        )

    def test_colocate_with_valid_params(self) -> None:
        left = _leaf("s1")
        right = _leaf("s2")
        combine = PlanStepNode(
            search_name="bool",
            primary_input=left,
            secondary_input=right,
            operator=CombineOp.COLOCATE,
            colocation_params=ColocationParams(
                upstream=100, downstream=200, strand="both"
            ),
            id="c1",
        )
        strategy = StrategyAST(record_type="gene", root=combine)
        result = validate_strategy(strategy)
        assert result.valid

    def test_validation_result_success_factory(self) -> None:
        result = ValidationResult.success()
        assert result.valid is True
        assert result.errors == []

    def test_available_searches_empty_for_record_type(self) -> None:
        """When available_searches has the record_type but it's empty list."""
        validator = StrategyValidator(available_searches={"gene": []})
        step = _leaf("s1", "S1")
        strategy = StrategyAST(record_type="gene", root=step)
        result = validator.validate(strategy)
        # S1 is not in the empty list -> UNKNOWN_SEARCH
        assert not result.valid
        assert any(e.code == "UNKNOWN_SEARCH" for e in result.errors)

    def test_available_searches_missing_record_type(self) -> None:
        """When available_searches doesn't have the current record_type."""
        validator = StrategyValidator(available_searches={"transcript": ["S1"]})
        step = _leaf("s1", "S1")
        strategy = StrategyAST(record_type="gene", root=step)
        result = validator.validate(strategy)
        # "gene" not in available_searches -> rt_searches is [] -> S1 not in [] -> error
        assert not result.valid

    def test_transform_node_validates_child(self) -> None:
        """Transform's primary_input should be validated too."""
        bad_child = PlanStepNode(search_name="", parameters={})
        transform = PlanStepNode(
            search_name="T1",
            primary_input=bad_child,
            parameters={},
        )
        strategy = StrategyAST(record_type="gene", root=transform)
        result = validate_strategy(strategy)
        assert not result.valid
        assert any(
            e.code == "MISSING_SEARCH_NAME" and "primaryInput" in e.path
            for e in result.errors
        )


# ===========================================================================
# 8. Round-trip serialization edge cases
# ===========================================================================


class TestRoundTripEdgeCases:
    def test_minimal_strategy_round_trip(self) -> None:
        ast = StrategyAST(record_type="gene", root=_leaf("s1", "S1"))
        d = ast.model_dump(by_alias=True, exclude_none=True, mode="json")
        parsed = StrategyAST.model_validate(d)
        assert parsed.record_type == "gene"
        assert parsed.root.search_name == "S1"

    def test_complex_strategy_round_trip(self) -> None:
        s1 = PlanStepNode(
            search_name="S1",
            parameters={"text": "kinase"},
            display_name="Search 1",
            id="s1",
            filters=[StepFilter(name="f1", value=42, disabled=True)],
            analyses=[
                StepAnalysis(
                    analysis_type="enrich", parameters={"go": "bp"}, custom_name="GO"
                )
            ],
            reports=[StepReport(report_name="tabular", config={"format": "csv"})],
        )
        s2 = PlanStepNode(search_name="S2", id="s2")
        root = PlanStepNode(
            search_name="bool",
            primary_input=s1,
            secondary_input=s2,
            operator=CombineOp.UNION,
            id="root",
            display_name="Combined",
        )
        ast = StrategyAST(
            record_type="gene",
            root=root,
            name="My Strategy",
            description="A test strategy",
            metadata={"custom": "field"},
        )
        d = ast.model_dump(by_alias=True, exclude_none=True, mode="json")
        parsed = StrategyAST.model_validate(d)

        assert parsed.record_type == "gene"
        assert parsed.name == "My Strategy"
        assert parsed.description == "A test strategy"
        assert parsed.root.operator == CombineOp.UNION
        assert parsed.root.display_name == "Combined"
        assert parsed.root.primary_input is not None
        assert parsed.root.primary_input.display_name == "Search 1"
        assert len(parsed.root.primary_input.filters) == 1
        assert parsed.root.primary_input.filters[0].disabled is True
        assert len(parsed.root.primary_input.analyses) == 1
        assert parsed.root.primary_input.analyses[0].custom_name == "GO"
        assert len(parsed.root.primary_input.reports) == 1

    def test_colocation_round_trip(self) -> None:
        left = _leaf("s1", "S1")
        right = _leaf("s2", "S2")
        root = PlanStepNode(
            search_name="bool",
            primary_input=left,
            secondary_input=right,
            operator=CombineOp.COLOCATE,
            colocation_params=ColocationParams(
                upstream=500, downstream=1000, strand="opposite"
            ),
            id="c1",
        )
        ast = StrategyAST(record_type="gene", root=root)
        d = ast.model_dump(by_alias=True, exclude_none=True, mode="json")
        parsed = StrategyAST.model_validate(d)
        cp = parsed.root.colocation_params
        assert cp is not None
        assert cp.upstream == 500
        assert cp.downstream == 1000
        assert cp.strand == "opposite"


# ===========================================================================
# 9. Undo and history edge cases
# ===========================================================================


class TestUndoEdgeCases:
    def test_undo_multiple_times(self) -> None:
        """Multiple undos should step through history."""
        graph = StrategyGraph("g1", "Test", "site")

        # State 1
        s1 = _leaf("s1")
        graph.add_step(s1)
        graph.current_strategy = StrategyAST(record_type="gene", root=s1)
        graph.save_history("state1")

        # State 2
        s2 = _leaf("s2")
        graph.add_step(s2)
        root2 = _combine(s1, s2, step_id="c1")
        graph.current_strategy = StrategyAST(record_type="gene", root=root2)
        graph.steps = {s.id: s for s in graph.current_strategy.get_all_steps()}
        graph.recompute_roots()
        graph.save_history("state2")

        # State 3
        s3 = _leaf("s3")
        graph.add_step(s3)
        root3 = _combine(root2, s3, step_id="c2")
        graph.current_strategy = StrategyAST(record_type="gene", root=root3)
        graph.steps = {s.id: s for s in graph.current_strategy.get_all_steps()}
        graph.recompute_roots()
        graph.save_history("state3")

        # Undo to state2
        assert graph.undo() is True
        assert len(graph.steps) == 3  # s1, s2, c1

        # Undo to state1
        assert graph.undo() is True
        assert len(graph.steps) == 1  # s1

        # Can't undo further
        assert graph.undo() is False

    def test_undo_preserves_correct_strategy(self) -> None:
        """After undo, current_strategy should match the previous state."""
        graph = StrategyGraph("g1", "Test", "site")

        root1 = _leaf("s1")
        graph.current_strategy = StrategyAST(record_type="gene", root=root1)
        graph.steps = {s.id: s for s in graph.current_strategy.get_all_steps()}
        graph.recompute_roots()
        graph.save_history("first")

        root2 = PlanStepNode(
            search_name="S2",
            parameters={"x": "y"},
            id="s2",
        )
        graph.current_strategy = StrategyAST(record_type="gene", root=root2)
        graph.steps = {s.id: s for s in graph.current_strategy.get_all_steps()}
        graph.recompute_roots()
        graph.save_history("second")

        graph.undo()
        assert graph.current_strategy is not None
        assert graph.current_strategy.root.search_name == "S1"
