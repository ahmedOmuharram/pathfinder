"""Lead tool: run 2+ search variants as SCORED experiments against a saved
control set, rank by an objective metric (MCC default), and surface a winner
card. The controls-based counterpart to compare_search_variants."""

from __future__ import annotations

from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import ToolReturn
from pydantic_ai.ui.vercel_ai.response_types import DataChunk

from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.ai.tools.standalone._id_arguments import parse_id_argument
from pathfinder.ai.tools.standalone._variant_targets import reject_combine_variants
from pathfinder.services.control_sets import ControlSetService
from pathfinder.services.experiment.scored_comparison import (
    ScoredComparison,
    run_scored_comparison,
)
from pathfinder.services.experiment.variant_comparison import VariantSpec

_MIN_VARIANTS = 2


def _summary(comparison: ScoredComparison) -> str:
    rows = "; ".join(
        f"{v.label}: MCC={v.mcc}, F1={v.f1}, prec={v.precision}"
        for v in comparison.variants
        if v.error is None
    )
    failed = "; ".join(
        f"{v.label} failed: {v.error}"
        for v in comparison.variants
        if v.error is not None
    )
    fail_note = f" Some variants failed — {failed}." if failed else ""
    winner = comparison.winner_label or "none (no variant scored)"
    return (
        f"Scored {len(comparison.variants)} variants by {comparison.objective}. "
        f"{rows}. Winner: {winner}.{fail_note} Report the winner and the "
        "metric trade-offs, then proceed with the chosen variant."
    )


async def compare_variants_scored(
    ctx: RunContext[LeadDeps],
    variants: list[VariantSpec],
    control_set_id: str,
    objective: str = "mcc",
) -> ToolReturn[ScoredComparison]:
    """Run each variant as a full scored experiment against a saved control
    set and rank them by ``objective`` (mcc | balanced_accuracy | f1 |
    precision | sensitivity). Use after the user has chosen/built a control
    set (see build_control_set / list_control_sets). Returns per-variant
    metrics + the winning variant as a card.
    """
    runtime = ctx.deps.runtime
    if len(variants) < _MIN_VARIANTS:
        msg = "compare_variants_scored needs at least 2 variants."
        raise ModelRetry(msg)
    reject_combine_variants(variants)

    parsed = parse_id_argument(
        control_set_id, argument="control_set_id", names="control set"
    )
    async with runtime.db_session_factory() as session:
        control_set = await ControlSetService(session).get(parsed, runtime.user_id)

    result = await run_scored_comparison(
        runtime.site_id,
        str(runtime.user_id),
        variants,
        positive_controls=control_set.positive_ids,
        negative_controls=control_set.negative_ids,
        objective=objective,
    )
    chunk = DataChunk(
        type="data-scored-comparison",
        data=result.model_dump(by_alias=True, mode="json"),
    )
    return ToolReturn(return_value=result, content=_summary(result), metadata=[chunk])
