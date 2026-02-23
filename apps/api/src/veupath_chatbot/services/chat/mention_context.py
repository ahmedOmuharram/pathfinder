"""Build rich context blocks for @-mentioned strategies and experiments.

When a user @-mentions a strategy or experiment in chat, we load the full
entity and format a human-readable context block that gets appended to the
system prompt so the model has complete information from the start.
"""

from __future__ import annotations

import json
from typing import Literal

from veupath_chatbot.persistence.repo import StrategyRepository
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import ExperimentMetrics

logger = get_logger(__name__)

MentionType = Literal["strategy", "experiment"]


async def build_mention_context(
    mentions: list[dict[str, str]],
    strategy_repo: StrategyRepository,
) -> str:
    """Build concatenated context blocks for all mentions.

    :param mentions: List of ``{"type": ..., "id": ..., "displayName": ...}`` dicts.
    :param strategy_repo: Repository for loading strategies.
    :returns: Markdown context string (empty if no mentions resolved).
    """
    blocks: list[str] = []

    for m in mentions:
        m_type = m.get("type")
        m_id = m.get("id", "")

        if m_type == "strategy":
            block = await _build_strategy_context(m_id, strategy_repo)
            if block:
                blocks.append(block)
        elif m_type == "experiment":
            block = await _build_experiment_context(m_id)
            if block:
                blocks.append(block)
        else:
            logger.debug("Unknown mention type", mention_type=m_type, mention_id=m_id)

    return "\n\n".join(blocks)


async def _build_strategy_context(
    strategy_id: str,
    strategy_repo: StrategyRepository,
) -> str | None:
    """Load a strategy and format a rich context block."""
    from uuid import UUID

    try:
        sid = UUID(strategy_id)
    except ValueError:
        logger.warning("Invalid strategy mention ID", strategy_id=strategy_id)
        return None

    strategy = await strategy_repo.get_by_id(sid)
    if not strategy:
        logger.warning("Mentioned strategy not found", strategy_id=strategy_id)
        return None

    lines: list[str] = [
        f'## Referenced Strategy: "{strategy.name}"',
        f"- **ID**: {strategy.id}",
        f"- **Record type**: {strategy.record_type or 'unknown'}",
    ]

    steps = strategy.steps
    if isinstance(steps, list) and steps:
        lines.append(f"- **Steps** ({len(steps)}):")
        lines.append("")
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            display_name = (
                step.get("displayName") or step.get("searchName") or f"Step {i + 1}"
            )
            kind = step.get("kind") or "search"
            step_id = step.get("id", "?")

            lines.append(f"### Step {i + 1}: {display_name} ({kind}) [id={step_id}]")

            search_name = step.get("searchName")
            if search_name:
                lines.append(f"- Search: `{search_name}`")

            params = step.get("parameters")
            if isinstance(params, dict) and params:
                non_empty = {k: v for k, v in params.items() if v}
                if non_empty:
                    param_strs = [
                        f"`{k}`: {_truncate(str(v), 80)}" for k, v in non_empty.items()
                    ]
                    lines.append(f"- Parameters: {', '.join(param_strs)}")

            result_count = step.get("resultCount")
            if result_count is not None:
                lines.append(f"- Result count: {result_count}")

            primary = step.get("primaryInputStepId")
            secondary = step.get("secondaryInputStepId")
            operator = step.get("operator")
            if primary and secondary and operator:
                lines.append(
                    f"- Combines: step {primary} **{operator}** step {secondary}"
                )
            elif primary:
                lines.append(f"- Input: step {primary}")

            lines.append("")
    elif isinstance(strategy.plan, dict):
        lines.append("")
        lines.append("### Strategy plan (AST):")
        lines.append("```json")
        lines.append(json.dumps(strategy.plan, indent=2, default=str)[:4000])
        lines.append("```")

    return "\n".join(lines)


async def _build_experiment_context(experiment_id: str) -> str | None:
    """Load an experiment and format a rich context block."""
    store = get_experiment_store()
    experiment = await store.get(experiment_id)
    if not experiment:
        logger.warning("Mentioned experiment not found", experiment_id=experiment_id)
        return None

    cfg = experiment.config
    lines: list[str] = [
        f'## Referenced Experiment: "{cfg.name or experiment.id}"',
        f"- **Status**: {experiment.status}",
        f"- **Search**: `{cfg.search_name}` on `{cfg.record_type}`",
    ]

    if cfg.parameters:
        non_empty = {k: v for k, v in cfg.parameters.items() if v}
        if non_empty:
            param_strs = [
                f"`{k}`: {_truncate(str(v), 60)}" for k, v in non_empty.items()
            ]
            lines.append(f"- **Parameters**: {', '.join(param_strs)}")

    if cfg.positive_controls:
        ids = ", ".join(cfg.positive_controls[:20])
        suffix = (
            f" ... ({len(cfg.positive_controls)} total)"
            if len(cfg.positive_controls) > 20
            else ""
        )
        lines.append(
            f"- **Positive controls** ({len(cfg.positive_controls)}): {ids}{suffix}"
        )

    if cfg.negative_controls:
        ids = ", ".join(cfg.negative_controls[:20])
        suffix = (
            f" ... ({len(cfg.negative_controls)} total)"
            if len(cfg.negative_controls) > 20
            else ""
        )
        lines.append(
            f"- **Negative controls** ({len(cfg.negative_controls)}): {ids}{suffix}"
        )

    metrics = experiment.metrics
    if metrics:
        lines.append("")
        lines.append("### Metrics")
        lines.append(_format_metrics(metrics))

    cv = experiment.cross_validation
    if cv:
        lines.append("")
        lines.append(
            f"### Cross-validation ({cv.k}-fold): "
            f"overfitting={cv.overfitting_level} (score={cv.overfitting_score:.3f})"
        )
        lines.append(f"- Mean F1: {cv.mean_metrics.f1_score:.4f}")
        lines.append(f"- Mean sensitivity: {cv.mean_metrics.sensitivity:.4f}")
        lines.append(f"- Mean specificity: {cv.mean_metrics.specificity:.4f}")

    for er in experiment.enrichment_results[:3]:
        if er.terms:
            lines.append("")
            lines.append(
                f"### Enrichment: {er.analysis_type} ({er.total_genes_analyzed} genes)"
            )
            for term in er.terms[:8]:
                lines.append(
                    f"- {term.term_name} ({term.gene_count} genes, "
                    f"p={term.p_value:.2e}, FDR={term.fdr:.2e})"
                )
            if len(er.terms) > 8:
                lines.append(f"- ... {len(er.terms) - 8} more terms")

    if experiment.optimization_result:
        best = experiment.optimization_result.get("bestTrial")
        if isinstance(best, dict):
            lines.append("")
            lines.append("### Optimization result")
            lines.append(f"- Best score: {best.get('score', '?')}")
            params = best.get("parameters")
            if isinstance(params, dict):
                param_strs = [f"`{k}`: {v}" for k, v in params.items()]
                lines.append(f"- Best parameters: {', '.join(param_strs)}")

    return "\n".join(lines)


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
        f"| TP={m.confusion_matrix.true_positives} | FP={m.confusion_matrix.false_positives} | "
        f"FN={m.confusion_matrix.false_negatives} | TN={m.confusion_matrix.true_negatives} |"
    )


def _truncate(s: str, max_len: int) -> str:
    """Truncate a string with ellipsis."""
    return s if len(s) <= max_len else s[: max_len - 3] + "..."
