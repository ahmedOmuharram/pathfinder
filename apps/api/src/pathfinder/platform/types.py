from typing import Literal

from pydantic import JsonValue

type JSONObject = dict[str, JsonValue]
type JSONArray = list[JsonValue]

ModelProvider = Literal["openai", "anthropic", "google", "ollama", "mock"]
ReasoningEffort = Literal["none", "low", "medium", "high"]
TierName = Literal["quality", "balanced", "fast"]


def as_json_object(value: JsonValue) -> JSONObject:
    if not isinstance(value, dict):
        msg = f"Expected dict, got {type(value)}"
        raise TypeError(msg)
    return value


def as_json_array(value: JsonValue) -> JSONArray:
    if not isinstance(value, list):
        msg = f"Expected list, got {type(value)}"
        raise TypeError(msg)
    return value
