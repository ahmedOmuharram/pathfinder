"""The gold corpus the resolver benchmark scores, and the contract a proposer
answers for one step."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Iterable
from pathlib import Path

from pydantic import BaseModel, Field

from pathfinder.ai.tools.standalone.frame_spec import ParamProposals
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.catalog.param_sheet import SheetEntry

_COMBINE_MARKER = "boolean_question"


class GoldStep(CamelModel):
    """One gold step: the search, its label, and the values it was built with."""

    strategy: str
    database: str
    record_type: str
    search_name: str
    label: str
    goal: str = ""
    params: dict[str, str] = Field(default_factory=dict)


class Proposal(BaseModel):
    """One proposer answer: a value or null per visible parameter, and why.
    The bench scores the values; the reason makes the model commit to a reading."""

    values: ParamProposals = Field(default_factory=dict)
    reason: str = ""


Proposer = Callable[[GoldStep, list[SheetEntry], dict[str, str]], Awaitable[Proposal]]
"""Reads one step's parameter sheet, plus the wire values already bound, and
proposes a value or null for every parameter on that sheet."""


def load_gold_steps(gold_dir: Path) -> list[GoldStep]:
    """Read every step that carries parameters from the gold strategy files."""
    steps: list[GoldStep] = []
    for path in sorted(gold_dir.glob("*.json")):
        raw = json.loads(path.read_text())
        ast = raw.get("ast")
        if not isinstance(ast, dict):
            continue
        goal = str((raw.get("prompts") or {}).get("precise") or "")
        steps.extend(
            _walk(
                ast.get("root"),
                strategy=path.stem,
                database=str(raw.get("database") or ""),
                record_type=str(ast.get("recordType") or "transcript"),
                goal=goal,
            )
        )
    return steps


def _walk(
    node: object,
    *,
    strategy: str,
    database: str,
    record_type: str,
    goal: str,
) -> Iterable[GoldStep]:
    if not isinstance(node, dict):
        return
    search = node.get("searchName")
    params = node.get("parameters")
    if (
        isinstance(search, str)
        and _COMBINE_MARKER not in search
        and isinstance(params, dict)
        and params
    ):
        yield GoldStep(
            strategy=strategy,
            database=database,
            record_type=record_type,
            search_name=search,
            label=str(node.get("displayName") or ""),
            goal=goal,
            params={str(k): str(v) for k, v in params.items()},
        )
    for key in ("primaryInput", "secondaryInput"):
        yield from _walk(
            node.get(key),
            strategy=strategy,
            database=database,
            record_type=record_type,
            goal=goal,
        )


def site_id_for(database: str) -> str:
    """Map a gold strategy's database label to a configured site id."""
    return database.strip().lower().replace(" ", "")
