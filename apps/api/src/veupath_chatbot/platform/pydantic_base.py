"""Shared Pydantic base models and custom float types for JSON serialization.

All domain/service types that need camelCase JSON output should inherit from
:class:`CamelModel`.  Use :data:`RoundedFloat` (4 dp) or :data:`RoundedFloat2`
(2 dp) for float fields that should be rounded during serialization.  Plain
``float`` fields are serialized at full precision.

WDK returns numeric fields as JSON strings (``"3.48"``, ``"3.40e-13"``) and
sometimes ``"Infinity"``.  Pydantic v2 lax mode already coerces str→int and
str→float.  Use :data:`SafeFiniteFloat` for float fields that must also clamp
``inf``/``nan`` to ``0.0`` (required for JSON serialization and PostgreSQL).
"""

import math
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, PlainSerializer
from pydantic.alias_generators import to_camel


def _clamp_finite(v: object) -> object:
    """Clamp non-finite float values to 0.0, pass everything else through.

    Pydantic lax mode handles str→float coercion. This validator only
    intercepts the result to replace inf/nan with 0.0 — necessary because
    WDK can return ``"Infinity"`` for odds ratios when the denominator is 0.
    """
    if isinstance(v, float) and not math.isfinite(v):
        return 0.0
    if isinstance(v, str):
        try:
            parsed = float(v)
            if not math.isfinite(parsed):
                return 0.0
        except ValueError:
            pass
    return v


class CamelModel(BaseModel):
    """Base model with camelCase JSON aliases.

    Serialization:  ``model.to_dict()`` or ``model.model_dump(by_alias=True)``
    Deserialization: ``Model.model_validate(data)``
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a camelCase dict with None values excluded."""
        return self.model_dump(by_alias=True, exclude_none=True)


RoundedFloat = Annotated[
    float, PlainSerializer(lambda v: round(v, 4), return_type=float)
]
"""Float rounded to 4 decimal places during serialization."""

RoundedFloat2 = Annotated[
    float, PlainSerializer(lambda v: round(v, 2), return_type=float)
]
"""Float rounded to 2 decimal places during serialization."""

SafeFiniteFloat = Annotated[float, BeforeValidator(_clamp_finite)]
"""Float that clamps inf/nan to 0.0 before Pydantic's lax coercion."""

SafeFiniteRoundedFloat = Annotated[
    float,
    BeforeValidator(_clamp_finite),
    PlainSerializer(lambda v: round(v, 4), return_type=float),
]
"""Float that clamps inf/nan AND rounds to 4 dp on serialization."""
