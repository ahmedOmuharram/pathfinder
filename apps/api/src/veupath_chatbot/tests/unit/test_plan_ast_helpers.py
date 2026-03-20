"""Tests for plan AST helpers in domain/strategy/plan_ast.py.

These pure functions build a recursive plan AST from a flat steps list
and count nodes in plan trees. They were extracted from platform/events.py
where they violated SRP (domain logic in a platform event layer).
"""

from veupath_chatbot.domain.strategy.plan_ast import (
    count_plan_nodes,
    steps_to_plan,
)


class TestStepsToPlan:
    """steps_to_plan builds a recursive plan AST from flat steps list."""

    def test_single_search_step(self) -> None:
        steps = [
            {
                "id": "step1",
                "searchName": "GenesByTextSearch",
                "parameters": {"text_expression": "kinase"},
            },
        ]
        snapshot = {"recordType": "gene", "name": "My Strategy"}
        plan = steps_to_plan(steps, "step1", snapshot)

        assert plan is not None
        assert plan["recordType"] == "gene"
        assert plan["metadata"]["name"] == "My Strategy"
        root = plan["root"]
        assert root["searchName"] == "GenesByTextSearch"
        assert root["parameters"]["text_expression"] == "kinase"

    def test_two_step_combine(self) -> None:
        steps = [
            {
                "id": "step1",
                "searchName": "GenesByTextSearch",
                "parameters": {"text_expression": "kinase"},
            },
            {
                "id": "step2",
                "searchName": "GenesByTextSearch",
                "parameters": {"text_expression": "protease"},
            },
            {
                "id": "step3",
                "searchName": "GenesBooleanQuestion",
                "operator": "INTERSECT",
                "primaryInputStepId": "step1",
                "secondaryInputStepId": "step2",
                "parameters": {},
            },
        ]
        snapshot = {"recordType": "gene", "name": "Boolean"}
        plan = steps_to_plan(steps, "step3", snapshot)

        assert plan is not None
        root = plan["root"]
        assert root["operator"] == "INTERSECT"
        assert root["primaryInput"]["searchName"] == "GenesByTextSearch"
        assert root["secondaryInput"]["searchName"] == "GenesByTextSearch"

    def test_returns_none_for_missing_root(self) -> None:
        steps = [{"id": "step1", "searchName": "X", "parameters": {}}]
        result = steps_to_plan(steps, "nonexistent", {})
        assert result is None

    def test_combine_kind_inferred(self) -> None:
        """Steps with 'kind': 'combine' and no searchName get __combine__."""
        steps = [
            {
                "id": "step1",
                "kind": "combine",
                "operator": "UNION",
                "primaryInputStepId": "stepA",
                "parameters": {},
            },
        ]
        plan = steps_to_plan(steps, "step1", {"recordType": "gene"})
        assert plan is not None
        assert plan["root"]["searchName"] == "__combine__"

    def test_unknown_kind_no_searchname(self) -> None:
        """Steps without searchName or kind='combine' get __unknown__."""
        steps = [{"id": "s1", "parameters": {}}]
        plan = steps_to_plan(steps, "s1", {"recordType": "transcript"})
        assert plan is not None
        assert plan["root"]["searchName"] == "__unknown__"

    def test_display_name_preserved(self) -> None:
        steps = [
            {
                "id": "s1",
                "searchName": "GenesByTextSearch",
                "displayName": "Kinase Genes",
                "parameters": {},
            },
        ]
        plan = steps_to_plan(steps, "s1", {"recordType": "gene"})
        assert plan is not None
        assert plan["root"]["displayName"] == "Kinase Genes"

    def test_colocation_params_preserved(self) -> None:
        steps = [
            {
                "id": "s1",
                "searchName": "X",
                "colocationParams": {"upstream": 500},
                "parameters": {},
            },
        ]
        plan = steps_to_plan(steps, "s1", {"recordType": "gene"})
        assert plan is not None
        assert plan["root"]["colocationParams"]["upstream"] == 500

    def test_defaults_record_type_to_transcript(self) -> None:
        """When snapshot lacks recordType, defaults to transcript."""
        steps = [{"id": "s1", "searchName": "X", "parameters": {}}]
        plan = steps_to_plan(steps, "s1", {})
        assert plan is not None
        assert plan["recordType"] == "transcript"

    def test_empty_steps_list(self) -> None:
        result = steps_to_plan([], "any", {})
        assert result is None


class TestCountPlanNodes:
    """count_plan_nodes counts step nodes in a plan dict."""

    def test_single_node(self) -> None:
        plan = {"root": {"searchName": "GenesByTextSearch"}}
        assert count_plan_nodes(plan) == 1

    def test_three_node_tree(self) -> None:
        plan = {
            "root": {
                "searchName": "GenesBooleanQuestion",
                "primaryInput": {"searchName": "GenesByTextSearch"},
                "secondaryInput": {"searchName": "GenesByOrthologs"},
            },
        }
        assert count_plan_nodes(plan) == 3

    def test_no_root(self) -> None:
        assert count_plan_nodes({}) == 0

    def test_non_dict_root(self) -> None:
        assert count_plan_nodes({"root": "bad"}) == 0

    def test_nested_tree(self) -> None:
        plan = {
            "root": {
                "searchName": "Combine3",
                "primaryInput": {
                    "searchName": "Combine2",
                    "primaryInput": {"searchName": "Search1"},
                    "secondaryInput": {"searchName": "Search2"},
                },
                "secondaryInput": {"searchName": "Search3"},
            },
        }
        assert count_plan_nodes(plan) == 5

    def test_node_without_search_name_not_counted(self) -> None:
        """Nodes without searchName are not counted."""
        plan = {"root": {"id": "s1"}}  # no searchName
        assert count_plan_nodes(plan) == 0
