"""Normalize and validate delegation inputs (subtasks + optional combines).

This is AI-orchestration logic: it validates a model-produced plan into a strict,
executable shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.domain.strategy.ops import parse_op


@dataclass(frozen=True)
class DelegationPlan:
    goal: str
    post_plan: str | None
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
    subtasks: list[dict[str, Any] | str] | None,
    post_plan: str | None,
    combines: list[dict[str, Any]] | None,
) -> DelegationPlan | dict[str, Any]:
    def plan_error(message: str, detail: str, **extra: Any) -> dict[str, Any]:
        return tool_error(
            "DELEGATION_PLAN_INVALID",
            message,
            goal=goal,
            postPlan=post_plan,
            detail=detail,
            **extra,
        )

    if not subtasks:
        return plan_error(
            "Subtasks are required when delegating.",
            "Provide a non-empty 'subtasks' list instead of only 'goal'.",
        )
    if not (post_plan and post_plan.strip()) and not combines:
        return plan_error(
            "A combine plan or post_plan is required when delegating.",
            "Provide 'combines' for union/intersect/minus steps or a short post_plan.",
        )

    raw_tasks = [task for task in subtasks if task]
    if not raw_tasks:
        return plan_error(
            "Subtasks are required when delegating.",
            "Subtasks list must include at least one non-empty string.",
        )

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for index, item in enumerate(raw_tasks, start=1):
        if isinstance(item, str):
            task_id = f"task_{index}"
            task_text = item.strip()
            depends_on: list[str] = []
            how = None
        elif isinstance(item, dict):
            task_id = str(item.get("id") or f"task_{index}").strip()
            task_text = str(item.get("task") or item.get("text") or "").strip()
            depends_raw = item.get("depends_on") or item.get("dependsOn") or []
            if isinstance(depends_raw, str):
                depends_on = [depends_raw.strip()] if depends_raw.strip() else []
            elif isinstance(depends_raw, list):
                depends_on = [str(dep).strip() for dep in depends_raw if str(dep).strip()]
            else:
                depends_on = []
            how = item.get("how")
        else:
            continue

        if not task_text:
            continue

        normalized_how = None
        if how is not None:
            if not depends_on:
                return plan_error(
                    "How requires dependencies.",
                    f"Subtask '{task_id}' how requires depends_on.",
                )

            normalized_how = []
            if isinstance(how, str):
                if len(depends_on) != 1:
                    return plan_error(
                        "How must provide one operator per dependency.",
                        (
                            f"Subtask '{task_id}' has {len(depends_on)} dependencies "
                            f"({', '.join(depends_on)}). Provide one operator per dependency."
                        ),
                    )
                op = _op_value(how)
                if not op:
                    return plan_error(
                        "Invalid how operator.",
                        f"Subtask '{task_id}' how operator must be a valid combine op.",
                    )
                normalized_how.append({"depends_on": depends_on[0], "operator": op})
            elif isinstance(how, list):
                if len(how) != len(depends_on):
                    return plan_error(
                        "How must provide one operator per dependency.",
                        (
                            f"Subtask '{task_id}' has {len(depends_on)} dependencies "
                            f"({', '.join(depends_on)}) but {len(how)} how entries."
                        ),
                    )
                for dep_id, entry in zip(depends_on, how):
                    op = None
                    if isinstance(entry, str):
                        op = _op_value(entry)
                    elif isinstance(entry, dict):
                        op = _op_value(entry.get("operator") or entry.get("op") or entry.get("combine"))
                    if not op:
                        return plan_error(
                            "Invalid how operator.",
                            f"Subtask '{task_id}' how operator must be a valid combine op.",
                        )
                    normalized_how.append({"depends_on": dep_id, "operator": op})
            elif isinstance(how, dict):
                has_operator_key = any(key in how for key in ("operator", "op", "combine"))
                if has_operator_key:
                    if len(depends_on) != 1:
                        return plan_error(
                            "How must provide one operator per dependency.",
                            (
                                f"Subtask '{task_id}' has {len(depends_on)} dependencies "
                                f"({', '.join(depends_on)}). Provide one operator per dependency."
                            ),
                        )
                    op = _op_value(how.get("operator") or how.get("op") or how.get("combine"))
                    if not op:
                        return plan_error(
                            "Invalid how operator.",
                            f"Subtask '{task_id}' how operator must be a valid combine op.",
                        )
                    normalized_how.append({"depends_on": depends_on[0], "operator": op})
                else:
                    for dep_id in depends_on:
                        if dep_id not in how:
                            return plan_error(
                                "How must provide one operator per dependency.",
                                (
                                    f"Subtask '{task_id}' how is missing operator for dependency '{dep_id}'."
                                ),
                            )
                        entry = how.get(dep_id)
                        op = None
                        if isinstance(entry, str):
                            op = _op_value(entry)
                        elif isinstance(entry, dict):
                            op = _op_value(entry.get("operator") or entry.get("op") or entry.get("combine"))
                        if not op:
                            return plan_error(
                                "Invalid how operator.",
                                f"Subtask '{task_id}' how operator must be a valid combine op.",
                            )
                        normalized_how.append({"depends_on": dep_id, "operator": op})
            else:
                return plan_error(
                    "Invalid how field.",
                    f"Subtask '{task_id}' how must be a string, list, or object.",
                )

        if task_id in seen_ids:
            return plan_error(
                "Duplicate subtask id.",
                f"Subtask id '{task_id}' appears more than once.",
            )
        seen_ids.add(task_id)
        normalized.append(
            {"id": task_id, "task": task_text, "depends_on": depends_on, "how": normalized_how}
        )

    if not normalized:
        return plan_error(
            "Subtasks are required when delegating.",
            "Subtasks list must include at least one non-empty string.",
        )

    task_ids = {task["id"] for task in normalized}

    # Combines
    raw_combines = [combine for combine in (combines or []) if combine]
    normalized_combines: list[dict[str, Any]] = []
    combine_ids: set[str] = set()

    for index, combine in enumerate(raw_combines, start=1):
        if not isinstance(combine, dict):
            return plan_error(
                "Invalid combine entry.",
                f"Combine entry #{index} must be an object.",
            )
        combine_id = str(combine.get("id") or f"combine_{index}").strip()
        if not combine_id:
            return plan_error(
                "Invalid combine id.",
                f"Combine entry #{index} requires an id.",
            )
        if combine_id in task_ids or combine_id in combine_ids:
            return plan_error(
                "Duplicate combine id.",
                f"Combine id '{combine_id}' appears more than once.",
            )

        operator_raw = combine.get("op") or combine.get("operator") or combine.get("combine")
        operator = _op_value(operator_raw)
        if not operator:
            return plan_error(
                "Invalid combine operator.",
                f"Combine '{combine_id}' requires a valid operator.",
            )

        inputs = combine.get("inputs")
        left = combine.get("left")
        right = combine.get("right")

        if inputs is not None:
            if not isinstance(inputs, list):
                return plan_error(
                    "Invalid combine inputs.",
                    f"Combine '{combine_id}' inputs must be a list.",
                )
            input_refs = [str(item).strip() for item in inputs if str(item).strip()]
            if len(input_refs) < 2:
                return plan_error(
                    "Invalid combine inputs.",
                    f"Combine '{combine_id}' inputs must include 2+ ids.",
                )
        else:
            input_refs = []
            if left:
                input_refs.append(str(left).strip())
            if right:
                input_refs.append(str(right).strip())
            if len(input_refs) != 2:
                return plan_error(
                    "Invalid combine inputs.",
                    f"Combine '{combine_id}' requires left/right or inputs list.",
                )

        depends_raw = combine.get("depends_on") or combine.get("dependsOn")
        if depends_raw is None:
            depends_on = input_refs
        elif isinstance(depends_raw, str):
            depends_on = [depends_raw.strip()] if depends_raw.strip() else []
        elif isinstance(depends_raw, list):
            depends_on = [str(dep).strip() for dep in depends_raw if str(dep).strip()]
        else:
            depends_on = []
        # Ensure inputs are dependencies so combines only run after inputs are ready.
        depends_on = list(dict.fromkeys([*depends_on, *input_refs]))

        normalized_combines.append(
            {
                "id": combine_id,
                "operator": operator,
                "inputs": input_refs,
                "depends_on": depends_on,
                "display_name": combine.get("display_name") or combine.get("displayName"),
                "upstream": combine.get("upstream"),
                "downstream": combine.get("downstream"),
            }
        )
        combine_ids.add(combine_id)

    valid_ref_ids = task_ids | combine_ids
    for combine in normalized_combines:
        missing = [ref for ref in combine["inputs"] if ref and ref not in valid_ref_ids]
        if missing:
            return plan_error(
                "Unknown combine input ids.",
                f"{combine['id']} references {missing} which are not in subtasks/combines.",
            )
        missing_deps = [dep for dep in combine["depends_on"] if dep not in valid_ref_ids]
        if missing_deps:
            return plan_error(
                "Unknown combine dependency ids.",
                f"{combine['id']} depends on {missing_deps} which are not in subtasks/combines.",
            )

    # Now validate and build a unified DAG over (tasks ∪ combines).
    nodes_by_id: dict[str, dict[str, Any]] = {}
    for task in normalized:
        nodes_by_id[task["id"]] = {
            **task,
            "kind": "task",
        }
    for combine in normalized_combines:
        nodes_by_id[combine["id"]] = {
            **combine,
            "kind": "combine",
            # Make `format_dependency_context` happy (it looks for "task" text)
            "task": combine.get("display_name")
            or f"Combine {combine['id']} ({combine.get('operator')})",
        }

    all_ids = set(nodes_by_id.keys())

    for task in normalized:
        missing = [dep for dep in (task.get("depends_on") or []) if dep not in all_ids]
        if missing:
            return plan_error(
                "Unknown dependency ids.",
                f"{task['id']} depends on {missing} which are not in subtasks/combines.",
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
        post_plan=post_plan,
        tasks=normalized,
        combines=normalized_combines,
        nodes_by_id=nodes_by_id,
        dependents=dependents,
    )

