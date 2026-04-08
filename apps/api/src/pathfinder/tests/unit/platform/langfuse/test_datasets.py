"""Tests for Langfuse dataset management."""

from unittest.mock import MagicMock, call, patch

from pathfinder.platform.langfuse.datasets import (
    DatasetItemInput,
    run_evaluation_experiment,
    seed_dataset,
)


def test_seed_dataset_noop_when_langfuse_disabled() -> None:
    """No-op when get_langfuse() returns None."""
    with patch(
        "pathfinder.platform.langfuse.datasets.get_langfuse",
        return_value=None,
    ):
        seed_dataset("test-ds", [DatasetItemInput(input={"q": "hello"})])


def test_seed_dataset_creates_and_populates() -> None:
    """Creates dataset then adds each item."""
    mock_client = MagicMock()
    items = [
        DatasetItemInput(
            input={"prompt": "What genes?"},
            expected_output={"genes": ["PF3D7_0100100"]},
            metadata={"source": "gold"},
        ),
        DatasetItemInput(
            input={"prompt": "Another question"},
        ),
    ]
    with patch(
        "pathfinder.platform.langfuse.datasets.get_langfuse",
        return_value=mock_client,
    ):
        seed_dataset("eval-v1", items)

    mock_client.create_dataset.assert_called_once_with(name="eval-v1")
    assert mock_client.create_dataset_item.call_count == 2

    first_call = mock_client.create_dataset_item.call_args_list[0]
    assert first_call == call(
        dataset_name="eval-v1",
        input={"prompt": "What genes?"},
        expected_output={"genes": ["PF3D7_0100100"]},
        metadata={"source": "gold"},
    )

    second_call = mock_client.create_dataset_item.call_args_list[1]
    assert second_call == call(
        dataset_name="eval-v1",
        input={"prompt": "Another question"},
        expected_output=None,
        metadata=None,
    )


def test_seed_dataset_handles_existing_dataset() -> None:
    """Does not fail if create_dataset raises (dataset already exists)."""
    mock_client = MagicMock()
    mock_client.create_dataset.side_effect = OSError("Already exists")
    items = [DatasetItemInput(input={"q": "test"})]
    with patch(
        "pathfinder.platform.langfuse.datasets.get_langfuse",
        return_value=mock_client,
    ):
        seed_dataset("existing-ds", items)

    # Items are still created even when dataset creation fails
    mock_client.create_dataset_item.assert_called_once()


def test_run_experiment_noop_when_disabled() -> None:
    """Returns None when Langfuse is disabled."""
    with patch(
        "pathfinder.platform.langfuse.datasets.get_langfuse",
        return_value=None,
    ):
        result = run_evaluation_experiment(
            dataset_name="ds",
            experiment_name="exp",
            task_fn=lambda item: None,
        )
    assert result is None


def test_run_experiment_delegates_to_dataset_client() -> None:
    """Fetches dataset and calls run_experiment on it."""
    mock_dataset = MagicMock()
    mock_dataset.run_experiment.return_value = "experiment-result"
    mock_client = MagicMock()
    mock_client.get_dataset.return_value = mock_dataset

    task = MagicMock()

    with patch(
        "pathfinder.platform.langfuse.datasets.get_langfuse",
        return_value=mock_client,
    ):
        result = run_evaluation_experiment(
            dataset_name="my-dataset",
            experiment_name="my-experiment",
            task_fn=task,
        )

    mock_client.get_dataset.assert_called_once_with("my-dataset")
    mock_dataset.run_experiment.assert_called_once_with(
        name="my-experiment",
        task=task,
    )
    assert result == "experiment-result"


def test_dataset_item_input_defaults() -> None:
    """DatasetItemInput uses None defaults for optional fields."""
    item = DatasetItemInput(input={"q": "hello"})
    assert item.input == {"q": "hello"}
    assert item.expected_output is None
    assert item.metadata is None
