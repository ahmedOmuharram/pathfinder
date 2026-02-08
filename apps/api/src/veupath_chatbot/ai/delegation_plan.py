"""Normalize and validate delegation inputs (nested plan structure).

This is AI-orchestration logic: it validates a model-produced *nested* plan
into a strict, executable shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.domain.strategy.ops import parse_op


@dataclass(frozen=True)
class DelegationPlan:
    goal: str
    tasks: list[dict[str, Any]]
    combines: list[dict[str, Any]]
    nodes_by_id: dict[str, dict[str, Any]]
    dependents: dict[str, list[str]]


def _op_value(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return parse_op(str(value).strip()).value
    except Exception:
        return None


def build_delegation_plan(
    *,
    goal: str,
    plan: dict[str, Any] | None,
) -> DelegationPlan | dict[str, Any]:
    def plan_error(message: str, detail: str, **extra: Any) -> dict[str, Any]:
        return tool_error(
            "DELEGATION_PLAN_INVALID",
            message,
            goal=goal,
            detail=detail,
            **extra,
        )

    if not isinstance(plan, dict):
        return plan_error(
            "plan is required when delegating.",
            "Provide a nested plan object as 'plan'.",
        )

    # Compile nested plan -> DAG nodes.
    node_counter = 0
    tasks: list[dict[str, Any]] = []
    combines: list[dict[str, Any]] = []
    # Structural dedupe: canonical node signature -> generated id
    seen_signatures: dict[str, str] = {}

    def new_id() -> str:
        nonlocal node_counter
        node_counter += 1
        return f"node_{node_counter}"

    def _canon(value: Any) -> Any:
        """Best-effort canonicalization for hashing."""
        if isinstance(value, dict):
            return {str(k): _canon(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
        if isinstance(value, list):
            return [_canon(v) for v in value]
        if isinstance(value, str):
            return value.strip()
        return value

    def compile_node(node: Any) -> str | dict[str, Any]:
        if not isinstance(node, dict):
            return plan_error(
                "Invalid plan node.",
                "Each node must be an object.",
            )
        node_type = str(node.get("type") or node.get("kind") or "").strip().lower()
        # Be forgiving: infer node type when omitted but structure is unambiguous.
        if not node_type:
            if (node.get("operator") is not None or node.get("op") is not None) and (
                node.get("left") is not None
                or node.get("right") is not None
                or node.get("inputs") is not None
            ):
                node_type = "combine"
            elif node.get("task") is not None or node.get("text") is not None:
                node_type = "task"
        if not node_type and node.get("id") is not None:
            # Model attempted an id-only reference. Since we ignore ids, this is invalid.
            return plan_error(
                "Invalid plan node.",
                "Do not use id-only references. Provide a full node object with 'type'.",
            )

        if node_type in ("combine", "op", "operator"):
            op_raw = node.get("operator") or node.get("op")
            operator = _op_value(op_raw)
            if not operator:
                return plan_error(
                    "Invalid combine operator.",
                    "Combine node requires a valid operator.",
                    nodeId=node.get("id"),
                    operator=op_raw,
                )
            inputs_raw = node.get("inputs")
            left = node.get("left")
            right = node.get("right")
            if inputs_raw is not None:
                if not isinstance(inputs_raw, list) or len(inputs_raw) != 2:
                    return plan_error(
                        "Invalid combine inputs.",
                        "Combine node inputs must be a list of exactly 2 child nodes.",
                        nodeId=node.get("id"),
                    )
                left_node, right_node = inputs_raw[0], inputs_raw[1]
            else:
                left_node, right_node = left, right
                if left_node is None or right_node is None:
                    return plan_error(
                        "Invalid combine inputs.",
                        "Combine node requires left and right child nodes.",
                        nodeId=node.get("id"),
                    )

            left_id = compile_node(left_node)
            if isinstance(left_id, dict):
                return left_id
            right_id = compile_node(right_node)
            if isinstance(right_id, dict):
                return right_id

            display_name = node.get("display_name") or node.get("displayName")
            hint = node.get("hint")
            signature_obj = {
                "kind": "combine",
                "operator": operator,
                "inputs": [left_id, right_id],
                "display_name": display_name,
                "hint": hint,
            }
            signature = str(_canon(signature_obj))
            existing = seen_signatures.get(signature)
            if existing:
                return existing
            node_id = new_id()
            seen_signatures[signature] = node_id

            combines.append(
                {
                    "id": node_id,
                    "kind": "combine",
                    "operator": operator,
                    "inputs": [left_id, right_id],
                    "depends_on": [left_id, right_id],
                    "display_name": display_name,
                    "hint": hint,
                    "task": display_name
                    or f"Combine {node_id} ({operator})",
                }
            )
            return node_id

        if node_type in ("task", "step", "subtask"):
            task_text = str(node.get("task") or node.get("text") or "").strip()
            if not task_text:
                return plan_error(
                    "Invalid task node.",
                    "Task node requires a non-empty 'task' string.",
                    nodeId=node.get("id"),
                )
            hint = str(node.get("hint") or "").strip()
            # Optional per-task context that will be passed to the sub-kani as additional
            # structured context (e.g. organism, recordType, dataset ids, constraints).
            # Allow common aliases since models vary: context / parameters / params.
            context = node.get("context")
            if context is None:
                context = node.get("parameters")
            if context is None:
                context = node.get("params")
            if context is not None and not isinstance(context, (dict, list, str, int, float, bool)):
                return plan_error(
                    "Invalid task context.",
                    "Task node 'context' must be a JSON-serializable object/array/string/primitive.",
                    nodeId=node.get("id"),
                    contextType=type(context).__name__,
                )
            input_node = node.get("input")
            depends: list[str] = []
            if input_node is not None:
                child_id = compile_node(input_node)
                if isinstance(child_id, dict):
                    return child_id
                depends = [child_id]

            signature_obj = {
                "kind": "task",
                "task": task_text,
                "hint": hint,
                "context": context,
                "depends_on": depends,
            }
            signature = str(_canon(signature_obj))
            existing = seen_signatures.get(signature)
            if existing:
                return existing
            node_id = new_id()
            seen_signatures[signature] = node_id

            tasks.append(
                {
                    "id": node_id,
                    "kind": "task",
                    "task": task_text,
                    "hint": hint,
                    "context": context,
                    "depends_on": depends,
                }
            )
            return node_id

        return plan_error(
            "Invalid node type.",
            "Node 'type' must be either 'task' or 'combine'.",
            nodeId=node.get("id"),
            nodeType=node_type,
        )

    root_id = compile_node(plan)
    if isinstance(root_id, dict):
        return root_id

    # Build nodes_by_id with explicit kinds; validate DAG.
    nodes_by_id: dict[str, dict[str, Any]] = {}
    for task in tasks:
        nodes_by_id[task["id"]] = {**task}
    for combine in combines:
        nodes_by_id[combine["id"]] = {**combine}

    all_ids = set(nodes_by_id.keys())
    if root_id not in all_ids:
        return plan_error(
            "Invalid root node.",
            "Root id missing after compilation.",
            rootId=root_id,
        )

    indegree: dict[str, int] = {node_id: 0 for node_id in all_ids}
    dependents: dict[str, list[str]] = {node_id: [] for node_id in all_ids}
    for node_id, node in nodes_by_id.items():
        for dep in node.get("depends_on") or []:
            if dep not in all_ids:
                continue
            indegree[node_id] += 1
            dependents[dep].append(node_id)

    queue = [node_id for node_id, count in indegree.items() if count == 0]
    processed = 0
    pending = dict(indegree)
    while queue:
        current = queue.pop()
        processed += 1
        for child in dependents.get(current, []):
            pending[child] -= 1
            if pending[child] == 0:
                queue.append(child)
    if processed != len(all_ids):
        return plan_error(
            "Dependency cycle detected.",
            "Cycle detected in delegation graph (tasks/combines). Replan and retry.",
        )

    return DelegationPlan(
        goal=goal,
        tasks=tasks,
        combines=combines,
        nodes_by_id=nodes_by_id,
        dependents=dependents,
    )

