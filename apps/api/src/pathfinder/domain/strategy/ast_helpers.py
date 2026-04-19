"""Plan AST helpers — count nodes and derive step metadata from plan trees."""

from pathfinder.domain.strategy.ast import walk_step_tree
from pathfinder.domain.strategy.strategy_ast import StrategyAst


def count_strategy_nodes(payload: StrategyAst) -> int:
    """Count step nodes in a typed plan payload."""
    return len(walk_step_tree(payload.root))


def derive_strategy_steps_json(payload: StrategyAst) -> list[dict[str, object]]:
    """Derive a steps JSON array from a plan payload for the projection column."""
    return [
        {
            "id": step.id,
            "searchName": step.search_name,
            "displayName": step.display_name,
            "kind": step.infer_kind(),
            "operator": step.operator.value if step.operator is not None else None,
        }
        for step in walk_step_tree(payload.root)
    ]
