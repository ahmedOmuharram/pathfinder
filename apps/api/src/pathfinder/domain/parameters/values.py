from __future__ import annotations

import json
from collections.abc import Callable
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, JsonValue, TypeAdapter, model_validator

from pathfinder.platform.pydantic_base import CamelModel

ParamKind = Literal[
    "string",
    "number",
    "number-range",
    "date",
    "date-range",
    "timestamp",
    "single-pick-vocabulary",
    "multi-pick-vocabulary",
    "filter",
    "input-dataset",
    "input-step",
]


class StringValue(CamelModel):
    type: Literal["string"] = "string"
    value: str

    def to_wire(self) -> str:
        return self.value

    def to_decoded(self) -> JsonValue:
        return self.value


class NumberValue(CamelModel):
    type: Literal["number"] = "number"
    value: float

    def to_wire(self) -> str:
        if self.value.is_integer():
            return str(int(self.value))
        return str(self.value)

    def to_decoded(self) -> JsonValue:
        return self.value


class NumberRangeValue(CamelModel):
    type: Literal["number-range"] = "number-range"
    min: float | None = None
    max: float | None = None

    @model_validator(mode="after")
    def _at_least_one_endpoint(self) -> NumberRangeValue:
        if self.min is None and self.max is None:
            msg = "number-range requires at least one of min/max"
            raise ValueError(msg)
        if self.min is not None and self.max is not None and self.min > self.max:
            msg = f"number-range min ({self.min}) > max ({self.max})"
            raise ValueError(msg)
        return self

    def to_wire(self) -> str:
        payload: dict[str, float] = {}
        if self.min is not None:
            payload["min"] = self.min
        if self.max is not None:
            payload["max"] = self.max
        return json.dumps(payload)

    def to_decoded(self) -> JsonValue:
        payload: dict[str, JsonValue] = {}
        if self.min is not None:
            payload["min"] = self.min
        if self.max is not None:
            payload["max"] = self.max
        return payload


class DateValue(CamelModel):
    type: Literal["date"] = "date"
    value: str = Field(min_length=1)

    def to_wire(self) -> str:
        return self.value

    def to_decoded(self) -> JsonValue:
        return self.value


class DateRangeValue(CamelModel):
    type: Literal["date-range"] = "date-range"
    min: str | None = None
    max: str | None = None

    @model_validator(mode="after")
    def _at_least_one_endpoint(self) -> DateRangeValue:
        if self.min is None and self.max is None:
            msg = "date-range requires at least one of min/max"
            raise ValueError(msg)
        return self

    def to_wire(self) -> str:
        payload: dict[str, str] = {}
        if self.min is not None:
            payload["min"] = self.min
        if self.max is not None:
            payload["max"] = self.max
        return json.dumps(payload)

    def to_decoded(self) -> JsonValue:
        payload: dict[str, JsonValue] = {}
        if self.min is not None:
            payload["min"] = self.min
        if self.max is not None:
            payload["max"] = self.max
        return payload


class TimestampValue(CamelModel):
    type: Literal["timestamp"] = "timestamp"
    value: str = Field(min_length=1)

    def to_wire(self) -> str:
        return self.value

    def to_decoded(self) -> JsonValue:
        return self.value


class SinglePickValue(CamelModel):
    type: Literal["single-pick-vocabulary"] = "single-pick-vocabulary"
    value: str = Field(min_length=1)

    def to_wire(self) -> str:
        return self.value

    def to_decoded(self) -> JsonValue:
        return self.value


class MultiPickValue(CamelModel):
    type: Literal["multi-pick-vocabulary"] = "multi-pick-vocabulary"
    values: list[str] = Field(min_length=1)

    def to_wire(self) -> str:
        return json.dumps(self.values)

    def to_decoded(self) -> JsonValue:
        return list(self.values)


class FilterTermClause(CamelModel):
    model_config = ConfigDict(extra="allow")
    field: str
    value: JsonValue


class FilterValue(CamelModel):
    type: Literal["filter"] = "filter"
    filters: list[FilterTermClause] = Field(default_factory=list)

    def to_wire(self) -> str:
        return json.dumps(
            {"filters": [c.model_dump(by_alias=True, mode="json") for c in self.filters]},
        )

    def to_decoded(self) -> JsonValue:
        return {
            "filters": [c.model_dump(by_alias=True, mode="json") for c in self.filters],
        }


class InputDatasetValue(CamelModel):
    type: Literal["input-dataset"] = "input-dataset"
    dataset_id: str = Field(min_length=1)

    def to_wire(self) -> str:
        return self.dataset_id

    def to_decoded(self) -> JsonValue:
        return self.dataset_id


class InputStepValue(CamelModel):
    type: Literal["input-step"] = "input-step"
    step_id: str = Field(min_length=1)

    def to_wire(self) -> str:
        return self.step_id

    def to_decoded(self) -> JsonValue:
        return self.step_id


ParamValue = Annotated[
    StringValue
    | NumberValue
    | NumberRangeValue
    | DateValue
    | DateRangeValue
    | TimestampValue
    | SinglePickValue
    | MultiPickValue
    | FilterValue
    | InputDatasetValue
    | InputStepValue,
    Field(discriminator="type"),
]




