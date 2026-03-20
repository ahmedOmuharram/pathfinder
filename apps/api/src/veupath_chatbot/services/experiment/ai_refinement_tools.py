"""AI tools for experiment strategy refinement.

Provides function-calling tools that let the AI assistant refine the
experiment strategy: add new search steps, combine with gene ID lists,
and re-evaluate control metrics after refinement.
"""

from typing import Annotated, cast

from kani import AIParam, ai_function

from veupath_chatbot.domain.strategy.ast import StepTreeNode
from veupath_chatbot.domain.strategy.ops import (
    BOOLEAN_OPERATOR_OPTIONS_DESC,
    DEFAULT_COMBINE_OPERATOR,
)
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.control_tests import resolve_controls_param_type
from veupath_chatbot.services.experiment.ai_analysis_helpers import (
    collect_all_result_ids,
)
from veupath_chatbot.services.experiment.metrics import (
    compute_confusion_matrix,
    compute_metrics,
)
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import (
    Experiment,
    GeneInfo,
    to_json,
)


class RefinementToolsMixin:
    """Mixin providing strategy-refinement @ai_function methods.

    Classes using this mixin must provide:
    - site_id: str
    - _get_experiment() -> Experiment | None  (async)
    """

    site_id: str = ""

    async def _get_experiment(self) -> Experiment | None: ...

    @ai_function()
    async def refine_with_search(
        self,
        search_name: Annotated[str, AIParam(desc="WDK search name for the new step")],
        parameters: Annotated[
            dict[str, str], AIParam(desc="Search parameters as key-value pairs")
        ],
        operator: Annotated[
            str,
            AIParam(desc=f"Boolean operator: {BOOLEAN_OPERATOR_OPTIONS_DESC}"),
        ] = DEFAULT_COMBINE_OPERATOR.value,
    ) -> JSONObject:
        """Add a new search step and combine it with current experiment results.

        Creates a WDK search step, then combines it with the experiment's
        current results using the specified boolean operator. The experiment
        strategy is updated so subsequent queries reflect the refined results.
        Call re_evaluate_controls afterwards to see the impact on metrics.
        """
        exp = await self._get_experiment()
        if not exp or not exp.wdk_strategy_id or not exp.wdk_step_id:
            return {"error": "Experiment has no WDK strategy"}

        api = get_strategy_api(self.site_id)
        record_type = exp.config.record_type

        new_step = await api.create_step(
            record_type=record_type,
            search_name=search_name,
            parameters=cast("JSONObject", parameters),
            custom_name=f"AI refinement: {search_name}",
        )
        new_step_id = new_step.get("id") if isinstance(new_step, dict) else None
        if not isinstance(new_step_id, int):
            return {"error": "Failed to create new search step"}

        return await self._combine_and_update(exp, api, new_step_id, operator)

    @ai_function()
    async def refine_with_gene_ids(
        self,
        gene_ids: Annotated[
            list[str],
            AIParam(desc="List of gene IDs to filter/combine with"),
        ],
        operator: Annotated[
            str,
            AIParam(desc=f"Boolean operator: {BOOLEAN_OPERATOR_OPTIONS_DESC}"),
        ] = DEFAULT_COMBINE_OPERATOR.value,
    ) -> JSONObject:
        """Combine experiment results with a gene ID list.

        Creates a gene ID search step using the experiment's controls search
        configuration, then combines it with the current results. Use
        INTERSECT to filter results to only these genes, UNION to add them,
        or MINUS to exclude them.
        Call re_evaluate_controls afterwards to see the impact on metrics.
        """
        exp = await self._get_experiment()
        if not exp or not exp.wdk_strategy_id or not exp.wdk_step_id:
            return {"error": "Experiment has no WDK strategy"}

        api = get_strategy_api(self.site_id)
        record_type = exp.config.record_type
        controls_search = exp.config.controls_search_name
        controls_param = exp.config.controls_param_name

        param_type = await resolve_controls_param_type(
            api, record_type, controls_search, controls_param
        )

        params: JSONObject = {}
        if param_type == "input-dataset":
            dataset_id = await api.create_dataset(gene_ids)
            params[controls_param] = str(dataset_id)
        else:
            params[controls_param] = "\n".join(gene_ids)

        new_step = await api.create_step(
            record_type=record_type,
            search_name=controls_search,
            parameters=params,
            custom_name=f"AI gene list ({len(gene_ids)} genes)",
        )
        new_step_id = new_step.get("id") if isinstance(new_step, dict) else None
        if not isinstance(new_step_id, int):
            return {"error": "Failed to create gene list step"}

        result = await self._combine_and_update(exp, api, new_step_id, operator)
        result["geneCount"] = len(gene_ids)
        return result

    @ai_function()
    async def re_evaluate_controls(self) -> JSONObject:
        """Re-run control evaluation against the current (possibly refined) strategy.

        Computes updated classification metrics by checking which positive
        and negative control genes appear in the current result set.
        Use this after refining the strategy to see the impact on performance.
        """
        exp = await self._get_experiment()
        if not exp or not exp.wdk_step_id:
            return {"error": "Experiment has no WDK strategy"}

        api = get_strategy_api(self.site_id)

        result_ids = await collect_all_result_ids(api, exp.wdk_step_id)

        pos_controls = set(exp.config.positive_controls)
        neg_controls = set(exp.config.negative_controls)

        tp_ids = pos_controls & result_ids
        fn_ids = pos_controls - result_ids
        fp_ids = neg_controls & result_ids
        tn_ids = neg_controls - result_ids

        cm = compute_confusion_matrix(
            positive_hits=len(tp_ids),
            total_positives=len(pos_controls),
            negative_hits=len(fp_ids),
            total_negatives=len(neg_controls),
        )
        metrics = compute_metrics(cm, total_results=len(result_ids))

        exp.metrics = metrics
        exp.true_positive_genes = [GeneInfo(id=g) for g in sorted(tp_ids)]
        exp.false_negative_genes = [GeneInfo(id=g) for g in sorted(fn_ids)]
        exp.false_positive_genes = [GeneInfo(id=g) for g in sorted(fp_ids)]
        exp.true_negative_genes = [GeneInfo(id=g) for g in sorted(tn_ids)]

        store = get_experiment_store()
        store.save(exp)

        return cast(
            "JSONObject",
            {
                "success": True,
                "totalResults": len(result_ids),
                "metrics": to_json(metrics),
            },
        )

    # -- Internal helpers -------------------------------------------------

    async def _combine_and_update(
        self,
        exp: Experiment,
        api: StrategyAPI,
        new_step_id: int,
        operator: str,
    ) -> JSONObject:
        """Create a boolean combine step and update the experiment strategy.

        :param exp: Current experiment.
        :param api: Strategy API instance.
        :param new_step_id: ID of the new step to combine with.
        :param operator: Boolean operator (INTERSECT, UNION, MINUS).
        :returns: Result dict with success status and new step info.
        """
        if exp.wdk_strategy_id is None:
            msg = "exp.wdk_strategy_id must not be None"
            raise RuntimeError(msg)
        if exp.wdk_step_id is None:
            msg = "exp.wdk_step_id must not be None"
            raise RuntimeError(msg)

        combined = await api.create_combined_step(
            primary_step_id=exp.wdk_step_id,
            secondary_step_id=new_step_id,
            boolean_operator=operator,
            record_type=exp.config.record_type,
            custom_name=f"AI {operator} refinement",
        )
        combined_id = combined.get("id") if isinstance(combined, dict) else None
        if not isinstance(combined_id, int):
            return {"error": "Failed to create combined step"}

        new_tree = StepTreeNode(
            combined_id,
            primary_input=StepTreeNode(exp.wdk_step_id),
            secondary_input=StepTreeNode(new_step_id),
        )
        await api.update_strategy(exp.wdk_strategy_id, step_tree=new_tree)

        exp.wdk_step_id = combined_id
        store = get_experiment_store()
        store.save(exp)

        try:
            count = await api.get_step_count(combined_id)
        except Exception:
            count = None

        return cast(
            "JSONObject",
            {
                "success": True,
                "newStepId": combined_id,
                "operator": operator,
                "resultCount": count,
            },
        )
