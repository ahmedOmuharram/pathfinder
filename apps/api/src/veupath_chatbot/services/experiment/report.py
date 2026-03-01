"""Self-contained HTML report generation for experiments.

Generates a single-file HTML document with embedded styles, tables,
and inline SVG charts. No external dependencies required.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime

from veupath_chatbot.services.experiment.types import (
    BootstrapResult,
    Experiment,
    RankMetrics,
    StepAnalysisResult,
)

_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 0 auto; padding: 24px; color: #1a1a2e; background: #fff; }
h1 { font-size: 1.5rem; margin-bottom: 4px; }
h2 { font-size: 1.1rem; margin-top: 2rem; border-bottom: 1px solid #e5e7eb; padding-bottom: 6px; }
h3 { font-size: 0.9rem; margin-top: 1rem; color: #6b7280; }
table { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 0.85rem; }
th, td { padding: 6px 12px; text-align: left; border-bottom: 1px solid #e5e7eb; }
th { background: #f9fafb; font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #6b7280; }
td { font-family: 'SF Mono', Consolas, monospace; }
.numeric { text-align: right; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: 600; }
.badge-green { background: #dcfce7; color: #166534; }
.badge-blue { background: #dbeafe; color: #1e40af; }
.badge-amber { background: #fef3c7; color: #92400e; }
.badge-red { background: #fee2e2; color: #991b1b; }
.summary-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 12px 0; }
.summary-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; text-align: center; }
.summary-card .label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; color: #6b7280; }
.summary-card .value { font-size: 1.5rem; font-weight: 700; font-family: 'SF Mono', Consolas, monospace; margin: 4px 0; }
.gene-list { max-height: 200px; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 4px; padding: 8px; font-size: 0.75rem; font-family: monospace; }
details summary { cursor: pointer; font-size: 0.85rem; font-weight: 600; color: #374151; }
.meta { font-size: 0.8rem; color: #6b7280; }
.ci { font-size: 0.7rem; color: #9ca3af; }
@media print { body { max-width: 100%; } }
"""


def generate_experiment_report(experiment: Experiment) -> str:
    """Generate a self-contained HTML report for an experiment.

    :param experiment: Full experiment object with results.
    :returns: Complete HTML string.
    """
    parts: list[str] = []
    parts.append(_header(experiment))
    parts.append(_config_section(experiment))

    if experiment.rank_metrics:
        parts.append(_rank_metrics_section(experiment.rank_metrics))

    if experiment.metrics:
        parts.append(_classification_section(experiment))

    if experiment.robustness:
        parts.append(_robustness_section(experiment.robustness))

    if experiment.step_analysis:
        parts.append(_step_analysis_section(experiment.step_analysis))

    if experiment.enrichment_results:
        parts.append(_enrichment_section(experiment))

    parts.append(_gene_lists_section(experiment))
    parts.append(_footer(experiment))

    body = "\n".join(parts)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Experiment Report — {_esc(experiment.config.name or experiment.id)}</title>
<style>{_CSS}</style>
</head>
<body>
{body}
</body>
</html>"""


def _esc(text: str) -> str:
    return html.escape(str(text))


def _pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def _num(v: float) -> str:
    return f"{v:.4f}"


def _header(exp: Experiment) -> str:
    name = exp.config.name or f"Experiment {exp.id}"
    ts = exp.created_at or datetime.now(UTC).isoformat()
    mode = exp.config.mode
    return f"""
<h1>{_esc(name)}</h1>
<p class="meta">
  Mode: <strong>{_esc(mode)}</strong> &middot;
  Site: <strong>{_esc(exp.config.site_id)}</strong> &middot;
  Record type: <strong>{_esc(exp.config.record_type)}</strong> &middot;
  Generated: {_esc(ts)}
