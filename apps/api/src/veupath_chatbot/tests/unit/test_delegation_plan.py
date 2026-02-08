from veupath_chatbot.ai.delegation_plan import build_delegation_plan


def test_delegation_plan_allows_missing_ids_generates_unique_ids():
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


def test_delegation_plan_dedupes_identical_repeated_subtrees_without_ids():
    # The same subtree is repeated twice; we should dedupe structurally.
    subtree = {
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


def test_delegation_plan_preserves_task_context_and_affects_dedupe():
    # Context should be preserved on task nodes and should be part of structural dedupe.
    plan = {
        "type": "combine",
        "operator": "UNION",
        "left": {"type": "task", "task": "A", "context": {"organism": "Pf3D7"}},
        "right": {"type": "task", "task": "A", "context": {"organism": "PbANKA"}},
    }
    compiled = build_delegation_plan(goal="x", plan=plan)
    assert not isinstance(compiled, dict)
    assert len(compiled.tasks) == 2
    contexts = [t.get("context") for t in compiled.tasks]
    assert {"organism": "Pf3D7"} in contexts
    assert {"organism": "PbANKA"} in contexts
    # Same task text but different context => should not dedupe into one node.
    assert len({t["id"] for t in compiled.tasks}) == 2


def test_delegation_plan_infers_combine_type_when_missing():
    plan = {
        # intentionally omit "type": "combine"
        "operator": "INTERSECT",
        "left": {"type": "task", "task": "left"},
        "right": {"type": "task", "task": "right"},
    }
    compiled = build_delegation_plan(goal="x", plan=plan)
    assert not isinstance(compiled, dict)
    assert len(compiled.combines) == 1
    assert len(compiled.tasks) == 2

