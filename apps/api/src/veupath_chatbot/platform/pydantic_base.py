"""Shared Pydantic base models and custom float types for JSON serialization.

All domain/service types that need camelCase JSON output should inherit from
:class:`CamelModel`.  Use :data:`RoundedFloat` (4 dp) or :data:`RoundedFloat2`
(2 dp) for float fields that should be rounded during serialization.  Plain
``float`` fields are serialized at full precision.
"""

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, PlainSerializer
from pydantic.alias_generators import to_camel


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
