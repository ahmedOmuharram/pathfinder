"""Unit tests for subkani utils — verifies no global state for round results.

The old implementation stored SubKaniRoundResult in a module-level dict
keyed by task name, causing:
1. Concurrency collisions when two sessions use the same task text
2. Memory leaks when _emit_task_end never fires (timeout, max retries)

The fix returns SubKaniRoundResult directly from consume_subkani_round.
"""

import veupath_chatbot.ai.orchestration.subkani.utils as utils_mod


class TestNoGlobalState:
    """Verify the module-level _last_round_results dict is removed."""

    def test_no_last_round_results_dict(self):
        """Module should not have a _last_round_results attribute."""
        assert not hasattr(utils_mod, "_last_round_results"), (
            "_last_round_results global dict still exists — concurrency bug not fixed"
        )

    def test_no_get_round_result_function(self):
        """Module should not have get_round_result function."""
        assert not hasattr(utils_mod, "get_round_result"), (
            "get_round_result still exists — should pass result through call chain"
        )


class TestConsumeSubkaniRoundReturnType:
    """Verify consume_subkani_round returns SubKaniRoundResult directly."""

    def test_return_annotation_is_subkani_round_result(self):
        """consume_subkani_round should return SubKaniRoundResult, not a tuple."""
        hints = utils_mod.consume_subkani_round.__annotations__
        assert hints.get("return") is utils_mod.SubKaniRoundResult


class TestSubKaniRoundResultDefaults:
    """Verify SubKaniRoundResult initializes with sane defaults."""

    def test_default_values(self):
        result = utils_mod.SubKaniRoundResult()
        assert result.response_text is None
        assert result.created_steps == []
        assert result.errors == []
        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0
        assert result.llm_call_count == 0
