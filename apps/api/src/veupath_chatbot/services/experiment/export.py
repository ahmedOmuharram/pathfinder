"""Export experiment results as CSV/ZIP."""

from __future__ import annotations

import csv
import io
import zipfile

from veupath_chatbot.services.experiment.types import (
    Experiment,
    ExperimentMetrics,
    GeneInfo,
)


def _metrics_rows(m: ExperimentMetrics) -> list[list[str]]:
    """Build CSV rows for classification metrics."""
    return [
        ["Metric", "Value"],
        ["Sensitivity", f"{m.sensitivity:.4f}"],
        ["Specificity", f"{m.specificity:.4f}"],
        ["Precision", f"{m.precision:.4f}"],
        ["F1 Score", f"{m.f1_score:.4f}"],
        ["MCC", f"{m.mcc:.4f}"],
        ["Balanced Accuracy", f"{m.balanced_accuracy:.4f}"],
        ["NPV", f"{m.negative_predictive_value:.4f}"],
        ["FPR", f"{m.false_positive_rate:.4f}"],
        ["FNR", f"{m.false_negative_rate:.4f}"],
        ["Youden's J", f"{m.youdens_j:.4f}"],
        ["Total Results", str(m.total_results)],
        ["Total Positives", str(m.total_positives)],
        ["Total Negatives", str(m.total_negatives)],
        [],
        ["Confusion Matrix"],
        ["", "Predicted Positive", "Predicted Negative"],
        [
            "Actual Positive",
            str(m.confusion_matrix.true_positives),
            str(m.confusion_matrix.false_negatives),
        ],
        [
            "Actual Negative",
            str(m.confusion_matrix.false_positives),
            str(m.confusion_matrix.true_negatives),
        ],
    ]


def _gene_rows(genes: list[GeneInfo]) -> list[list[str]]:
    """Build CSV rows for a gene list."""
    rows: list[list[str]] = [["Gene ID", "Name", "Product", "Organism"]]
    for g in genes:
        rows.append([g.id, g.name or "", g.product or "", g.organism or ""])
    return rows


def _write_csv(buf: io.StringIO, rows: list[list[str]]) -> None:
    writer = csv.writer(buf)
    writer.writerows(rows)


def export_experiment_zip(exp: Experiment) -> bytes:
    """Build a ZIP archive containing all experiment results as CSVs.

    :param exp: Completed experiment.
    :returns: ZIP file bytes.
    """
    zip_buf = io.BytesIO()

    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if exp.metrics:
            buf = io.StringIO()
            _write_csv(buf, _metrics_rows(exp.metrics))
            zf.writestr("metrics.csv", buf.getvalue())

        gene_lists = [
            ("true_positives.csv", exp.true_positive_genes),
            ("false_negatives.csv", exp.false_negative_genes),
            ("false_positives.csv", exp.false_positive_genes),
            ("true_negatives.csv", exp.true_negative_genes),
        ]
        for filename, genes in gene_lists:
            if genes:
                buf = io.StringIO()
                _write_csv(buf, _gene_rows(genes))
                zf.writestr(f"genes/{filename}", buf.getvalue())

        if exp.cross_validation:
            cv = exp.cross_validation
            rows: list[list[str]] = [
                ["Fold", "Sensitivity", "Specificity", "Precision", "F1", "MCC"],
            ]
            for f in cv.folds:
                rows.append(
                    [
                        str(f.fold_index + 1),
                        f"{f.metrics.sensitivity:.4f}",
                        f"{f.metrics.specificity:.4f}",
                        f"{f.metrics.precision:.4f}",
                        f"{f.metrics.f1_score:.4f}",
                        f"{f.metrics.mcc:.4f}",
                    ]
                )
            rows.append([])
            rows.append(
                [
                    "Mean",
                    *[
                        f"{getattr(cv.mean_metrics, a):.4f}"
                        for a in (
                            "sensitivity",
                            "specificity",
                            "precision",
                            "f1_score",
                            "mcc",
                        )
                    ],
                ]
            )
            rows.append(["Overfitting Score", f"{cv.overfitting_score:.4f}"])
            rows.append(["Overfitting Level", cv.overfitting_level])
            buf = io.StringIO()
            _write_csv(buf, rows)
            zf.writestr("cross_validation.csv", buf.getvalue())

        for er in exp.enrichment_results:
            rows = [
                [
                    "Term ID",
                    "Term Name",
                    "Gene Count",
                    "Background Count",
                    "Fold Enrichment",
                    "Odds Ratio",
                    "p-value",
                    "FDR",
                    "Bonferroni",
                    "Genes",
                ],
            ]
            for t in er.terms:
                rows.append(
                    [
                        t.term_id,
                        t.term_name,
                        str(t.gene_count),
                        str(t.background_count),
                        f"{t.fold_enrichment:.4f}",
                        f"{t.odds_ratio:.4f}",
                        f"{t.p_value:.6e}",
                        f"{t.fdr:.6e}",
                        f"{t.bonferroni:.6e}",
                        ";".join(t.genes),
                    ]
                )
            buf = io.StringIO()
            _write_csv(buf, rows)
            zf.writestr(f"enrichment/{er.analysis_type}.csv", buf.getvalue())

    return zip_buf.getvalue()