</p>"""


def _config_section(exp: Experiment) -> str:
    cfg = exp.config
    rows = [
        ("Search", cfg.search_name),
        ("Positive controls", str(len(cfg.positive_controls))),
        ("Negative controls", str(len(cfg.negative_controls))),
    ]
    if cfg.control_set_id:
        rows.append(("Control set ID", cfg.control_set_id))
    if exp.total_time_seconds:
        rows.append(("Total time", f"{exp.total_time_seconds:.1f}s"))

    tbody = "\n".join(f"<tr><td>{_esc(k)}</td><td>{_esc(v)}</td></tr>" for k, v in rows)
    return f"<h2>Configuration</h2>\n<table>{tbody}</table>"


def _rank_metrics_section(rm: RankMetrics) -> str:
    header = "<tr><th>K</th><th class='numeric'>Precision@K</th><th class='numeric'>Recall@K</th><th class='numeric'>Enrichment@K</th></tr>"
    rows = []
    for k in sorted(rm.precision_at_k.keys()):
        p = rm.precision_at_k.get(k, 0)
        r = rm.recall_at_k.get(k, 0)
        e = rm.enrichment_at_k.get(k, 0)
        rows.append(
            f"<tr><td>{k}</td><td class='numeric'>{_pct(p)}</td><td class='numeric'>{_pct(r)}</td><td class='numeric'>{_num(e)}x</td></tr>"
        )

    p50 = rm.precision_at_k.get(50, 0)
    r50 = rm.recall_at_k.get(50, 0)
    e50 = rm.enrichment_at_k.get(50, 0)

    summary = f"""
<div class="summary-grid">
  <div class="summary-card"><div class="label">Precision@50</div><div class="value">{_pct(p50)}</div></div>
  <div class="summary-card"><div class="label">Recall@50</div><div class="value">{_pct(r50)}</div></div>
  <div class="summary-card"><div class="label">Enrichment@50</div><div class="value">{_num(e50)}x</div></div>
</div>"""

    return f"<h2>Rank-Based Metrics</h2>\n{summary}\n<table>{header}\n{''.join(rows)}</table>"


def _classification_section(exp: Experiment) -> str:
    m = exp.metrics
    if not m:
        return ""
    cm = m.confusion_matrix
    rows = [
        ("Sensitivity", _pct(m.sensitivity)),
        ("Specificity", _pct(m.specificity)),
        ("Precision", _pct(m.precision)),
        ("F1 Score", _num(m.f1_score)),
        ("MCC", _num(m.mcc)),
        ("Balanced Accuracy", _pct(m.balanced_accuracy)),
    ]
    tbody = "\n".join(
        f"<tr><td>{_esc(k)}</td><td class='numeric'>{_esc(v)}</td></tr>"
        for k, v in rows
    )
    cm_html = f"""
