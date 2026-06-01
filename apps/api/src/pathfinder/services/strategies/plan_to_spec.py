"""Convert an APPROVED ``StrategyPlan`` into a ``StrategyStepNode`` tree.

Stage E: when the planning gate has resolved every slot (no NEEDS_*),
execution becomes a deterministic, no-LLM call:

    spec = build_step_tree_from_plan(plan)
    outcome = await build_strategy_from_spec(deps=deps, root=spec)

The conversion is pure (no I/O). It walks the plan's steps + connections
and returns a single recursive ``StrategyStepNode``. Raises
``PlanTopologyError`` for unresolved slots, multiple roots, cycles, or
arity mismatches that ``StrategyPlan.verify_topology`` would have
caught — defense in depth.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from pathfinder.domain.parameters.values import ParamValue
from pathfinder.domain.strategy.ast import (
    COMBINE_SEARCH_NAME,
    StrategyStepNode,
)
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.plan import (
    ParamStatus,
    PlannedConnection,
    PlannedStep,
    PlanTopologyError,
    StepType,
    StrategyPlan,
)


def build_step_tree_from_plan(plan: StrategyPlan) -> StrategyStepNode:
    """Convert a fully-resolved plan into a single ``StrategyStepNode`` tree.

    Raises ``PlanTopologyError`` if the plan has unresolved slots, no
    root, multiple roots, or any topological violation.
    """
    _refuse_if_unresolved_slots(plan)
    inputs_by_step = _index_inputs_by_step(plan.connections)
    root_id = _resolve_root_step(plan)
    by_id = {s.id: s for s in plan.steps}
    return _build_node(root_id, by_id, inputs_by_step)


def _refuse_if_unresolved_slots(plan: StrategyPlan) -> None:
    bad: list[str] = [
        f"{step.id}.{p.name}"
        for step in plan.steps
        for p in step.parameters
        if p.status in (ParamStatus.NEEDS_DISCOVERY, ParamStatus.NEEDS_USER_INPUT)
    ]
    if bad:
        msg = (
            f"Plan {plan.id!r} has unresolved slots and cannot be "
            f"materialized to a step tree: {bad}"
        )
        raise PlanTopologyError(msg)


def _index_inputs_by_step(
    connections: list[PlannedConnection],
) -> dict[str, dict[str, PlannedConnection]]:
    """Return ``{to_step: {input_type: PlannedConnection}}``."""
    out: dict[str, dict[str, PlannedConnection]] = {}
    for conn in connections:
        slot = (
            conn.input_type
            if conn.input_type in ("primary", "secondary")
            else "primary"
        )
        out.setdefault(conn.to_step, {})[slot] = conn
    return out


def _resolve_root_step(plan: StrategyPlan) -> str:
    """Find the unique step that no connection feeds out of (the tree root)."""
    used_as_input = {c.from_step for c in plan.connections}
    roots = [s.id for s in plan.steps if s.id not in used_as_input]
    if len(roots) == 0:
        msg = f"Plan {plan.id!r} has no root step (cycle or empty plan)."
        raise PlanTopologyError(msg)
    if len(roots) > 1:
        msg = (
            f"Plan {plan.id!r} has multiple roots {sorted(roots)!r}; "
            "exactly one root is required to build a step tree."
        )
        raise PlanTopologyError(msg)
    return roots[0]


def _build_node(
    step_id: str,
    by_id: Mapping[str, PlannedStep],
    inputs_by_step: Mapping[str, Mapping[str, PlannedConnection]],
) -> StrategyStepNode:
    step = by_id.get(step_id)
    if step is None:
        msg = f"Step {step_id!r} not found while building tree."
        raise PlanTopologyError(msg)
    inputs = inputs_by_step.get(step_id, {})
    primary = _build_input(inputs.get("primary"), by_id, inputs_by_step)
    secondary = _build_input(inputs.get("secondary"), by_id, inputs_by_step)
    operator = _coerce_operator(
        _operator_string_from_inputs(inputs.values()) or step.operator,
    )
    return StrategyStepNode(
        id=step.id,
        search_name=_search_name(step),
        parameters=_step_parameters_dict(step),
        primary_input=primary,
        secondary_input=secondary,
        operator=operator,
        display_name=step.display_name or None,
    )


def _build_input(
    conn: PlannedConnection | None,
    by_id: Mapping[str, PlannedStep],
    inputs_by_step: Mapping[str, Mapping[str, PlannedConnection]],
) -> StrategyStepNode | None:
    if conn is None:
        return None
    return _build_node(conn.from_step, by_id, inputs_by_step)


def _operator_string_from_inputs(
    conns: Iterable[PlannedConnection],
) -> str | None:
    """If any connection carries an operator, return its string; else None."""
    for conn in conns:
        if conn.operator:
            return conn.operator
    return None


def _coerce_operator(value: str | None) -> CombineOp | None:
    if value is None:
        return None
    try:
        return CombineOp(value)
    except ValueError:
        return None


def _search_name(step: PlannedStep) -> str:
    """Combine steps use the magic ``__combine__`` sentinel; leaves and
    transforms use the planned ``search_name``."""
    if step.step_type == StepType.COMBINE:
        return step.search_name or COMBINE_SEARCH_NAME
    return step.search_name


def _step_parameters_dict(step: PlannedStep) -> dict[str, ParamValue]:
    return {
        p.name: p.value
        for p in step.parameters
        if p.value is not None
        and p.status
        in (
            ParamStatus.SET,
            ParamStatus.USER_SET,
            ParamStatus.DEFAULT,
        )
    }
