"""What the Lead is told when a dispatch cannot proceed.

Pure renderings of an ``OperationalSpec`` that a run ran out of budget on, or
that is not ready to build.
"""

from __future__ import annotations

from pathfinder.ai.lead.deltas import FrameResult
from pathfinder.domain.strategy.operational_spec import OperationalSpec


def frame_result_from_draft(spec: OperationalSpec | None) -> FrameResult:
    """Report a run that ran out of budget by what it managed to bind.

    Every criterion is written into the shared draft as it is bound, so the
    work is there to report. Saying "no result" discards a usable turn.
    """
    bound = [c for c in (spec.criteria if spec else []) if c.bound]
    if not bound:
        return FrameResult(
            disposition="needs_user",
            summary=(
                "FRAME ran out of its tool budget with no criteria bound. "
                "Narrow the goal or state fewer criteria, then try again."
            ),
        )
    names = ", ".join(c.id for c in bound)
    return FrameResult(
        disposition="needs_user",
        summary=(
            f"FRAME ran out of its tool budget after binding {len(bound)} "
            f"criteria ({names}). They are kept. Ask it to continue with the "
            f"rest rather than starting again."
        ),
    )


def build_not_ready_message(spec: OperationalSpec | None) -> str:
    """Why the spec cannot be built, phrased for what the model can do next.

    Open parameter slots are not a retry. Re-running FRAME regenerates the
    same slots, so telling the model to "call frame_problem first" sends it
    round a loop it cannot exit -- only the user can answer.
    """
    if spec is None or not spec.criteria or spec.structure is None:
        return (
            "No OperationalSpec to build yet (no criteria or no structure). "
            "Call frame_problem first."
        )
    if spec.open_slots:
        slots = "; ".join(
            f"{slot.param_name}"
            + (f" -- {slot.question}" if slot.question else "")
            + (f" (options: {', '.join(slot.options)})" if slot.options else "")
            for slot in spec.open_slots
        )
        return (
            f"The strategy cannot be built until the user answers "
            f"{len(spec.open_slots)} open parameter(s): {slots}. "
            "Do NOT re-frame -- the same slots come back. Ask the user for "
            "these values in your reply, then build once they answer."
        )
    unbound = [c.id for c in spec.criteria if not c.bound]
    if unbound:
        return (
            f"These criteria are not bound to a WDK search: {', '.join(unbound)}. "
            "Call frame_problem to bind them."
        )
    open_params = [
        f"{c.id}.{slot.param_name}" for c in spec.criteria for slot in c.open_params
    ]
    return (
        f"These criteria still need user-supplied parameters: "
        f"{', '.join(open_params)}. Ask the user for them, then build."
    )
