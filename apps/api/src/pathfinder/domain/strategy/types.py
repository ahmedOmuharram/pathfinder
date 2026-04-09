"""Domain-native parameter value types and protocols.

Defines ``ParamValue`` and ``SerializedParams`` — Pydantic-aware annotated
types that coerce arbitrary JSON values to ``str`` using pydantic-core union
schemas (no isinstance dispatch in user code).

Also defines ``SyncStateProtocol`` — a structural protocol for WDK sync state
so that domain code (``StrategySession``) can hold and access sync state
fields without importing service-layer types.

These replace the integration-layer ``WDKSerializedParams`` / ``WdkParamValue``
so that ``PlanStepNode.parameters`` carries no integration imports.
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Protocol

from pydantic import BeforeValidator, GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from pathfinder.domain.strategy.validation import StepValidation


def _json_encode(v: object) -> str:
    """JSON-serialize a non-string value."""
    return json.dumps(v, ensure_ascii=False)


class _ParamValueSchema:
    """Pydantic-core custom type: coerces any JSON value to str.

    Uses pydantic-core union schema: strings pass through via
    ``str_schema()``, all other types fall through to ``_json_encode``
    which produces their JSON representation.
    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        return core_schema.union_schema([
            core_schema.str_schema(),
            core_schema.no_info_plain_validator_function(_json_encode),
        ])


ParamValue = Annotated[str, _ParamValueSchema]
"""Single parameter value: str passthrough, non-str → json.dumps."""


def _parse_json_dict(v: object) -> dict[str, object] | object:
    """Parse double-serialized JSON dicts from LLMs.

    Only accepts dicts from parsed JSON (not arrays or scalars).
    Non-string input or non-dict parse results pass through unchanged.
    """
    if not isinstance(v, str):
        return v
    try:
        parsed = json.loads(v)
    except (json.JSONDecodeError, ValueError):
        return v
    return parsed if isinstance(parsed, dict) else v


SerializedParams = Annotated[
    dict[str, ParamValue],
    BeforeValidator(lambda v: v if v is not None else {}),
    BeforeValidator(_parse_json_dict),
]
"""dict[str, str] with automatic coercion from JSON values.

Handles: None → {}, double-serialized JSON strings → dict,
per-value coercion (int/float/bool/list/dict → JSON string).
"""


# ---------------------------------------------------------------------------
# Sync state protocol
# ---------------------------------------------------------------------------


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
