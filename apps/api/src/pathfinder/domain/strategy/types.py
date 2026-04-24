"""Domain-native parameter value types and protocols.

Two shapes:

* ``DecodedParams = dict[str, JsonValue]`` — in-memory domain format. Values
  keep their natural JSON types (scalars, lists, numbers, booleans).
  Everything inside the domain/services layer uses this.
* ``WireParams = dict[str, str]`` — WDK over-the-wire format. Matches
  WDK's own ``SearchConfig.parameters: Record<string, ParameterValue>``
  where ``ParameterValue = string``. Only produced at integration write
  boundaries; only consumed at integration read boundaries.

Encoding/decoding between the two lives in
``pathfinder.integrations.veupathdb.value_decoding``.

``DecodedParamsField`` is the canonical Annotated type for any model field
or tool argument that holds parameter values. Its ``BeforeValidator`` decodes
JSON-encoded list/object strings (the WDK wire form) back into native
Python types. This single validator defends every entry point — HTTP request
bodies, DB load via ``model_validate``, LLM tool args — against wire-form
leaks. Always use ``DecodedParamsField`` instead of the bare
``DecodedParams`` alias on a field.
"""

from __future__ import annotations

import json
from typing import Annotated, Protocol

from pydantic import BeforeValidator, JsonValue

from pathfinder.domain.strategy.validation import StepValidation

DecodedParams = dict[str, JsonValue]
WireParams = dict[str, str]

_MIN_JSON_WRAPPER_LEN = 2


def decode_wire_value(value: JsonValue) -> JsonValue:
    """Decode one wire-form value into its native Python type.

    A "wire form" value is a string that JSON-encodes a list or object —
    the shape WDK requires on the HTTP boundary and that legacy DB rows /
    older LLM emissions still carry. Anything else passes through unchanged.
    """
    if not isinstance(value, str):
        return value
    if len(value) < _MIN_JSON_WRAPPER_LEN:
        return value
    if value[0] not in "[{" or value[-1] not in "]}":
        return value
    try:
        decoded: JsonValue = json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return value
    return decoded


def decode_wire_dict(params: object) -> object:
    """Decode every wire-form value in *params* into native Python types.

    Pass-through for non-dict input so it composes safely as a Pydantic
    ``BeforeValidator`` — letting the field's standard validation surface
    its own type error rather than masking it.
    """
    if not isinstance(params, dict):
        return params
    return {k: decode_wire_value(v) for k, v in params.items()}


DecodedParamsField = Annotated[
    DecodedParams,
    BeforeValidator(decode_wire_dict),
]
"""Canonical Annotated type for parameter-value fields. Use everywhere."""


class SyncStateProtocol(Protocol):
    """Structural contract for WDK synchronization state.

    Defined in the domain layer so ``StrategySession`` can hold typed sync
    state without importing service-layer ``WDKSyncState``.  The concrete
    ``WDKSyncState`` dataclass satisfies this protocol structurally.

    Service-layer functions that mutate sync state or need WDK-specific
    fields (``wdk_step_tree``) accept the concrete ``WDKSyncState`` type
    directly.
    """

    @property
    def wdk_strategy_id(self) -> int | None: ...
    @property
    def step_counts(self) -> dict[str, int | None]: ...
    @property
    def wdk_step_ids(self) -> dict[str, int]: ...
    @property
    def wdk_push_errors(self) -> dict[str, str]: ...
    @property
    def step_validations(self) -> dict[str, StepValidation]: ...
