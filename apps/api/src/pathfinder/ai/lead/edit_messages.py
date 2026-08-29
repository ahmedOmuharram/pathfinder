"""What an edit dispatch says: its work order, and why it refuses.

Prose only. The values a criterion already holds are printed here because a
pass that cannot see them re-derives them from a sentence.
"""

from __future__ import annotations

from pathfinder.domain.parameters.values import to_wire
from pathfinder.domain.strategy.operational_spec import OperationalSpec

__all__ = [
    "changed_revision_message",
    "edit_bound_nothing_message",
    "edit_work_order",
    "no_strategy_to_edit_message",
    "unsupported_edit_message",
]


def edit_work_order(reason: str, prompt: str, before: OperationalSpec) -> str:
    """The FRAME work order for an edit, carrying every bound value."""
    lines = [
        f"EDIT work order: {reason}",
        f"The user's message: {prompt}",
        "",
        "This turn EDITS the strategy below; it is not a fresh frame. State a "
        'disposition in `changes` for EVERY criterion listed here: "kept", '
        '"changed" (name the parameters the request moves in `changed_params`) '
        'or "dropped" (with a `reason`).',
        "",
        "A criterion the request does not name is kept: do not call "
        "set_criterion for it, and its values below stay byte for byte. For a "
        "criterion the request DOES change, call set_criterion with the values "
        "below as the `params` object plus the requested override, so only the "
        "named parameter moves and every other value is copied rather than "
        "re-derived from the text.",
        "",
        f"The strategy holds {len(before.criteria)} criteria now:",
    ]
    for criterion in before.criteria:
        lines.append(
            f"- [{criterion.id}] {criterion.text[:80]} -> "
            f"{criterion.search_name or '(UNBOUND)'} ({criterion.role})"
        )
        lines.extend(
            f"    {name}={to_wire(value)}"
            for name, value in criterion.resolved_params.items()
        )
    lines.extend(
        [
            "",
            "Call set_structure only when the request changes the shape of the "
            "strategy. Return a FrameResult with `changes` filled in.",
        ]
    )
    return "\n".join(lines)


def no_strategy_to_edit_message() -> str:
    return (
        "edit_strategy needs a strategy to edit, and this thread has none. Call "
        "frame_problem to operationalize the goal, then build_strategy."
    )


def edit_bound_nothing_message() -> str:
    return (
        "The edit pass left no spec behind, so there is nothing to compare "
        "against the strategy. Dispatch edit_strategy again and tell it to "
        "record its work with set_criterion and drop_criterion."
    )


def unsupported_edit_message(detail: str) -> str:
    return (
        f"This edit does not map onto the strategy's steps: {detail}. An edit "
        f"changes, adds or drops criteria in place; it cannot re-nest the steps "
        f"that stay. Restate it as a change to named criteria, or tell the user "
        f"what the request would cost and ask before anything is replaced."
    )


def changed_revision_message(base_revision: str, current: str) -> str:
    return (
        f"The strategy changed while this edit was being planned (it was "
        f"{base_revision!r} and is now {current!r}). Nothing was applied. Call "
        f"get_live_strategy_state to read it as it is now, then decide whether "
        f"the edit still applies."
    )
