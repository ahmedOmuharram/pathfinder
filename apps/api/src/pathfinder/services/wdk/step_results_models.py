"""Service-layer response models produced by ``StepResultsService``.

Owned by the service (the producer) so transport returns them without the
service importing transport.
"""

from assistant_core.platform.pydantic_base import CamelModel
from pydantic import JsonValue

from pathfinder.domain.wdk_values import WDKRecordIdPart


class RecordAttribute(CamelModel):
    name: str
    display_name: str
    help: str | None
    type: str | None
    is_displayable: bool
    is_sortable: bool
    is_suggested: bool


class AttributesResponse(CamelModel):
    attributes: list[RecordAttribute]
    record_type: str


class RecordDetailResponse(CamelModel):
    display_name: str
    id: list[WDKRecordIdPart]
    record_class_name: str
    attributes: dict[str, JsonValue]
    attribute_names: dict[str, str]
    tables: dict[str, JsonValue]
    table_errors: list[str]
