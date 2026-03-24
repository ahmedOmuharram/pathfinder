"""Build rich context blocks for @-mentioned strategies and experiments.

When a user @-mentions a strategy or experiment in chat, we load the full
entity and format a human-readable context block that gets appended to the
system prompt so the model has complete information from the start.
"""

import json
from uuid import UUID

from veupath_chatbot.domain.strategy.ast import PlanStepNode, walk_step_tree
from veupath_chatbot.persistence.repositories.stream import StreamRepository
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.chat.types import ChatMention
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import (
    Experiment,
    ExperimentConfig,
    ExperimentMetrics,
)

logger = get_logger(__name__)

# Cap control-ID and enrichment-term lists injected into the system prompt
# to avoid bloating the LLM context window with long gene-ID enumerations.
_MAX_DISPLAYED_POSITIVE_CONTROLS = 20
_MAX_DISPLAYED_NEGATIVE_CONTROLS = 20
# Enrichment results can have hundreds of terms; show only the top few
# so the model focuses on the most significant findings.
_MAX_DISPLAYED_ENRICHMENT_TERMS = 8
# Strings shorter than this are too small for a meaningful "..." suffix.
_MIN_LENGTH_FOR_ELLIPSIS = 4


async def build_mention_context(
    mentions: list[ChatMention],
    stream_repo: StreamRepository,
) -> str:
    """Build concatenated context blocks for all mentions.

    :param mentions: List of ChatMention objects from the chat request.
    :param stream_repo: Repository for loading stream projections.
    :returns: Markdown context string (empty if no mentions resolved).
    """
    blocks: list[str] = []

    for m in mentions:
        if m.type == "strategy":
            block = await _build_strategy_context(m.id, stream_repo)
            if block:
                blocks.append(block)
        elif m.type == "experiment":
            block = await _build_experiment_context(m.id)
            if block:
                blocks.append(block)

    return "\n\n".join(blocks)


async def _build_strategy_context(
    strategy_id: str,
    stream_repo: StreamRepository,
) -> str | None:
    """Load a stream projection and format a rich context block."""
    try:
        sid = UUID(strategy_id)
    except ValueError:
        logger.warning("Invalid strategy mention ID", strategy_id=strategy_id)
        return None

    projection = await stream_repo.get_projection(sid)
    if not projection:
        logger.warning("Mentioned strategy not found", strategy_id=strategy_id)
        return None

    lines: list[str] = [
        f'## Referenced Strategy: "{projection.name}"',
        f"- **ID**: {projection.stream_id}",
        f"- **Record type**: {projection.record_type or 'unknown'}",
    ]

    plan: JSONObject = projection.plan if isinstance(projection.plan, dict) else {}
    root = _parse_plan_root(plan)
    step_counts = _extract_step_counts(plan)

    if root:
        all_steps = walk_step_tree(root)
        lines.append(f"- **Steps** ({len(all_steps)}):")
        lines.append("")
        for i, step in enumerate(all_steps):
            _format_step_context(lines, i, step, step_counts)
    elif plan:
        lines.append("")
        lines.append("### Strategy plan (AST):")
        lines.append("```json")
        lines.append(json.dumps(plan, indent=2, default=str)[:4000])
        lines.append("```")

    return "\n".join(lines)


def _parse_plan_root(plan: JSONObject) -> PlanStepNode | None:
    """Parse the root node from a plan dict, returning None on failure."""
    if not plan or "root" not in plan:
        return None
    root_raw = plan.get("root")
    if not isinstance(root_raw, dict):
        return None
    try:
        return PlanStepNode.model_validate(root_raw)
    except ValueError, KeyError, TypeError:
        return None


def _extract_step_counts(plan: JSONObject) -> dict[str, int]:
    """Extract step_counts from a plan dict. Returns empty dict if missing."""
    raw = plan.get("stepCounts")
    if isinstance(raw, dict):
        return {str(k): v for k, v in raw.items() if isinstance(v, int)}
    return {}


def _format_step_context(
    lines: list[str],
    index: int,
    step: PlanStepNode,
    step_counts: dict[str, int],
) -> None:
    """Append formatted lines for a single step to the output."""
    display_name = step.display_name or step.search_name or f"Step {index + 1}"
    kind = step.infer_kind()
    step_id = step.id

    lines.append(f"### Step {index + 1}: {display_name} ({kind}) [id={step_id}]")

    if step.search_name:
        lines.append(f"- Search: `{step.search_name}`")

    if step.parameters:
        non_empty = {k: v for k, v in step.parameters.items() if v}
        if non_empty:
            param_strs = [
                f"`{k}`: {_truncate(str(v), 80)}" for k, v in non_empty.items()
            ]
            lines.append(f"- Parameters: {', '.join(param_strs)}")

    estimated_size = step_counts.get(step.id)
    if estimated_size is not None:
        lines.append(f"- Result count: {estimated_size}")

    primary_id = step.primary_input.id if step.primary_input else None
    secondary_id = step.secondary_input.id if step.secondary_input else None
    if primary_id and secondary_id and step.operator:
        lines.append(
            f"- Combines: step {primary_id} "
            f"**{step.operator.value}** step {secondary_id}"
        )
    elif primary_id:
        lines.append(f"- Input: step {primary_id}")

    lines.append("")


