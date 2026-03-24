"""Step request/response DTOs."""

from pydantic import BaseModel, Field


class PrimaryKeyPart(BaseModel):
    """A single part of a composite WDK primary key."""

    name: str
    value: str


class RecordDetailRequest(BaseModel):
    """Request to fetch a single record by primary key."""

    primary_key: list[PrimaryKeyPart] = Field(alias="primaryKey", min_length=1)

    model_config = {"populate_by_name": True}
