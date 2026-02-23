"""Normalize and validate delegation inputs (nested plan structure).

This is AI-orchestration logic: it validates a model-produced *nested* plan
into a strict, executable shape.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from veupath_chatbot.domain.strategy.ops import parse_op
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import (
    JSONArray,
    JSONObject,
    JSONValue,
    as_json_object,
)


@dataclass(frozen=True)
class DelegationPlan:
    goal: str
    tasks: JSONArray
    combines: JSONArray
    nodes_by_id: dict[str, JSONObject]
    dependents: dict[str, list[str]]


def _op_value(value: JSONValue) -> str | None:
    if value is None:
        return None
    try:
        return parse_op(str(value).strip()).value
    except Exception:
        return None


def build_delegation_plan(
    *,
    goal: str,
    plan: JSONObject | None,
) -> DelegationPlan | JSONObject:
    def plan_error(message: str, detail: str, **extra: JSONValue) -> JSONObject:
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
    tasks: JSONArray = []
    combines: JSONArray = []
    # Structural dedupe: canonical node signature -> generated id
    seen_signatures: dict[str, str] = {}

    def new_id() -> str:
        nonlocal node_counter
        node_counter += 1
        return f"node_{node_counter}"

    def _canon(value: JSONValue) -> JSONValue:
        """Best-effort canonicalization for hashing.

        :param value: Value to process.

        """
        if isinstance(value, dict):
            return {
                str(k): _canon(v)
                for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))
            }
        if isinstance(value, list):
            return [_canon(v) for v in value]
        if isinstance(value, str):
            return value.strip()
        return value

    def _get_field(
        node: JSONObject, *keys: str, default: JSONValue = None
    ) -> JSONValue:
        """Get field from node with multiple possible keys.

        :param node: Node dict to read from.
        :param keys: Possible keys to try.
        :param default: Default value if no key found.
        :returns: Value at first matching key, or default.
        """
        for key in keys:
            if key in node:
                return node[key]
        return default

    def _compile_dependencies(
        *nodes: JSONValue,
    ) -> tuple[list[str], JSONObject | None]:
        """Compile child nodes and return their IDs, or an error.

        :param nodes: Child nodes to compile.
        :returns: Tuple of dependency IDs and optional error.
        """
        dep_ids: list[str] = []
        for node in nodes:
            if node is None:
                continue
            child_id = compile_node(node)
            if isinstance(child_id, dict):
                return [], child_id
            dep_ids.append(child_id)
        return dep_ids, None

    def _get_or_create_node_id(
        signature_obj: JSONObject,
        target_list: JSONArray,
        node_data: JSONObject,
        task_formatter: Callable[[str], str] | None = None,
    ) -> str:
        """Get existing node ID from signature or create new one.

        :param signature_obj: Object to use for signature matching.
        :param target_list: List to append new nodes to.
        :param node_data: Node data dict (will be modified with id).
        :param task_formatter: Optional function to format task field using node_id.
        :returns: Node ID (existing or newly created).
        """
        signature = str(_canon(signature_obj))
        existing = seen_signatures.get(signature)
        if existing:
            return existing
        node_id = new_id()
        seen_signatures[signature] = node_id
        node_data["id"] = node_id
        if task_formatter is not None:
            node_data["task"] = task_formatter(node_id)
        target_list.append(node_data)
        return node_id

    def compile_node(node: JSONValue) -> str | JSONObject:
        if not isinstance(node, dict):
            return plan_error(
                "Invalid plan node.",
                "Each node must be an object.",
            )
        node_type = str(_get_field(node, "type", "kind") or "").strip().lower()
        # Be forgiving: infer node type when omitted but structure is unambiguous.
        if not node_type:
            if (_get_field(node, "operator", "op") is not None) and (
                _get_field(node, "left") is not None
                or _get_field(node, "right") is not None
                or _get_field(node, "inputs") is not None
            ):
                node_type = "combine"
            elif _get_field(node, "task", "text") is not None:
                node_type = "task"
        if not node_type and node.get("id") is not None:
            # Model attempted an id-only reference.
            # Since we ignore ids, this is invalid.
            return plan_error(
                "Invalid plan node.",
                (
                    "Do not use id-only references. "
                    "Provide a full node object with 'type'."
                ),
            )

        if node_type in ("combine", "op", "operator"):
            op_raw = _get_field(node, "operator", "op")
            operator = _op_value(op_raw)
            if not operator:
                return plan_error(
                    "Invalid combine operator.",
                    "Combine node requires a valid operator.",
                    nodeId=node.get("id"),
                    operator=op_raw,
                )
            inputs_raw = _get_field(node, "inputs")
            left = _get_field(node, "left")
            right = _get_field(node, "right")
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

            dep_ids, error = _compile_dependencies(left_node, right_node)
            if error is not None:
                return error
            left_id, right_id = dep_ids[0], dep_ids[1]

            display_name = _get_field(node, "display_name", "displayName")
            hint = _get_field(node, "hint")
            combine_depends_json: JSONArray = [left_id, right_id]
            combine_node_data: JSONObject = {
                "kind": "combine",
                "operator": operator,
                "inputs": [left_id, right_id],
                "depends_on": combine_depends_json,
                "display_name": display_name,
                "hint": hint,
                "task": display_name or "",  # Will be formatted with node_id if needed
            }
            combine_signature_obj: JSONObject = {
                "kind": "combine",
                "operator": operator,
                "inputs": [left_id, right_id],
                "display_name": display_name,
                "hint": hint,
            }

            def task_formatter(nid: str) -> str:
                display_str = str(display_name) if display_name is not None else ""
                return display_str or f"Combine {nid} ({operator})"

            return _get_or_create_node_id(
                combine_signature_obj, combines, combine_node_data, task_formatter
            )

        if node_type in ("task", "step", "subtask"):
            task_text = str(_get_field(node, "task", "text") or "").strip()
            if not task_text:
                return plan_error(
                    "Invalid task node.",
                    "Task node requires a non-empty 'task' string.",
                    nodeId=node.get("id"),
                )
            hint = str(_get_field(node, "hint") or "").strip()
            # Optional per-task context that will be passed to the sub-kani as
            # additional structured context (e.g. organism, recordType, dataset ids,
            # constraints). Allow common aliases since models vary:
            # context / parameters / params.
            context = _get_field(node, "context", "parameters", "params")
            if context is not None and not isinstance(
                context, (dict, list, str, int, float, bool)
            ):
                return plan_error(
                    "Invalid task context.",
                    (
                        "Task node 'context' must be a JSON-serializable "
                        "object/array/string/primitive."
                    ),
                    nodeId=node.get("id"),
                    contextType=type(context).__name__,
                )
            input_node = _get_field(node, "input")
            dep_ids, error = (
                _compile_dependencies(input_node)
                if input_node is not None
                else ([], None)
            )
            if error is not None:
                return error
            # Convert list[str] to JSONArray (list[JSONValue]) for type compatibility
            from typing import cast

            task_depends_json: JSONArray = cast(JSONArray, dep_ids)

            task_node_data: JSONObject = {
                "kind": "task",
                "task": task_text,
                "hint": hint,
                "context": context,
                "depends_on": task_depends_json,
            }
            task_signature_obj: JSONObject = {
                "kind": "task",
                "task": task_text,
                "hint": hint,
                "context": context,
                "depends_on": task_depends_json,
            }
            return _get_or_create_node_id(task_signature_obj, tasks, task_node_data)

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
    def _build_nodes_by_id(node_list: JSONArray) -> dict[str, JSONObject]:
        """Extract nodes from list into nodes_by_id dict.

        :param node_list: List of nodes.

        """
        result: dict[str, JSONObject] = {}
        for node in node_list:
            if isinstance(node, dict):
                node_obj = as_json_object(node)
                node_id = node_obj.get("id")
                if isinstance(node_id, str):
                    result[node_id] = node_obj
        return result

    nodes_by_id: dict[str, JSONObject] = {}
    nodes_by_id.update(_build_nodes_by_id(tasks))
    nodes_by_id.update(_build_nodes_by_id(combines))

    all_ids = set(nodes_by_id.keys())
    if root_id not in all_ids:
        return plan_error(
            "Invalid root node.",
            "Root id missing after compilation.",
            rootId=root_id,
        )

    indegree: dict[str, int] = dict.fromkeys(all_ids, 0)
    dependents: dict[str, list[str]] = {node_id: [] for node_id in all_ids}
    for node_id, node in nodes_by_id.items():
        depends_on = node.get("depends_on")
        if isinstance(depends_on, list):
            for dep in depends_on:
                if isinstance(dep, str) and dep in all_ids:
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
