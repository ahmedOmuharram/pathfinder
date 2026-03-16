"""Tests for ai.models.pricing — cost estimation utilities."""

from veupath_chatbot.ai.models.pricing import estimate_cost


def test_estimate_cost_known_model():
    cost = estimate_cost(
        "openai/gpt-4.1", prompt_tokens=1_000_000, completion_tokens=100_000
    )
    assert cost == 2.8


def test_estimate_cost_with_cached_tokens():
    cost = estimate_cost(
        "openai/gpt-4.1",
        prompt_tokens=1_000_000,
        completion_tokens=0,
        cached_tokens=500_000,
    )
    assert cost == 1.25


def test_estimate_cost_unknown_model():
    cost = estimate_cost("unknown/model", prompt_tokens=1000, completion_tokens=1000)
    assert cost == 0.0
