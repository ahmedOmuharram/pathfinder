"""Sites request/response DTOs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, RootModel


class SiteResponse(BaseModel):
    """VEuPathDB site information."""

    id: str
    name: str
    display_name: str = Field(alias="displayName")
    base_url: str = Field(alias="baseUrl")
    project_id: str = Field(alias="projectId")
    is_portal: bool = Field(alias="isPortal")

    model_config = {"populate_by_name": True}


class RecordTypeResponse(BaseModel):
    """Record type information."""

    name: str
    display_name: str = Field(alias="displayName")
    description: str | None = None

    model_config = {"populate_by_name": True}


class SearchResponse(BaseModel):
    """Search information."""

    name: str
    display_name: str = Field(alias="displayName")
    description: str | None = None
    record_type: str = Field(alias="recordType")

    model_config = {"populate_by_name": True}


class DependentParamsRequest(BaseModel):
    """Dependent parameter values request."""

    parameter_name: str = Field(alias="parameterName")
    context_values: dict[str, Any] = Field(default_factory=dict, alias="contextValues")

    model_config = {"populate_by_name": True}


class SearchDetailsResponse(BaseModel):
    """Search details payload (UI-facing)."""

    search_data: dict[str, Any] | None = Field(default=None, alias="searchData")
    validation: dict[str, Any] | None = None
    search_config: dict[str, Any] | None = Field(default=None, alias="searchConfig")
    parameters: list[dict[str, Any]] | None = None
    param_map: dict[str, Any] | None = Field(default=None, alias="paramMap")
    question: dict[str, Any] | None = None

    model_config = {"populate_by_name": True, "extra": "allow"}


class DependentParamsResponse(RootModel[list[dict[str, Any]]]):
    """Dependent parameter values response."""


class SearchValidationRequest(BaseModel):
    """Search parameter validation request."""

    context_values: dict[str, Any] = Field(default_factory=dict, alias="contextValues")

    model_config = {"populate_by_name": True}


class SearchValidationErrors(BaseModel):
    general: list[str] = Field(default_factory=list)
    by_key: dict[str, list[str]] = Field(default_factory=dict, alias="byKey")

    model_config = {"populate_by_name": True}


class SearchValidationPayload(BaseModel):
    is_valid: bool = Field(alias="isValid")
    normalized_context_values: dict[str, Any] = Field(
        default_factory=dict, alias="normalizedContextValues"
    )
    errors: SearchValidationErrors = Field(default_factory=SearchValidationErrors)

    model_config = {"populate_by_name": True}


class SearchValidationResponse(BaseModel):
    """Stable validation response for UI consumption."""

    validation: SearchValidationPayload

    model_config = {"populate_by_name": True}


class ParamSpecResponse(BaseModel):
    """Normalized parameter spec (UI-friendly)."""

    name: str
    display_name: str | None = Field(default=None, alias="displayName")
    type: str
    allow_empty_value: bool = Field(default=False, alias="allowEmptyValue")
    min_selected_count: int | None = Field(default=None, alias="minSelectedCount")
    max_selected_count: int | None = Field(default=None, alias="maxSelectedCount")
    count_only_leaves: bool = Field(default=False, alias="countOnlyLeaves")
    vocabulary: Any | None = None

    model_config = {"populate_by_name": True}
