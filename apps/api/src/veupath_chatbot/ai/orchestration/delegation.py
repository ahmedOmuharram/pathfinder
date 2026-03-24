"""Normalize and validate delegation inputs (nested plan structure).

This is AI-orchestration logic: it validates a model-produced *nested* plan
into a strict, executable shape.
"""

from collections.abc import Callable
from typing import Annotated, Literal, cast

from pydantic import ConfigDict, Discriminator

from veupath_chatbot.domain.strategy.ops import CombineOp, parse_op
from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import (
    JSONArray,
    JSONObject,
    JSONValue,
)

_REQUIRED_COMBINE_INPUTS = 2


# ---------------------------------------------------------------------------
# Compiled node types (output of the plan compiler)
# ---------------------------------------------------------------------------


class CompiledTask(CamelModel):
    """A validated, flat task node in the delegation DAG."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["task"] = "task"
    id: str
    task: str
    instructions: str
    context: JSONValue
    depends_on: tuple[str, ...]


class CompiledCombine(CamelModel):
    """A validated, flat combine node in the delegation DAG."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["combine"] = "combine"
    id: str
    operator: CombineOp
    inputs: tuple[str, str]
    depends_on: tuple[str, ...]
    display_name: str | None
    instructions: str
    task: str


CompiledNode = Annotated[
    CompiledTask | CompiledCombine, Discriminator("kind")
]


# ---------------------------------------------------------------------------
# Delegation plan (compiler output)
# ---------------------------------------------------------------------------


class DelegationPlan(CamelModel):
    model_config = ConfigDict(frozen=True)

    goal: str
    tasks: list[CompiledTask]
    combines: list[CompiledCombine]
    nodes_by_id: dict[str, CompiledNode]
    dependents: dict[str, list[str]]


# ---------------------------------------------------------------------------
# Compiler internals
# ---------------------------------------------------------------------------


def _op_value(value: JSONValue) -> CombineOp | None:
    if value is None:
        return None
    try:
        return parse_op(str(value).strip())
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
    return value.strip() if isinstance(value, str) else value


def _get_field(node: JSONObject, *keys: str, default: JSONValue = None) -> JSONValue:
    """Get field from node with multiple possible keys."""
    for key in keys:
        if key in node:
            return node[key]
    return default


