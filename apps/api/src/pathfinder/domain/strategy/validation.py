"""Domain-native step validation types.

Defines ``StepValidation`` and ``StepValidationErrors`` — the domain
representation of WDK step/search/strategy validation state.  These are
pure data types (frozen, no I/O) that happen to match the shape returned
by the WDK REST API.

Previously defined in ``integrations.veupathdb.wdk_models`` as
``WDKValidation`` / ``WDKValidationErrors``, they were stranded in the
wrong layer.  Validation state ("is this step valid, and what are the
error messages?") is a domain concept, not an integration concern.

Moving them here lets ``SyncStateProtocol`` declare ``step_validations``
without importing from the integration layer, eliminating the isinstance
narrowing that was required at every read site.
"""

from pydantic import ConfigDict, Field

from pathfinder.platform.pydantic_base import CamelModel


class StepValidationErrors(CamelModel):
    """Validation error details for a step."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    general: list[str] = Field(default_factory=list)
    by_key: dict[str, list[str]] = Field(default_factory=dict)


class StepValidation(CamelModel):
    """Step/search/strategy validation state."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    level: str = "NONE"
    is_valid: bool = True
    errors: StepValidationErrors | None = None
