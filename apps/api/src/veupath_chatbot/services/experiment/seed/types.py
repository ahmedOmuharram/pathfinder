"""Shared types for seed definitions."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ControlSetDef:
    name: str
    positive_ids: list[str]
    negative_ids: list[str]
    provenance_notes: str
    tags: list[str] = field(default_factory=list)


@dataclass
class SeedDef:
    name: str
    description: str
    site_id: str
    step_tree: dict[str, Any]
    control_set: ControlSetDef
    record_type: str = "transcript"
