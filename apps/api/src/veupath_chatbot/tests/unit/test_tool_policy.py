from veupath_chatbot.services.tool_policy import ToolPolicy


def test_tool_policy_create_search_step_violations() -> None:
    policy = ToolPolicy(
        max_steps_per_strategy=2,
        max_parameters_per_search=1,
        allowed_record_types=["gene"],
        blocked_searches=["blocked_search"],
    )

    res = policy.check_create_search_step(
        record_type="genome",
        search_name="blocked_search",
        parameters={"a": 1, "b": 2},
        current_step_count=2,
    )
    assert res.allowed is False
    codes = {v.code for v in res.violations}
    assert "MAX_STEPS_EXCEEDED" in codes
    assert "RECORD_TYPE_NOT_ALLOWED" in codes
    assert "SEARCH_BLOCKED" in codes
    assert "TOO_MANY_PARAMETERS" in codes


def test_tool_policy_combine_and_build_strategy() -> None:
    policy = ToolPolicy(max_steps_per_strategy=1)

    res = policy.check_combine_steps(operator="UNION", current_step_count=1)
    assert res.allowed is False
    assert any(v.code == "MAX_STEPS_EXCEEDED" for v in res.violations)

    res2 = policy.check_build_strategy(step_count=0)
    assert res2.allowed is False
    assert any(v.code == "EMPTY_STRATEGY" for v in res2.violations)