<h3>Confusion Matrix</h3>
<table>
<tr><th></th><th class='numeric'>Predicted +</th><th class='numeric'>Predicted -</th></tr>
<tr><td>Actual +</td><td class='numeric'>{cm.true_positives}</td><td class='numeric'>{cm.false_negatives}</td></tr>
<tr><td>Actual -</td><td class='numeric'>{cm.false_positives}</td><td class='numeric'>{cm.true_negatives}</td></tr>
</table>"""
    return f"<h2>Classification Metrics</h2>\n<table>{tbody}</table>\n{cm_html}"


def _robustness_section(br: BootstrapResult) -> str:
    rows = []
    for key, ci in {**br.metric_cis, **br.rank_metric_cis}.items():
        rows.append(
            f"<tr><td>{_esc(key)}</td>"
            f"<td class='numeric'>{_num(ci.mean)}</td>"
            f"<td class='numeric ci'>[{_num(ci.lower)}, {_num(ci.upper)}]</td>"
            f"<td class='numeric'>{_num(ci.std)}</td></tr>"
        )
    header = "<tr><th>Metric</th><th class='numeric'>Mean</th><th class='numeric'>95% CI</th><th class='numeric'>Std</th></tr>"
    stability_text = f"<p>Top-50 Stability (Jaccard): <strong>{_num(br.top_k_stability)}</strong> ({br.n_iterations} bootstrap iterations)</p>"
    return f"<h2>Robustness &amp; Uncertainty</h2>\n{stability_text}\n<table>{header}\n{''.join(rows)}</table>"


def _step_analysis_section(sa: StepAnalysisResult) -> str:
    parts: list[str] = ["<h2>Step Analysis</h2>"]

    if sa.step_evaluations:
        header = "<tr><th>Step</th><th class='numeric'>Results</th><th class='numeric'>Recall</th><th class='numeric'>FPR</th><th class='numeric'>TP Δ</th><th class='numeric'>FP Δ</th></tr>"
        rows = []
        for ev in sa.step_evaluations:
            rows.append(
                f"<tr><td>{_esc(ev.display_name)}</td>"
                f"<td class='numeric'>{ev.result_count}</td>"
                f"<td class='numeric'>{_pct(ev.recall)}</td>"
                f"<td class='numeric'>{_pct(ev.false_positive_rate)}</td>"
                f"<td class='numeric'>{ev.tp_movement:+d}</td>"
                f"<td class='numeric'>{ev.fp_movement:+d}</td></tr>"
            )
        parts.append(
            f"<h3>Per-Step Evaluation</h3>\n<table>{header}\n{''.join(rows)}</table>"
        )

    if sa.step_contributions:
        header = "<tr><th>Step</th><th class='numeric'>Recall Δ</th><th class='numeric'>FPR Δ</th><th>Verdict</th><th>Narrative</th></tr>"
        rows = []
        for sc in sa.step_contributions:
            badge_cls = {
                "essential": "badge-green",
                "helpful": "badge-blue",
                "neutral": "badge-amber",
                "harmful": "badge-red",
            }.get(sc.verdict, "")
            rows.append(
                f"<tr><td>{_esc(sc.search_name)}</td>"
                f"<td class='numeric'>{sc.recall_delta:+.1%}</td>"
                f"<td class='numeric'>{sc.fpr_delta:+.1%}</td>"
                f"<td><span class='badge {badge_cls}'>{_esc(sc.verdict)}</span></td>"
                f"<td>{_esc(sc.narrative)}</td></tr>"
            )
        parts.append(
            f"<h3>Step Contribution</h3>\n<table>{header}\n{''.join(rows)}</table>"
        )

    return "\n".join(parts)


def _enrichment_section(exp: Experiment) -> str:
    parts: list[str] = ["<h2>Enrichment Analysis</h2>"]
    for er in exp.enrichment_results:
        header = "<tr><th>Term</th><th class='numeric'>Genes</th><th class='numeric'>Fold</th><th class='numeric'>FDR</th></tr>"
        rows = []
        for t in er.terms[:20]:
            rows.append(
                f"<tr><td>{_esc(t.term_name)}</td>"
                f"<td class='numeric'>{t.gene_count}</td>"
                f"<td class='numeric'>{t.fold_enrichment:.2f}</td>"
                f"<td class='numeric'>{t.fdr:.2e}</td></tr>"
            )
        parts.append(
            f"<h3>{_esc(er.analysis_type)} ({er.total_genes_analyzed} genes)</h3>\n"
            f"<table>{header}\n{''.join(rows)}</table>"
        )
    return "\n".join(parts)


def _gene_lists_section(exp: Experiment) -> str:
    parts: list[str] = ["<h2>Gene Lists</h2>"]

    for label, genes in [
        ("True Positives", exp.true_positive_genes),
        ("False Negatives", exp.false_negative_genes),
        ("False Positives", exp.false_positive_genes),
    ]:
        if not genes:
            continue
        gene_ids = ", ".join(g.id for g in genes[:200])
        parts.append(
            f"<details><summary>{label} ({len(genes)})</summary>"
            f"<div class='gene-list'>{_esc(gene_ids)}</div></details>"
        )

    return "\n".join(parts)


def _footer(exp: Experiment) -> str:
    return f"""
<hr style="margin-top: 2rem; border: none; border-top: 1px solid #e5e7eb;">
<p class="meta" style="text-align: center; margin-top: 12px;">
  Experiment ID: {_esc(exp.id)} &middot;
  Generated by Pathfinder Experiment Lab
</p>"""
