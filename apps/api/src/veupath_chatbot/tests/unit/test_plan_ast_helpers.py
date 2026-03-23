"""Tests for plan AST helpers in domain/strategy/plan_ast.py."""

from veupath_chatbot.domain.strategy.plan_ast import count_plan_nodes


class TestCountPlanNodes:
    def test_single_node(self) -> None:
        plan = {
            "recordType": "gene",
            "root": {"searchName": "GenesByTextSearch", "id": "s1"},
        }
        assert count_plan_nodes(plan) == 1

    def test_three_node_tree(self) -> None:
        plan = {
            "recordType": "gene",
            "root": {
                "searchName": "GenesBooleanQuestion",
                "id": "s3",
                "operator": "INTERSECT",
                "primaryInput": {
                    "searchName": "GenesByTextSearch",
                    "id": "s1",
                },
                "secondaryInput": {
                    "searchName": "GenesByOrthologs",
                    "id": "s2",
                },
            },
        }
        assert count_plan_nodes(plan) == 3

    def test_no_root(self) -> None:
        assert count_plan_nodes({}) == 0

    def test_non_dict_root(self) -> None:
        assert count_plan_nodes({"root": "bad"}) == 0

    def test_nested_tree(self) -> None:
        plan = {
            "recordType": "gene",
            "root": {
                "searchName": "Combine3",
                "id": "s5",
                "operator": "UNION",
                "primaryInput": {
                    "searchName": "Combine2",
                    "id": "s4",
                    "operator": "INTERSECT",
                    "primaryInput": {"searchName": "Search1", "id": "s1"},
                    "secondaryInput": {"searchName": "Search2", "id": "s2"},
                },
                "secondaryInput": {"searchName": "Search3", "id": "s3"},
            },
        }
        assert count_plan_nodes(plan) == 5

    def test_invalid_plan_returns_zero(self) -> None:
        assert count_plan_nodes({"root": {"id": "s1"}}) == 0
