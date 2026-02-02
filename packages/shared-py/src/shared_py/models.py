"""Shared Pydantic models for Pathfinder - VEuPathDB Strategy Builder."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# Combine Operations
# ============================================================================


class CombineOperator(str, Enum):
    """Set operations for combining two steps."""

    INTERSECT = "INTERSECT"
    UNION = "UNION"
    MINUS_LEFT = "MINUS_LEFT"
    MINUS_RIGHT = "MINUS_RIGHT"
    COLOCATE = "COLOCATE"


COMBINE_OPERATOR_LABELS: dict[CombineOperator, str] = {
    CombineOperator.INTERSECT: "IDs in common (AND)",
    CombineOperator.UNION: "Combined (OR)",
    CombineOperator.MINUS_LEFT: "Not in right",
    CombineOperator.MINUS_RIGHT: "Not in left",
    CombineOperator.COLOCATE: "Genomic colocation",
}


# ============================================================================
# Strategy Plan DSL (AST)
# ============================================================================


class ColocationParams(BaseModel):
    """Parameters for genomic colocation operations."""

    upstream: int = Field(ge=0, description="Upstream distance in base pairs")
    downstream: int = Field(ge=0, description="Downstream distance in base pairs")
    strand: Literal["same", "opposite", "both"] = Field(default="both")


class SearchNode(BaseModel):
    """A search step in the strategy plan."""

    type: Literal["search"] = "search"
    id: str | None = None
    search_name: str = Field(alias="searchName")
    display_name: str | None = Field(default=None, alias="displayName")
    parameters: dict[str, Any]

    model_config = {"populate_by_name": True}


class CombineNode(BaseModel):
    """A combine step that joins two inputs with a set operation."""

    type: Literal["combine"] = "combine"
    id: str | None = None
    display_name: str | None = Field(default=None, alias="displayName")
    operator: CombineOperator
    left: "PlanNode"
    right: "PlanNode"
    colocation_params: ColocationParams | None = Field(
        default=None, alias="colocationParams"
    )

    model_config = {"populate_by_name": True}


class TransformNode(BaseModel):
    """A transform step that modifies its input (e.g., orthology expansion)."""

    type: Literal["transform"] = "transform"
    id: str | None = None
    display_name: str | None = Field(default=None, alias="displayName")
    transform_name: str = Field(alias="transformName")
    input: "PlanNode"
    parameters: dict[str, Any] | None = None

    model_config = {"populate_by_name": True}


PlanNode = Annotated[
    SearchNode | CombineNode | TransformNode, Field(discriminator="type")
]


class StrategyPlanMetadata(BaseModel):
    """Metadata for a strategy plan."""

    name: str | None = None
    description: str | None = None
    site_id: str | None = Field(default=None, alias="siteId")
    created_at: datetime | None = Field(default=None, alias="createdAt")

    model_config = {"populate_by_name": True}


class StrategyPlan(BaseModel):
    """Complete strategy plan with AST root node."""

    record_type: str = Field(alias="recordType")
    root: PlanNode
    metadata: StrategyPlanMetadata | None = None

    model_config = {"populate_by_name": True}


# ============================================================================
# VEuPathDB Site Configuration
# ============================================================================


class VEuPathDBSite(BaseModel):
    """VEuPathDB site configuration."""

    id: str
    name: str
    display_name: str = Field(alias="displayName")
    base_url: str = Field(alias="baseUrl")
    project_id: str = Field(alias="projectId")
    is_portal: bool = Field(alias="isPortal")

    model_config = {"populate_by_name": True}


# ============================================================================
# API Types
# ============================================================================


class RecordType(BaseModel):
    """A record type available in a VEuPathDB site."""

    name: str
    display_name: str = Field(alias="displayName")
    description: str | None = None

    model_config = {"populate_by_name": True}


class SearchParameter(BaseModel):
    """A parameter for a search."""

    name: str
    display_name: str = Field(alias="displayName")
    type: Literal["string", "number", "enum", "multiEnum", "date", "organism"]
    required: bool
    default_value: str | None = Field(default=None, alias="defaultValue")
    allowed_values: list[str] | None = Field(default=None, alias="allowedValues")
    help: str | None = None

    model_config = {"populate_by_name": True}


class Search(BaseModel):
    """A search available in a VEuPathDB site."""

    name: str
    display_name: str = Field(alias="displayName")
    description: str | None = None
    record_type: str = Field(alias="recordType")
    parameters: list[SearchParameter]

    model_config = {"populate_by_name": True}


# ============================================================================
# Strategy Types
# ============================================================================


class Step(BaseModel):
    """A step in a compiled strategy."""

    id: str
    type: Literal["search", "combine", "transform"]
    display_name: str = Field(alias="displayName")
    search_name: str | None = Field(default=None, alias="searchName")
    parameters: dict[str, Any] | None = None
    operator: CombineOperator | None = None
    primary_input_step_id: str | None = Field(default=None, alias="primaryInputStepId")
    secondary_input_step_id: str | None = Field(
        default=None, alias="secondaryInputStepId"
    )
    result_count: int | None = Field(default=None, alias="resultCount")

    model_config = {"populate_by_name": True}


class Strategy(BaseModel):
    """A compiled strategy with steps and tree structure."""

    id: UUID
    name: str
    site_id: str = Field(alias="siteId")
    record_type: str = Field(alias="recordType")
    steps: list[Step]
    root_step_id: str = Field(alias="rootStepId")
    wdk_strategy_id: int | None = Field(default=None, alias="wdkStrategyId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}


class StrategySummary(BaseModel):
    """Summary of a strategy for list views."""

    id: UUID
    name: str
    site_id: str = Field(alias="siteId")
    record_type: str = Field(alias="recordType")
    step_count: int = Field(alias="stepCount")
    result_count: int | None = Field(default=None, alias="resultCount")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}


# ============================================================================
# Chat Types
# ============================================================================


class ToolCall(BaseModel):
    """A tool call made by the assistant."""

    id: str
    name: str
    arguments: dict[str, Any]
    result: str | None = None


class Message(BaseModel):
    """A message in a conversation."""

    role: Literal["user", "assistant", "system"]
    content: str
    tool_calls: list[ToolCall] | None = Field(default=None, alias="toolCalls")
    timestamp: datetime

    model_config = {"populate_by_name": True}


class Conversation(BaseModel):
    """A conversation with message history."""

    id: UUID
    site_id: str = Field(alias="siteId")
    title: str | None = None
    messages: list[Message]
    strategy_id: UUID = Field(alias="strategyId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}


class ChatRequest(BaseModel):
    """Request to send a chat message."""

    conversation_id: UUID | None = Field(default=None, alias="conversationId")
    site_id: str = Field(alias="siteId")
    message: str = Field(min_length=1, max_length=10000)

    model_config = {"populate_by_name": True}


# ============================================================================
# Result Types
# ============================================================================


class PreviewRequest(BaseModel):
    """Request to preview step results."""

    strategy_id: UUID = Field(alias="strategyId")
    step_id: str = Field(alias="stepId")
    limit: int = Field(default=100, ge=1, le=1000)

    model_config = {"populate_by_name": True}


class PreviewResponse(BaseModel):
    """Response with preview of step results."""

    total_count: int = Field(alias="totalCount")
    records: list[dict[str, Any]]
    columns: list[str]

    model_config = {"populate_by_name": True}


class DownloadRequest(BaseModel):
    """Request to download step results."""

    strategy_id: UUID = Field(alias="strategyId")
    step_id: str = Field(alias="stepId")
    format: Literal["csv", "json", "tab"] = "csv"
    attributes: list[str] | None = None

    model_config = {"populate_by_name": True}


class DownloadResponse(BaseModel):
    """Response with download URL."""

    download_url: str = Field(alias="downloadUrl")
    expires_at: datetime = Field(alias="expiresAt")

    model_config = {"populate_by_name": True}


# Rebuild models for forward references
CombineNode.model_rebuild()
TransformNode.model_rebuild()

