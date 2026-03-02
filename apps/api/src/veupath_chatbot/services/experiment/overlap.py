"""Gene set overlap analysis across experiments."""

from __future__ import annotations

from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.types import Experiment


def compute_gene_set_overlap(
    experiments: list[Experiment],
    experiment_ids: list[str],
) -> JSONObject:
    """Compute pairwise gene set overlap between experiments.

    For each experiment the result gene set is the union of TP and FP genes.
    Returns Jaccard similarity, shared/unique genes, and membership counts.
    """
    # Build gene sets (TP + FP) per experiment
    gene_sets: dict[str, set[str]] = {}
    labels: dict[str, str] = {}
    for exp in experiments:
        genes = {g.id for g in exp.true_positive_genes} | {
            g.id for g in exp.false_positive_genes
        }
        gene_sets[exp.id] = genes
        labels[exp.id] = exp.config.name or exp.id

    # Pairwise comparisons
    pairwise: list[JSONObject] = []
    for i in range(len(experiment_ids)):
        for j in range(i + 1, len(experiment_ids)):
            a_id, b_id = experiment_ids[i], experiment_ids[j]
            set_a, set_b = gene_sets[a_id], gene_sets[b_id]
            shared = set_a & set_b
            combined = set_a | set_b
            jaccard = len(shared) / len(combined) if combined else 0.0
            pairwise.append(
                {
                    "experimentA": a_id,
                    "experimentB": b_id,
                    "labelA": labels[a_id],
                    "labelB": labels[b_id],
                    "sizeA": len(set_a),
                    "sizeB": len(set_b),
                    "intersection": len(shared),
                    "union": len(combined),
                    "jaccard": round(jaccard, 4),
                    "sharedGenes": sorted(shared),
                    "uniqueA": sorted(set_a - set_b),
                    "uniqueB": sorted(set_b - set_a),
                }
            )

    # Per-experiment summary
    all_genes: set[str] = set()
    for gs in gene_sets.values():
        all_genes |= gs

    # Track which experiments each gene appears in
    gene_to_experiments: dict[str, list[str]] = {}
    for eid, gs in gene_sets.items():
        for gid in gs:
            gene_to_experiments.setdefault(gid, []).append(eid)

    # Genes present in every experiment
    universal = {
        gid
        for gid, exps in gene_to_experiments.items()
        if len(exps) == len(experiment_ids)
    }

    per_experiment: list[JSONObject] = []
    for exp in experiments:
        gs = gene_sets[exp.id]
        shared_count = sum(1 for gid in gs if len(gene_to_experiments[gid]) > 1)
        per_experiment.append(
            {
                "experimentId": exp.id,
                "label": labels[exp.id],
                "totalGenes": len(gs),
                "uniqueGenes": len(gs) - shared_count,
                "sharedGenes": shared_count,
            }
        )

    gene_membership: list[JSONObject] = [
        {
            "geneId": gid,
            "foundIn": len(exps),
            "totalExperiments": len(experiment_ids),
            "experiments": sorted(exps),
        }
        for gid, exps in sorted(gene_to_experiments.items())
    ]

    return {
        "experimentIds": list(experiment_ids),
        "experimentLabels": labels,
        "pairwise": pairwise,
        "perExperiment": per_experiment,
        "universalGenes": sorted(universal),
        "totalUniqueGenes": len(all_genes),
        "geneMembership": gene_membership,
    }
