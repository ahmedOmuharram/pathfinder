"""Read-only AI tools for workbench experiment data access.

Provides function-calling tools that let the workbench AI agent read
experiment results: evaluation summary, enrichment, confidence scores,
step contributions, config, ensemble analysis, and gene lists by
classification category.

All tools follow the thin @ai_function wrapper pattern: fetch experiment
from store, return structured JSON, return {"error": ...} when data is
absent.
"""

from typing import Annotated, Literal, cast

from kani import AIParam, ai_function

from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import Experiment, to_json

ClassificationCategory = Literal["tp", "fp", "fn", "tn"]


class WorkbenchReadToolsMixin:
    """Mixin providing read-only @ai_function methods for workbench experiment data.

    Classes using this mixin must provide:
    - site_id: str
    - experiment_id: str
    - _get_experiment() -> Experiment | None  (async)
    """

    site_id: str = ""
    experiment_id: str = ""

    async def _get_experiment(self) -> Experiment | None:
        store = get_experiment_store()
        return await store.aget(self.experiment_id)

    @ai_function()
    async def get_evaluation_summary(self) -> JSONObject:
        """Get a summary of the experiment evaluation results.

        Returns classification metrics, confusion matrix counts, and sample
        gene IDs from each classification category (TP/FP/FN/TN).
        """
        exp = await self._get_experiment()
        if not exp:
            return {"error": "Experiment not found"}
        if not exp.metrics:
            return {"error": "Experiment has no evaluation metrics yet"}

        return cast(
            JSONObject,
            {
                "metrics": to_json(exp.metrics),
                "classificationCounts": {
                    "truePositives": len(exp.true_positive_genes),
                    "falsePositives": len(exp.false_positive_genes),
                    "falseNegatives": len(exp.false_negative_genes),
                    "trueNegatives": len(exp.true_negative_genes),
                },
                "sampleGeneIds": {
                    "truePositives": [g.id for g in exp.true_positive_genes[:5]],
                    "falsePositives": [g.id for g in exp.false_positive_genes[:5]],
                    "falseNegatives": [g.id for g in exp.false_negative_genes[:5]],
                    "trueNegatives": [g.id for g in exp.true_negative_genes[:5]],
                },
                "status": exp.status,
            },
        )

    @ai_function()
    async def get_enrichment_results(self) -> JSONObject:
        """Get the enrichment analysis results for this experiment.

        Returns GO term, pathway, and word enrichment results. Each result
        includes the analysis type, enriched terms with p-values, and
        background statistics.
        """
        exp = await self._get_experiment()
        if not exp:
            return {"error": "Experiment not found"}
        if not exp.enrichment_results:
            return {"error": "No enrichment results available for this experiment"}

        return cast(
            JSONObject,
            {
                "enrichmentResults": [to_json(r) for r in exp.enrichment_results],
                "count": len(exp.enrichment_results),
            },
        )

    @ai_function()
    async def get_confidence_scores(self) -> JSONObject:
        """Get cross-validation confidence scores for this experiment.

        Returns mean metrics, per-fold metrics, standard deviations, and
        overfitting assessment. Indicates how robustly the strategy generalises.
        """
        exp = await self._get_experiment()
        if not exp:
            return {"error": "Experiment not found"}
        if not exp.cross_validation:
            return {
                "error": "No cross-validation results available for this experiment"
            }

        return cast(
            JSONObject,
            {
                "crossValidation": to_json(exp.cross_validation),
            },
        )

    @ai_function()
    async def get_step_contributions(self) -> JSONObject:
        """Get the step contribution (ablation) analysis for this experiment.

        Returns per-step recall delta, FPR delta, and verdict indicating whether
        each search step adds meaningful value to the strategy.
        """
        exp = await self._get_experiment()
        if not exp:
            return {"error": "Experiment not found"}
        if not exp.step_analysis:
            return {"error": "No step analysis available for this experiment"}

        return cast(
            JSONObject,
            {
                "stepContributions": [
                    to_json(c) for c in exp.step_analysis.step_contributions
                ],
                "count": len(exp.step_analysis.step_contributions),
            },
        )

    @ai_function()
    async def get_experiment_config(self) -> JSONObject:
        """Get the experiment configuration, status, and WDK strategy IDs.

        Returns the full config (search name, parameters, controls, mode),
        current execution status, and WDK strategy/step IDs if available.
        """
        exp = await self._get_experiment()
        if not exp:
            return {"error": "Experiment not found"}

        return cast(
            JSONObject,
            {
                "config": to_json(exp.config),
                "status": exp.status,
                "wdkStrategyId": exp.wdk_strategy_id,
                "wdkStepId": exp.wdk_step_id,
                "notes": exp.notes,
                "createdAt": exp.created_at,
                "completedAt": exp.completed_at,
            },
        )

    @ai_function()
    async def get_ensemble_analysis(self) -> JSONObject:
        """Get the full ensemble step analysis for this experiment.

        Returns step evaluations, operator comparisons, step contributions,
        and parameter sensitivities. Useful for understanding multi-step
        strategy behaviour in detail.
        """
        exp = await self._get_experiment()
        if not exp:
            return {"error": "Experiment not found"}
        if not exp.step_analysis:
            return {"error": "No step analysis available for this experiment"}

        return cast(
            JSONObject,
            {
                "stepAnalysis": to_json(exp.step_analysis),
            },
        )

    @ai_function()
    async def get_result_gene_lists(
        self,
        classification: Annotated[
            str,
            AIParam(
                desc=(
                    "Classification category to return: "
                    "'tp' (true positives), 'fp' (false positives), "
                    "'fn' (false negatives), 'tn' (true negatives)"
                )
            ),
        ],
        limit: Annotated[
            int,
            AIParam(desc="Maximum number of gene IDs to return (max 200)"),
        ] = 50,
    ) -> JSONObject:
        """Get gene IDs for a specific classification category.

        Returns gene IDs and basic metadata (name, organism, product) for
        the requested category. Use 'tp' for hits that are known positives,
        'fp' for hits that are known negatives, 'fn' for missed known positives,
        'tn' for non-hits that are known negatives.
        """
        valid: set[str] = {"tp", "fp", "fn", "tn"}
        if classification not in valid:
            return {
                "error": f"Invalid classification '{classification}'. "
                f"Must be one of: {', '.join(sorted(valid))}"
            }

        exp = await self._get_experiment()
        if not exp:
            return {"error": "Experiment not found"}

        category = cast(ClassificationCategory, classification)
        gene_list = {
            "tp": exp.true_positive_genes,
            "fp": exp.false_positive_genes,
            "fn": exp.false_negative_genes,
            "tn": exp.true_negative_genes,
        }[category]

        capped = min(limit, 200)
        selected = gene_list[:capped]

        return cast(
            JSONObject,
            {
                "classification": classification,
                "genes": [to_json(g) for g in selected],
                "returned": len(selected),
                "total": len(gene_list),
            },
        )
