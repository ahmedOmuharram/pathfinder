"""Plan AST helpers — build and count nodes in plan trees.

Pure functions (no I/O) that convert flat step lists into recursive
plan AST structures and walk plan trees to count nodes.

Extracted from ``platform/events.py`` to keep domain logic in the
domain layer.
"""

from veupath_chatbot.platform.types import JSONObject


def _infer_search_name(step: JSONObject) -> str:
    """Infer a search name from a flat step dict.

    Falls back to ``__combine__`` for combine steps (by kind or operator
    presence) and ``__unknown__`` otherwise.
    """
    raw_name = step.get("searchName") or ""
    if raw_name:
        return str(raw_name)
    kind = str(step.get("kind") or "").strip().lower()
    if kind == "combine" or step.get("operator"):
        return "__combine__"
    return "__unknown__"


def _build_step_node(
    step_id: str,
    step_map: dict[str, JSONObject],
) -> JSONObject | None:
    """Build a single plan AST node, recursing into inputs."""
    step = step_map.get(step_id)
    if not step:
        return None

    node: JSONObject = {
        "id": step_id,
        "searchName": _infer_search_name(step),
        "parameters": step.get("parameters", {}),
    }

    display = step.get("displayName")
    if display:
        node["displayName"] = display
    op = step.get("operator")
    if op:
        node["operator"] = op
    coloc = step.get("colocationParams")
    if coloc:
        node["colocationParams"] = coloc

    primary_id = step.get("primaryInputStepId")
    if isinstance(primary_id, str):
        primary = _build_step_node(primary_id, step_map)
        if primary:
            node["primaryInput"] = primary

    secondary_id = step.get("secondaryInputStepId")
    if isinstance(secondary_id, str):
        secondary = _build_step_node(secondary_id, step_map)
        if secondary:
            node["secondaryInput"] = secondary

    return node


def steps_to_plan(
    steps: list[JSONObject],
    root_step_id: str,
    snapshot: JSONObject,
) -> JSONObject | None:
    """Build a recursive plan AST from a flat steps list.

    Returns None if the root step cannot be found.
    """
    step_map: dict[str, JSONObject] = {}
    for s in steps:
        sid = s.get("id")
        if isinstance(sid, str):
            step_map[sid] = s

    root = _build_step_node(root_step_id, step_map)
    if not root:
        return None
    return {
        "recordType": snapshot.get("recordType", "transcript"),
        "root": root,
        "metadata": {"name": snapshot.get("name", "")},
    }


def count_plan_nodes(plan: JSONObject) -> int:
    """Count step nodes in a plan dict by walking the tree.

    The plan dict has ``{"root": {..., "primaryInput": ..., "secondaryInput": ...}}``.
    Each node with a ``searchName`` key counts as a step.
    """
    root = plan.get("root")
    if not isinstance(root, dict):
        return 0

    count = 0

    def visit(node: JSONObject) -> None:
        nonlocal count
        if node.get("searchName"):
            count += 1
        primary = node.get("primaryInput")
        if isinstance(primary, dict):
            visit(primary)
        secondary = node.get("secondaryInput")
        if isinstance(secondary, dict):
            visit(secondary)

    visit(root)
    return count
