"""Normalize and validate delegation inputs (nested plan structure).

This is AI-orchestration logic: it validates a model-produced *nested* plan
into a strict, executable shape.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from veupath_chatbot.domain.strategy.ops import parse_op
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import (
    JSONArray,
    JSONObject,
    JSONValue,
    as_json_object,
)

_REQUIRED_COMBINE_INPUTS = 2


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
    except ValueError, KeyError:
        return None


def _canon(value: JSONValue) -> JSONValue:
    """Best-effort canonicalization for hashing."""
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


def _get_field(node: JSONObject, *keys: str, default: JSONValue = None) -> JSONValue:
    """Get field from node with multiple possible keys."""
    for key in keys:
        if key in node:
            return node[key]
    return default


def _get_or_create_node_id(
    signature_obj: JSONObject,
    target_list: JSONArray,
    node_data: JSONObject,
    seen_signatures: dict[str, str],
    new_id_fn: Callable[[], str],
    task_formatter: Callable[[str], str] | None = None,
) -> str:
    """Get existing node ID from signature or create new one."""
    signature = str(_canon(signature_obj))
    existing = seen_signatures.get(signature)
    if existing:
        return existing
    node_id = new_id_fn()
    seen_signatures[signature] = node_id
    node_data["id"] = node_id
    if task_formatter is not None:
        node_data["task"] = task_formatter(node_id)
    target_list.append(node_data)
    return node_id


class _PlanCompiler:
    """Stateful compiler that transforms a nested plan tree into a flat DAG."""

    def __init__(self, goal: str) -> None:
        self._goal = goal
        self._node_counter = 0
        self.tasks: JSONArray = []
        self.combines: JSONArray = []
        self._seen_signatures: dict[str, str] = {}

    def _plan_error(self, message: str, detail: str, **extra: JSONValue) -> JSONObject:
        return tool_error(
            "DELEGATION_PLAN_INVALID",
            message,
            goal=self._goal,
            detail=detail,
            **extra,
        )

    def _new_id(self) -> str:
        self._node_counter += 1
        return f"node_{self._node_counter}"

    def _compile_dependencies(
        self, *nodes: JSONValue
    ) -> tuple[list[str], JSONObject | None]:
        """Compile child nodes and return their IDs, or an error."""
        dep_ids: list[str] = []
        for node in nodes:
            if node is None:
                continue
            child_id = self.compile_node(node)
            if isinstance(child_id, dict):
                return [], child_id
            dep_ids.append(child_id)
        return dep_ids, None

    def _infer_node_type(self, node: JSONObject) -> str:
        """Infer node type when not explicitly specified."""
        if (_get_field(node, "operator", "op") is not None) and (
            _get_field(node, "left") is not None
            or _get_field(node, "right") is not None
            or _get_field(node, "inputs") is not None
        ):
            return "combine"
        if _get_field(node, "task", "text") is not None:
            return "task"
        return ""

    def _compile_combine_node(
        self, node: JSONObject, node_type: str
    ) -> str | JSONObject:
        """Compile a combine node into the DAG."""
        op_raw = _get_field(node, "operator", "op")
        operator = _op_value(op_raw)
        if not operator:
            return self._plan_error(
                "Invalid combine operator.",
                "Combine node requires a valid operator.",
                nodeId=node.get("id"),
                operator=op_raw,
            )

        left_node, right_node, error = self._resolve_combine_inputs(node)
        if error is not None:
            return error

        dep_ids, dep_error = self._compile_dependencies(left_node, right_node)
        if dep_error is not None:
            return dep_error
        left_id, right_id = dep_ids[0], dep_ids[1]

        display_name = _get_field(node, "display_name", "displayName")
        instructions = _get_field(node, "instructions")
        combine_node_data: JSONObject = {
            "kind": "combine",
            "operator": operator,
            "inputs": [left_id, right_id],
            "depends_on": cast("JSONArray", [left_id, right_id]),
            "display_name": display_name,
            "instructions": instructions,
            "task": display_name or "",
        }
        combine_signature_obj: JSONObject = {
            "kind": "combine",
            "operator": operator,
            "inputs": [left_id, right_id],
            "display_name": display_name,
            "instructions": instructions,
        }

        def task_formatter(nid: str) -> str:
            display_str = str(display_name) if display_name is not None else ""
            return display_str or f"Combine {nid} ({operator})"

        return _get_or_create_node_id(
            combine_signature_obj,
            self.combines,
            combine_node_data,
            self._seen_signatures,
            self._new_id,
            task_formatter,
        )

    def _resolve_combine_inputs(
        self, node: JSONObject
    ) -> tuple[JSONValue, JSONValue, JSONObject | None]:
        """Resolve left/right inputs for a combine node.

        Returns (left_node, right_node, error_or_none).
        """
        inputs_raw = _get_field(node, "inputs")
        left = _get_field(node, "left")
        right = _get_field(node, "right")
        if inputs_raw is not None:
            if (
                not isinstance(inputs_raw, list)
                or len(inputs_raw) != _REQUIRED_COMBINE_INPUTS
            ):
                return (
                    None,
                    None,
                    self._plan_error(
                        "Invalid combine inputs.",
                        "Combine node inputs must be a list of exactly 2 child nodes.",
                        nodeId=node.get("id"),
                    ),
                )
            return inputs_raw[0], inputs_raw[1], None
        if left is None or right is None:
            return (
                None,
                None,
                self._plan_error(
                    "Invalid combine inputs.",
                    "Combine node requires left and right child nodes.",
                    nodeId=node.get("id"),
                ),
            )
        return left, right, None

    def _compile_task_node(self, node: JSONObject) -> str | JSONObject:
        """Compile a task node into the DAG."""
        task_text = str(_get_field(node, "task", "text") or "").strip()
        if not task_text:
            return self._plan_error(
                "Invalid task node.",
                "Task node requires a non-empty 'task' string.",
                nodeId=node.get("id"),
            )
        instructions = str(_get_field(node, "instructions") or "").strip()
        context = _get_field(node, "context", "parameters", "params")
        if context is not None and not isinstance(
            context, (dict, list, str, int, float, bool)
        ):
            return self._plan_error(
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
            self._compile_dependencies(input_node)
            if input_node is not None
            else ([], None)
        )
        if error is not None:
            return error
        task_depends_json: JSONArray = cast("JSONArray", dep_ids)
        task_node_data: JSONObject = {
            "kind": "task",
            "task": task_text,
            "instructions": instructions,
            "context": context,
            "depends_on": task_depends_json,
        }
        task_signature_obj: JSONObject = {
            "kind": "task",
            "task": task_text,
            "instructions": instructions,
            "context": context,
            "depends_on": task_depends_json,
        }
        return _get_or_create_node_id(
            task_signature_obj,
            self.tasks,
            task_node_data,
            self._seen_signatures,
            self._new_id,
        )

    def compile_node(self, node: JSONValue) -> str | JSONObject:
        """Compile a single plan node (task or combine)."""
        if not isinstance(node, dict):
            return self._plan_error(
                "Invalid plan node.",
                "Each node must be an object.",
            )
        node_type = str(_get_field(node, "type", "kind") or "").strip().lower()
        if not node_type:
            node_type = self._infer_node_type(node)
        if not node_type and node.get("id") is not None:
            return self._plan_error(
                "Invalid plan node.",
                (
                    "Do not use id-only references. "
                    "Provide a full node object with 'type'."
                ),
            )

        if node_type in ("combine", "op", "operator"):
            return self._compile_combine_node(node, node_type)

        if node_type in ("task", "step", "subtask"):
            return self._compile_task_node(node)

        return self._plan_error(
            "Invalid node type.",
            "Node 'type' must be either 'task' or 'combine'.",
            nodeId=node.get("id"),
            nodeType=node_type,
        )


def _build_nodes_by_id(node_list: JSONArray) -> dict[str, JSONObject]:
    """Extract nodes from list into nodes_by_id dict."""
    result: dict[str, JSONObject] = {}
    for node in node_list:
        if isinstance(node, dict):
            node_obj = as_json_object(node)
            node_id = node_obj.get("id")
            if isinstance(node_id, str):
                result[node_id] = node_obj
    return result


def _validate_dag(
    all_ids: set[str],
    nodes_by_id: dict[str, JSONObject],
    dependents: dict[str, list[str]],
    plan_error_fn: Callable[..., JSONObject],
) -> JSONObject | None:
    """Topological sort to detect cycles. Returns error if cycle found."""
    indegree: dict[str, int] = dict.fromkeys(all_ids, 0)
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
        return plan_error_fn(
            "Dependency cycle detected.",
            "Cycle detected in delegation graph (tasks/combines). Replan and retry.",
        )
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

    compiler = _PlanCompiler(goal)
    root_id = compiler.compile_node(plan)
    if isinstance(root_id, dict):
        return root_id

    nodes_by_id: dict[str, JSONObject] = {}
    nodes_by_id.update(_build_nodes_by_id(compiler.tasks))
    nodes_by_id.update(_build_nodes_by_id(compiler.combines))

    all_ids = set(nodes_by_id.keys())
    if root_id not in all_ids:
        return plan_error(
            "Invalid root node.",
            "Root id missing after compilation.",
            rootId=root_id,
        )

    dependents: dict[str, list[str]] = {node_id: [] for node_id in all_ids}
    cycle_error = _validate_dag(all_ids, nodes_by_id, dependents, plan_error)
    if cycle_error is not None:
        return cycle_error

    return DelegationPlan(
        goal=goal,
        tasks=compiler.tasks,
        combines=compiler.combines,
        nodes_by_id=nodes_by_id,
        dependents=dependents,
    )