_PARAM_VALUE_ADAPTER: TypeAdapter[ParamValue] = TypeAdapter(ParamValue)
_PARAM_KIND_ADAPTER: TypeAdapter[ParamKind] = TypeAdapter(ParamKind)


def as_param_kind(raw: str) -> ParamKind:
    return _PARAM_KIND_ADAPTER.validate_python(raw)


def _decoded_object(wire: str, kind: str) -> dict[str, JsonValue]:
    decoded: JsonValue = json.loads(wire) if wire else {}
    if not isinstance(decoded, dict):
        msg = f"{kind} wire payload must be a JSON object"
        raise TypeError(msg)
    return decoded


def _multi_pick_payload(w: str) -> dict[str, JsonValue]:
    return {
        "type": "multi-pick-vocabulary",
        "values": list(json.loads(w)) if w else [],
    }


def _number_range_payload(w: str) -> dict[str, JsonValue]:
    return {"type": "number-range", **_decoded_object(w, "number-range")}


def _date_range_payload(w: str) -> dict[str, JsonValue]:
    return {"type": "date-range", **_decoded_object(w, "date-range")}


def _filter_payload(w: str) -> dict[str, JsonValue]:
    body = _decoded_object(w or '{"filters": []}', "filter")
    return {"type": "filter", "filters": body.get("filters", [])}


def _number_payload(w: str) -> dict[str, JsonValue]:
    return {"type": "number", "value": float(w)}


def _input_dataset_payload(w: str) -> dict[str, JsonValue]:
    return {"type": "input-dataset", "dataset_id": w}


def _input_step_payload(w: str) -> dict[str, JsonValue]:
    return {"type": "input-step", "step_id": w}


_WIRE_BUILDERS: dict[ParamKind, Callable[[str], dict[str, JsonValue]]] = {
    "multi-pick-vocabulary": _multi_pick_payload,
    "number-range": _number_range_payload,
    "date-range": _date_range_payload,
    "filter": _filter_payload,
    "number": _number_payload,
    "input-dataset": _input_dataset_payload,
    "input-step": _input_step_payload,
}


def _wire_payload(kind: ParamKind, wire: str) -> dict[str, JsonValue]:
    builder = _WIRE_BUILDERS.get(kind)
    if builder is not None:
        return builder(wire)
    return {"type": kind, "value": wire}


def from_wire(kind: ParamKind, wire: str) -> ParamValue:
    return _PARAM_VALUE_ADAPTER.validate_python(_wire_payload(kind, wire))


def to_wire(value: ParamValue) -> str:
    return value.to_wire()


def wire_map(values: dict[str, ParamValue]) -> dict[str, str]:
    return {name: to_wire(v) for name, v in values.items()}


def from_wire_map(
    wire: dict[str, str], kinds: dict[str, ParamKind],
) -> dict[str, ParamValue]:
    out: dict[str, ParamValue] = {}
    for name, raw in wire.items():
        kind = kinds.get(name)
        if kind is None:
            continue
        out[name] = from_wire(kind, raw)
    return out


def to_decoded(value: ParamValue) -> JsonValue:
    return value.to_decoded()


def to_decoded_map(values: dict[str, ParamValue]) -> dict[str, JsonValue]:
    return {name: v.to_decoded() for name, v in values.items()}


def _normalize_decoded_endpoint(value: JsonValue) -> JsonValue:
    if isinstance(value, str):
        return value or None
    return value


def from_decoded(kind: ParamKind, decoded: JsonValue) -> ParamValue:
    """Build a ``ParamValue`` from a canonicalized decoded JSON shape.

    Inverse of :func:`to_decoded` for canonicalizer outputs:
      * ``string``/``number``/``date``/``timestamp``/``single-pick-vocabulary``/
        ``input-dataset``/``input-step`` accept a scalar wire value.
      * ``multi-pick-vocabulary`` accepts a list of strings.
      * ``number-range``/``date-range`` accept a ``{min?, max?}`` dict.
      * ``filter`` accepts a ``{filters: [...]}`` dict.
    """
    payload: dict[str, JsonValue]
    match kind:
        case "multi-pick-vocabulary":
            values = decoded if isinstance(decoded, list) else [decoded]
            payload = {
                "type": "multi-pick-vocabulary",
                "values": [str(v) for v in values if v is not None],
            }
        case "number-range" | "date-range":
            if not isinstance(decoded, dict):
                msg = f"{kind} requires a dict, got {type(decoded).__name__}"
                raise TypeError(msg)
            payload = {"type": kind}
            min_v = _normalize_decoded_endpoint(decoded.get("min"))
            max_v = _normalize_decoded_endpoint(decoded.get("max"))
            if min_v is not None:
                payload["min"] = min_v
            if max_v is not None:
                payload["max"] = max_v
        case "filter":
            filters: JsonValue = (
                decoded.get("filters", []) if isinstance(decoded, dict) else []
            )
            payload = {"type": "filter", "filters": filters}
        case "number":
            payload = {"type": "number", "value": float(str(decoded))}
        case "input-dataset":
            payload = {"type": "input-dataset", "dataset_id": str(decoded)}
        case "input-step":
            payload = {"type": "input-step", "step_id": str(decoded)}
        case _:
            payload = {"type": kind, "value": str(decoded)}
    return _PARAM_VALUE_ADAPTER.validate_python(payload)
