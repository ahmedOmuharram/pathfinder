"""Structural stand-ins for the EDA wire shapes the pure predicates walk."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Var:
    id: str
    type: str = "string"
    display_name: str = ""
    display_type: str = "default"
    parent_id: str | None = None
    vocabulary: list[str] | None = None
    is_multi_valued: bool = False
    data_shape: str | None = None


@dataclass(frozen=True)
class Ent:
    id: str
    display_name: str = ""
    variables: list[Var] = field(default_factory=list)
    children: list["Ent"] = field(default_factory=list)


@dataclass(frozen=True)
class Study:
    id: str
    root_entity: Ent
