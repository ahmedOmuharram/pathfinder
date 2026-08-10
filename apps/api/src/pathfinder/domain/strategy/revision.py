"""Fingerprint of what a strategy computes, ignoring what it happened to return.

A chat transcript reports counts that were true at the time of writing. Editing
the strategy afterwards leaves those numbers on screen with nothing marking
them historical. Stamping each assistant turn with the revision it observed,
and comparing that against the live one, is what lets the UI say "superseded"
without rewriting history.

Only inputs are hashed: search names, parameters, combine operators and tree
shape. Counts, WDK ids, validations and display labels are excluded so a
refresh never masquerades as an edit.
"""

from __future__ import annotations

import hashlib
import json

from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.platform.types import JSONObject

__all__ = ["strategy_revision"]

_INPUT_KEYS: tuple[str, ...] = (
    "searchName",
    "parameters",
    "operator",
    "colocationParams",
    "filters",
    "wdkWeight",
    "expandedStrategyId",
)

_REVISION_LENGTH = 16


def _node_inputs(node: StrategyStepNode) -> JSONObject:
    dumped = node.model_dump(
        by_alias=True,
        mode="json",
        exclude_none=True,
        exclude={"primary_input", "secondary_input"},
    )
    inputs: JSONObject = {key: dumped[key] for key in _INPUT_KEYS if key in dumped}
    if node.primary_input is not None:
        inputs["primaryInput"] = _node_inputs(node.primary_input)
    if node.secondary_input is not None:
        inputs["secondaryInput"] = _node_inputs(node.secondary_input)
    return inputs


def strategy_revision(ast: StrategyAst | None) -> str:
    """Return a stable fingerprint of the strategy's inputs, ``""`` if absent."""
    if ast is None:
        return ""
    canonical = json.dumps(
        {
            "recordType": ast.record_type,
            "root": _node_inputs(ast.root),
            # A step added but not yet combined is still a change the agent
            # must not write over, so it has to move the fingerprint.
            "detachedRoots": [_node_inputs(n) for n in ast.detached_roots],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return digest[:_REVISION_LENGTH]
