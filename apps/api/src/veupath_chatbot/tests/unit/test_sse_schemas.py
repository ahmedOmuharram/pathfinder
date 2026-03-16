"""Unit tests for SSE event payload schemas."""

from veupath_chatbot.transport.http.schemas.sse import (
    MessageEndEventData,
    ModelSelectedEventData,
    OptimizationTrialData,
    SubKaniTaskEndEventData,
    ToolCallStartEventData,
)


def test_subkani_task_end_serializes_with_aliases():
    m = SubKaniTaskEndEventData(task="test", status="done", modelId="openai/gpt-4.1")
    d = m.model_dump(by_alias=True)
    assert d["modelId"] == "openai/gpt-4.1"
    assert "model_id" not in d


def test_optimization_trial_typed():
    trial = OptimizationTrialData(trialNumber=1, score=0.8, recall=0.7)
    d = trial.model_dump(by_alias=True)
    assert d["trialNumber"] == 1
    assert d["score"] == 0.8


def test_message_end_has_all_token_fields():
    m = MessageEndEventData(
        modelId="openai/gpt-4.1",
        promptTokens=100,
        completionTokens=10,
        totalTokens=110,
        cachedTokens=50,
        toolCallCount=2,
        registeredToolCount=42,
        llmCallCount=3,
        subKaniPromptTokens=500,
        subKaniCompletionTokens=50,
        subKaniCallCount=1,
        estimatedCostUsd=0.05,
    )
    d = m.model_dump(by_alias=True)
    assert d["cachedTokens"] == 50
    assert d["llmCallCount"] == 3
    assert d["subKaniPromptTokens"] == 500


def test_tool_call_start_required_fields():
    m = ToolCallStartEventData(id="tc1", name="search")
    d = m.model_dump(by_alias=True)
    assert d["id"] == "tc1"


def test_model_selected_required():
    m = ModelSelectedEventData(modelId="openai/gpt-5")
    d = m.model_dump(by_alias=True)
    assert d["modelId"] == "openai/gpt-5"
