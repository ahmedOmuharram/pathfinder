"""Comprehensive test: every SSE schema serializes with camelCase aliases."""

import pytest
from pydantic import BaseModel, ValidationError

from veupath_chatbot.transport.http.schemas.optimization import (
    OptimizationParameterSpecData,
    OptimizationProgressEventData,
    OptimizationTrialData,
)
from veupath_chatbot.transport.http.schemas.sse import (
    AssistantDeltaEventData,
    AssistantMessageEventData,
    CitationsEventData,
    ErrorEventData,
    ExecutorBuildRequestEventData,
    GeneSetSummary,
    GraphClearedEventData,
    GraphPlanEventData,
    GraphSnapshotEventData,
    MessageEndEventData,
    MessageStartEventData,
    ModelSelectedEventData,
    PlanningArtifactEventData,
    ReasoningEventData,
    StrategyLinkEventData,
    StrategyMetaEventData,
    StrategyUpdateEventData,
    SubKaniTaskEndEventData,
    SubKaniTaskStartEventData,
    SubKaniToolCallEndEventData,
    SubKaniToolCallStartEventData,
    TokenUsagePartialEventData,
    ToolCallEndEventData,
    ToolCallStartEventData,
    UserMessageEventData,
    WorkbenchGeneSetEventData,
)


def _has_snake_case_key(dumped: dict) -> str | None:
    """Return the first snake_case key found, or None if all are camelCase."""
    for key in dumped:
        if "_" in key and not key.startswith("_"):
            return key
    return None


def _check_nested(dumped: dict) -> str | None:
    """Recursively check for snake_case keys in nested dicts and lists."""
    for key, value in dumped.items():
        if "_" in key and not key.startswith("_"):
            return key
        if isinstance(value, dict):
            found = _check_nested(value)
            if found:
                return found
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    found = _check_nested(item)
                    if found:
                        return found
    return None


# All SSE models with minimal data needed for construction.
MODELS_WITH_MINIMAL_DATA: list[tuple[type[BaseModel], dict]] = [
    # Message lifecycle
    (MessageStartEventData, {}),
    (UserMessageEventData, {}),
    (AssistantDeltaEventData, {}),
    (AssistantMessageEventData, {}),
    (MessageEndEventData, {}),
    # Tool calls
    (ToolCallStartEventData, {"id": "tc1", "name": "search"}),
    (ToolCallEndEventData, {"id": "tc1"}),
    # Sub-kani events
    (SubKaniTaskStartEventData, {}),
    (SubKaniToolCallStartEventData, {"id": "tc2", "name": "sub_tool"}),
    (SubKaniToolCallEndEventData, {"id": "tc2"}),
    (SubKaniTaskEndEventData, {}),
    # Token usage / model selection
    (TokenUsagePartialEventData, {}),
    (ModelSelectedEventData, {"modelId": "openai/gpt-4.1"}),
    # Error
    (ErrorEventData, {"error": "something broke"}),
    # Strategy / graph events
    (GraphSnapshotEventData, {}),
    (StrategyMetaEventData, {}),
    (GraphPlanEventData, {}),
    (StrategyUpdateEventData, {}),
    (StrategyLinkEventData, {}),
    (GraphClearedEventData, {}),
    (ExecutorBuildRequestEventData, {}),
    # Workbench gene sets
    (GeneSetSummary, {}),
    (WorkbenchGeneSetEventData, {}),
    # Miscellaneous
    (CitationsEventData, {}),
    (PlanningArtifactEventData, {}),
    (ReasoningEventData, {}),
    # Optimization (re-exported)
    (OptimizationTrialData, {"trialNumber": 1}),
    (OptimizationParameterSpecData, {"name": "threshold", "type": "numeric"}),
    (
        OptimizationProgressEventData,
        {"optimizationId": "opt-1"},
    ),
]


@pytest.mark.parametrize(
    "model_cls,data",
    MODELS_WITH_MINIMAL_DATA,
    ids=[cls.__name__ for cls, _ in MODELS_WITH_MINIMAL_DATA],
)
def test_model_serializes_with_camel_case(model_cls: type[BaseModel], data: dict):
    """Every SSE model must serialize with camelCase keys (no snake_case)."""
    instance = model_cls(**data)
    dumped = instance.model_dump(by_alias=True)
    snake_key = _has_snake_case_key(dumped)
    assert snake_key is None, (
        f"snake_case key found in {model_cls.__name__}: {snake_key}"
    )


@pytest.mark.parametrize(
    "model_cls,data",
    MODELS_WITH_MINIMAL_DATA,
    ids=[cls.__name__ for cls, _ in MODELS_WITH_MINIMAL_DATA],
)
def test_model_can_roundtrip(model_cls: type[BaseModel], data: dict):
    """Every model should be reconstructable from its own dump."""
    instance = model_cls(**data)
    dumped = instance.model_dump(by_alias=True)
    reconstructed = model_cls(**dumped)
    assert reconstructed.model_dump(by_alias=True) == dumped


class TestMessageEndEventDataFields:
    """MessageEndEventData has the most fields — verify each alias."""

    def test_all_aliases(self):
        instance = MessageEndEventData(
            modelId="openai/gpt-4.1",
            promptTokens=100,
            completionTokens=20,
            totalTokens=120,
            cachedTokens=10,
            toolCallCount=3,
            registeredToolCount=15,
            llmCallCount=2,
            subKaniPromptTokens=50,
            subKaniCompletionTokens=10,
            subKaniCallCount=1,
            estimatedCostUsd=0.005,
        )
        dumped = instance.model_dump(by_alias=True)
        expected_keys = {
            "modelId",
            "promptTokens",
            "completionTokens",
            "totalTokens",
            "cachedTokens",
            "toolCallCount",
            "registeredToolCount",
            "llmCallCount",
            "subKaniPromptTokens",
            "subKaniCompletionTokens",
            "subKaniCallCount",
            "estimatedCostUsd",
        }
        assert set(dumped.keys()) == expected_keys


class TestModelSelectedRequiresModelId:
    """ModelSelectedEventData requires modelId."""

    def test_requires_model_id(self):
        with pytest.raises(ValidationError):
            ModelSelectedEventData()

    def test_accepts_model_id(self):
        instance = ModelSelectedEventData(modelId="anthropic/claude-4-opus")
        assert instance.model_id == "anthropic/claude-4-opus"


class TestPopulateByName:
    """All models support construction with Python field names too."""

    def test_message_end_python_names(self):
        instance = MessageEndEventData(
            model_id="test",
            prompt_tokens=10,
            completion_tokens=5,
        )
        assert instance.model_id == "test"
        assert instance.prompt_tokens == 10

    def test_strategy_link_python_names(self):
        instance = StrategyLinkEventData(
            graph_id="g1",
            wdk_strategy_id=123,
            wdk_url="https://example.com",
        )
        dumped = instance.model_dump(by_alias=True)
        assert dumped["graphId"] == "g1"
        assert dumped["wdkStrategyId"] == 123
        assert dumped["wdkUrl"] == "https://example.com"
