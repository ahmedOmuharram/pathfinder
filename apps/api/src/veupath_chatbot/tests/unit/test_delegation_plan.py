from veupath_chatbot.ai.orchestration.delegation import build_delegation_plan
from veupath_chatbot.platform.types import JSONObject, as_json_object


def test_delegation_plan_allows_missing_ids_generates_unique_ids() -> None:
    compiled = build_delegation_plan(
        goal="x",
        plan={
            "type": "combine",
            "operator": "UNION",
            "left": {"type": "task", "task": "A"},
            "right": {"type": "task", "task": "B"},
        },
    )
    assert not isinstance(compiled, dict)
    assert compiled.goal == "x"
    assert len(compiled.tasks) == 2
    assert len(compiled.combines) == 1
    ids = set(compiled.nodes_by_id.keys())
    # 2 tasks + 1 combine
    assert len(ids) == 3


def test_delegation_plan_dedupes_identical_repeated_subtrees_without_ids() -> None:
    # The same subtree is repeated twice; we should dedupe structurally.
    subtree: JSONObject = {
        "type": "combine",
        "operator": "UNION",
        "left": {"type": "task", "task": "A"},
        "right": {"type": "task", "task": "B"},
    }
    compiled = build_delegation_plan(
        goal="x",
        plan={
            "type": "combine",
            "operator": "INTERSECT",
            "left": subtree,
            "right": {"type": "task", "task": "Use subtree", "input": subtree},
        },
    )
    assert not isinstance(compiled, dict)
    # nodes: A, B, UNION(A,B), "Use subtree", INTERSECT(UNION, Use)
    assert len(compiled.nodes_by_id) == 5


def test_delegation_plan_preserves_task_context_and_affects_dedupe() -> None:
    # Context should be preserved on task nodes and should be part of structural dedupe.
    plan: JSONObject = {
        "type": "combine",
        "operator": "UNION",
        "left": {"type": "task", "task": "A", "context": {"organism": "Pf3D7"}},
        "right": {"type": "task", "task": "A", "context": {"organism": "PbANKA"}},
    }
    compiled = build_delegation_plan(goal="x", plan=plan)
    assert not isinstance(compiled, dict)
    assert len(compiled.tasks) == 2
    contexts: list[JSONObject] = []
    for t_value in compiled.tasks:
        if isinstance(t_value, dict):
            t = as_json_object(t_value)
            context_value = t.get("context")
            if isinstance(context_value, dict):
                contexts.append(as_json_object(context_value))
    context_dicts: list[dict[str, str]] = []
    for ctx in contexts:
        context_dicts.append(
            {k: str(v) if v is not None else "" for k, v in ctx.items()}
        )
    assert {"organism": "Pf3D7"} in context_dicts
    assert {"organism": "PbANKA"} in context_dicts
    # Same task text but different context => should not dedupe into one node.
    task_ids: set[str] = set()
    for t_value in compiled.tasks:
        if isinstance(t_value, dict):
            t = as_json_object(t_value)
            task_id_value = t.get("id")
            if isinstance(task_id_value, str):
                task_ids.add(task_id_value)
    assert len(task_ids) == 2


def test_delegation_plan_infers_combine_type_when_missing() -> None:
    plan: JSONObject = {
        # intentionally omit "type": "combine"
        "operator": "INTERSECT",
        "left": {"type": "task", "task": "left"},
        "right": {"type": "task", "task": "right"},
    }
    compiled = build_delegation_plan(goal="x", plan=plan)
    assert not isinstance(compiled, dict)
    assert len(compiled.combines) == 1
    assert len(compiled.tasks) == 2