async def _build_experiment_context(experiment_id: str) -> str | None:
    """Load an experiment and format a rich context block."""
    store = get_experiment_store()
    experiment = await store.aget(experiment_id)
    if not experiment:
        logger.warning("Mentioned experiment not found", experiment_id=experiment_id)
        return None

    cfg = experiment.config
    lines: list[str] = [
        f'## Referenced Experiment: "{cfg.name or experiment.id}"',
        f"- **Status**: {experiment.status}",
        f"- **Search**: `{cfg.search_name}` on `{cfg.record_type}`",
    ]

    _format_experiment_config(lines, cfg)
    _format_experiment_results(lines, experiment)

    return "\n".join(lines)


def _format_experiment_config(
    lines: list[str],
    cfg: ExperimentConfig,
) -> None:
    """Append config details (parameters, controls) to lines."""
    if cfg.parameters:
        non_empty = {k: v for k, v in cfg.parameters.items() if v}
        if non_empty:
            param_strs = [
                f"`{k}`: {_truncate(str(v), 60)}" for k, v in non_empty.items()
            ]
            lines.append(f"- **Parameters**: {', '.join(param_strs)}")

    _format_control_list(
        lines,
        "Positive controls",
        cfg.positive_controls,
        _MAX_DISPLAYED_POSITIVE_CONTROLS,
    )
    _format_control_list(
        lines,
        "Negative controls",
        cfg.negative_controls,
        _MAX_DISPLAYED_NEGATIVE_CONTROLS,
    )


def _format_control_list(
    lines: list[str],
    label: str,
    controls: list[str] | None,
    max_displayed: int,
) -> None:
    """Append a control-ID list line if controls are present."""
    if not controls:
        return
    ids = ", ".join(controls[:max_displayed])
    suffix = f" ... ({len(controls)} total)" if len(controls) > max_displayed else ""
    lines.append(f"- **{label}** ({len(controls)}): {ids}{suffix}")


def _format_experiment_results(
    lines: list[str],
    experiment: Experiment,
) -> None:
    """Append metrics, cross-validation, enrichment, and optimization."""
    if experiment.metrics:
        lines.append("")
        lines.append("### Metrics")
        lines.append(_format_metrics(experiment.metrics))

    _format_cross_validation(lines, experiment)
    _format_enrichment_results(lines, experiment)
    _format_optimization_result(lines, experiment)


def _format_cross_validation(
    lines: list[str],
    experiment: Experiment,
) -> None:
    """Append cross-validation summary."""
    cv = experiment.cross_validation
    if not cv:
        return
    lines.append("")
    lines.append(
        f"### Cross-validation ({cv.k}-fold): "
        f"overfitting={cv.overfitting_level} (score={cv.overfitting_score:.3f})"
    )
    lines.append(f"- Mean F1: {cv.mean_metrics.f1_score:.4f}")
    lines.append(f"- Mean sensitivity: {cv.mean_metrics.sensitivity:.4f}")
    lines.append(f"- Mean specificity: {cv.mean_metrics.specificity:.4f}")


def _format_enrichment_results(
    lines: list[str],
    experiment: Experiment,
) -> None:
    """Append enrichment result summaries."""
    for er in experiment.enrichment_results[:3]:
        if not er.terms:
            continue
        lines.append("")
        lines.append(
            f"### Enrichment: {er.analysis_type} ({er.total_genes_analyzed} genes)"
        )
        lines.extend(
            f"- {term.term_name} ({term.gene_count} genes, "
            f"p={term.p_value:.2e}, FDR={term.fdr:.2e})"
            for term in er.terms[:_MAX_DISPLAYED_ENRICHMENT_TERMS]
        )
        if len(er.terms) > _MAX_DISPLAYED_ENRICHMENT_TERMS:
            lines.append(
                f"- ... {len(er.terms) - _MAX_DISPLAYED_ENRICHMENT_TERMS} more terms"
            )


def _format_optimization_result(
    lines: list[str],
    experiment: Experiment,
) -> None:
    """Append optimization result summary."""
    if not experiment.optimization_result:
        return
    best = experiment.optimization_result.get("bestTrial")
    if not isinstance(best, dict):
        return
    lines.append("")
    lines.append("### Optimization result")
    lines.append(f"- Best score: {best.get('score', '?')}")
    params = best.get("parameters")
    if isinstance(params, dict):
        param_strs = [f"`{k}`: {v}" for k, v in params.items()]
        lines.append(f"- Best parameters: {', '.join(param_strs)}")


def _format_metrics(m: ExperimentMetrics) -> str:
    """Format metrics as a compact table."""
    return (
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| Sensitivity | {m.sensitivity:.4f} |\n"
        f"| Specificity | {m.specificity:.4f} |\n"
        f"| Precision | {m.precision:.4f} |\n"
        f"| F1 Score | {m.f1_score:.4f} |\n"
        f"| MCC | {m.mcc:.4f} |\n"
        f"| Balanced Accuracy | {m.balanced_accuracy:.4f} |\n"
        f"| Total Results | {m.total_results} |\n"
        f"| Confusion Matrix | TP={m.confusion_matrix.true_positives} FP={m.confusion_matrix.false_positives} "
        f"FN={m.confusion_matrix.false_negatives} TN={m.confusion_matrix.true_negatives} |"
    )


def _truncate(s: str, max_len: int) -> str:
    """Truncate a string with ellipsis."""
    if len(s) <= max_len:
        return s
    # Too small for "..." suffix — just hard-truncate.
    if max_len < _MIN_LENGTH_FOR_ELLIPSIS:
        return s[:max_len]
    return s[: max_len - 3] + "..."