class _PlanCompiler:
    """Stateful compiler that transforms a nested plan tree into a flat DAG."""

    def __init__(self, goal: str) -> None:
        self._goal = goal
        self._node_counter = 0
        self.tasks: list[CompiledTask] = []
        self.combines: list[CompiledCombine] = []
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

    def _dedup_check(self, signature: JSONObject) -> str | None:
        """Return existing node ID for this signature, or None."""
        sig_str = str(_canon(signature))
        return self._seen_signatures.get(sig_str)

    def _register_signature(self, signature: JSONObject, node_id: str) -> None:
        sig_str = str(_canon(signature))
        self._seen_signatures[sig_str] = node_id

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
        self, node: JSONObject
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
        dep_ids, dep_error = (
            self._compile_dependencies(left_node, right_node)
            if error is None
            else ([], error)
        )
        if dep_error is not None:
            return dep_error
        left_id, right_id = dep_ids[0], dep_ids[1]

        display_name_raw = _get_field(node, "display_name", "displayName")
        display_name = str(display_name_raw) if display_name_raw is not None else None
        instructions_raw = _get_field(node, "instructions")
        instructions = str(instructions_raw).strip() if instructions_raw is not None else ""

        signature: JSONObject = {
            "kind": "combine",
            "operator": operator.value,
            "inputs": [left_id, right_id],
            "display_name": display_name,
            "instructions": instructions,
        }
        existing = self._dedup_check(signature)
        if existing:
            return existing

        node_id = self._new_id()
        self._register_signature(signature, node_id)
        task_label = display_name or f"Combine {node_id} ({operator.value})"
        self.combines.append(
            CompiledCombine(
                id=node_id,
                operator=operator,
                inputs=(left_id, right_id),
                depends_on=(left_id, right_id),
                display_name=display_name,
                instructions=instructions,
                task=task_label,
            )
        )
        return node_id

    def _resolve_combine_inputs(
        self, node: JSONObject
    ) -> tuple[JSONValue, JSONValue, JSONObject | None]:
        """Resolve left/right inputs for a combine node.

        Returns (left_node, right_node, error_or_none).
        """
        inputs_raw = _get_field(node, "inputs")
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
        left = _get_field(node, "left")
        right = _get_field(node, "right")
        error = (
            self._plan_error(
                "Invalid combine inputs.",
                "Combine node requires left and right child nodes.",
                nodeId=node.get("id"),
            )
            if left is None or right is None
            else None
        )
        return left, right, error

    def _compile_task_node(self, node: JSONObject) -> str | JSONObject:
        """Compile a task node into the DAG."""
        task_text = str(_get_field(node, "task", "text") or "").strip()
        context = _get_field(node, "context", "parameters", "params")
        instructions = str(_get_field(node, "instructions") or "").strip()
        input_node = _get_field(node, "input")

        if not task_text:
            return self._plan_error(
                "Invalid task node.",
                "Task node requires a non-empty 'task' string.",
                nodeId=node.get("id"),
            )
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
        dep_ids, error = (
            self._compile_dependencies(input_node)
            if input_node is not None
            else ([], None)
        )
        if error is not None:
            return error

        signature: JSONObject = {
            "kind": "task",
            "task": task_text,
            "instructions": instructions,
            "context": context,
            "depends_on": cast("JSONArray", dep_ids),
        }
        existing = self._dedup_check(signature)
        if existing:
            return existing

        node_id = self._new_id()
        self._register_signature(signature, node_id)
        self.tasks.append(
            CompiledTask(
                id=node_id,
                task=task_text,
                instructions=instructions,
                context=context,
                depends_on=tuple(dep_ids),
            )
        )
        return node_id

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
            return self._compile_combine_node(node)
        if node_type in ("task", "step", "subtask"):
            return self._compile_task_node(node)
        return self._plan_error(
            "Invalid node type.",
            "Node 'type' must be either 'task' or 'combine'.",
            nodeId=node.get("id"),
            nodeType=node_type,
        )


# ---------------------------------------------------------------------------
# DAG validation + public entry point
# ---------------------------------------------------------------------------


def _build_nodes_by_id(
    tasks: list[CompiledTask],
    combines: list[CompiledCombine],
) -> dict[str, CompiledNode]:
    """Build a nodes_by_id dict from typed task and combine lists."""
    result: dict[str, CompiledNode] = {}
    for task in tasks:
        result[task.id] = task
    for combine in combines:
        result[combine.id] = combine
    return result


def _validate_dag(
    all_ids: set[str],
    nodes_by_id: dict[str, CompiledNode],
    dependents: dict[str, list[str]],
    plan_error_fn: Callable[..., JSONObject],
) -> JSONObject | None:
    """Topological sort to detect cycles. Returns error if cycle found."""
    indegree: dict[str, int] = dict.fromkeys(all_ids, 0)
    for node_id, node in nodes_by_id.items():
        for dep in node.depends_on:
            if dep in all_ids:
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
    compiler_result = compiler.compile_node(plan)

    if isinstance(compiler_result, dict):
        return compiler_result

    root_id: str = compiler_result
    nodes_by_id = _build_nodes_by_id(compiler.tasks, compiler.combines)

    all_ids = set(nodes_by_id.keys())
    dependents: dict[str, list[str]] = {node_id: [] for node_id in all_ids}
    validation_error: JSONObject | None = (
        plan_error(
            "Invalid root node.",
            "Root id missing after compilation.",
            rootId=root_id,
        )
        if root_id not in all_ids
        else _validate_dag(all_ids, nodes_by_id, dependents, plan_error)
    )
    if validation_error is not None:
        return validation_error

    return DelegationPlan(
        goal=goal,
        tasks=compiler.tasks,
        combines=compiler.combines,
        nodes_by_id=nodes_by_id,
        dependents=dependents,
    )
