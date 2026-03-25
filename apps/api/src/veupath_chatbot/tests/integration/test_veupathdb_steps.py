"""Pure domain tests for WDK step tree serialization.

VCR-backed strategy/step CRUD tests are in test_vcr_steps.py.
"""

from veupath_chatbot.integrations.veupathdb.wdk_models import WDKStepTree


class TestWDKStepTree:
    """Tests for WDKStepTree."""

    def test_simple_tree(self) -> None:
        node = WDKStepTree(step_id=100)
        assert node.model_dump(by_alias=True, exclude_none=True, mode="json") == {
            "stepId": 100
        }

    def test_nested_tree(self) -> None:
        tree = WDKStepTree(
            step_id=100,
            primary_input=WDKStepTree(step_id=10),
            secondary_input=WDKStepTree(step_id=11),
        )

        result = tree.model_dump(by_alias=True, exclude_none=True, mode="json")
        assert result["stepId"] == 100
        primary_input_value = result.get("primaryInput")
        assert isinstance(primary_input_value, dict)
        assert primary_input_value["stepId"] == 10
        secondary_input_value = result.get("secondaryInput")
        assert isinstance(secondary_input_value, dict)
        assert secondary_input_value["stepId"] == 11

    def test_deeply_nested_tree(self) -> None:
        tree = WDKStepTree(
            step_id=100,
            primary_input=WDKStepTree(
                step_id=50,
                primary_input=WDKStepTree(step_id=10),
                secondary_input=WDKStepTree(step_id=11),
            ),
        )

        result = tree.model_dump(by_alias=True, exclude_none=True, mode="json")
        primary_input_value = result.get("primaryInput")
        assert isinstance(primary_input_value, dict)
        nested_primary_input_value = primary_input_value.get("primaryInput")
        assert isinstance(nested_primary_input_value, dict)
        assert nested_primary_input_value["stepId"] == 10
