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
"""

from __future__ import annotations

from typing import Protocol

from pydantic import JsonValue

from pathfinder.domain.strategy.validation import StepValidation

DecodedParams = dict[str, JsonValue]
WireParams = dict[str, str]


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
