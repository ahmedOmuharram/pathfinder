"""AI tools for deep experiment result analysis and strategy refinement.

Provides function-calling tools that let the AI assistant access
experiment data: paginate through records, look up individual genes,
get attribute distributions, compare gene groups, and refine the
experiment strategy with new search steps or gene ID lists.
"""

from __future__ import annotations

from typing import Annotated, cast

from kani import AIParam, ChatMessage, ai_function
from kani.engines.base import BaseEngine

from veupath_chatbot.ai.agents.experiment import ExperimentAssistantAgent
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.integrations.veupathdb.strategy_api import (
    StepTreeNode,
    StrategyAPI,
)
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.control_tests import resolve_controls_param_type
from veupath_chatbot.services.experiment.ai_analysis_helpers import (
    classify_gene,
    collect_all_result_ids,
    extract_pk,
    fetch_group_records,
    record_matches,
)
from veupath_chatbot.services.experiment.metrics import (
    compute_confusion_matrix,
    compute_metrics,
)
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import (
    Experiment,
    GeneInfo,
    metrics_to_json,
)


class ExperimentAnalysisAgent(ExperimentAssistantAgent):
    """AI agent with data-access and strategy-refinement tools.

    Extends :class:`ExperimentAssistantAgent` (which provides catalog
    tools, gene lookup, and research tools) with functions to browse
    records, look up gene details, compute attribute distributions,
    compare gene subsets, and refine the experiment strategy.
    """

    def __init__(
        self,
        engine: BaseEngine,
        site_id: str,
        experiment_id: str,
        system_prompt: str,
        chat_history: list[ChatMessage] | None = None,
    ) -> None:
        self.experiment_id = experiment_id
        super().__init__(
            engine=engine,
            site_id=site_id,
            system_prompt=system_prompt,
            chat_history=chat_history,
        )

    def _get_experiment(self) -> Experiment | None:
        store = get_experiment_store()
        return store.get(self.experiment_id)

    # -- Data access tools ------------------------------------------------

    @ai_function()
    async def fetch_result_records(
        self,
        offset: Annotated[int, AIParam(desc="Page offset (0-based)")] = 0,
        limit: Annotated[int, AIParam(desc="Number of records (max 50)")] = 20,
        sort_attribute: Annotated[
            str | None,
            AIParam(desc="Attribute name to sort by"),
        ] = None,
        sort_direction: Annotated[str, AIParam(desc="ASC or DESC")] = "ASC",
    ) -> JSONObject:
        """Fetch paginated result records from the experiment's WDK search results.

        Each record includes attributes and a classification (TP/FP/FN/TN)
        based on the experiment's control genes.
        """
        exp = self._get_experiment()
        if not exp or not exp.wdk_step_id:
            return {"error": "Experiment has no WDK strategy"}

        api = get_strategy_api(self.site_id)
        sorting: list[JSONObject] | None = None
        if sort_attribute:
            sorting = [{"attributeName": sort_attribute, "direction": sort_direction}]

        answer = await api.get_step_records(
            step_id=exp.wdk_step_id,
            pagination={"offset": offset, "numRecords": min(limit, 50)},
            sorting=sorting,
        )

        tp_ids = {g.id for g in exp.true_positive_genes}
        fp_ids = {g.id for g in exp.false_positive_genes}
        fn_ids = {g.id for g in exp.false_negative_genes}
        tn_ids = {g.id for g in exp.true_negative_genes}

        records = answer.get("records", [])
        classified: list[JSONObject] = []
        if isinstance(records, list):
            for rec in records:
                if not isinstance(rec, dict):
                    continue
                gene_id = extract_pk(rec)
                classification = classify_gene(gene_id, tp_ids, fp_ids, fn_ids, tn_ids)
                attrs = rec.get("attributes", {})
                classified.append(
                    {
                        "geneId": gene_id,
                        "classification": classification,
                        "attributes": attrs,
                    }
                )

        meta = answer.get("meta", {})
        total = meta.get("totalCount", 0) if isinstance(meta, dict) else 0
        return cast(
            JSONObject,
            {
                "records": classified[:50],
                "totalCount": total,
                "offset": offset,
            },
        )

    @ai_function()
    async def lookup_gene_detail(
        self,
        gene_id: Annotated[str, AIParam(desc="Gene ID to look up")],
    ) -> JSONObject:
        """Get the full record details for a specific gene by its ID.

        Returns all attributes and tables for the gene from WDK.
        """
        exp = self._get_experiment()
        if not exp:
            return {"error": "Experiment not found"}

        api = get_strategy_api(self.site_id)
        pk_parts = cast(list[JSONObject], [{"name": "source_id", "value": gene_id}])
        try:
            result = await api.get_single_record(
                record_type=exp.config.record_type,
                primary_key=pk_parts,
            )
            tp_ids = {g.id for g in exp.true_positive_genes}
            fp_ids = {g.id for g in exp.false_positive_genes}
            fn_ids = {g.id for g in exp.false_negative_genes}
            tn_ids = {g.id for g in exp.true_negative_genes}
            classification = classify_gene(gene_id, tp_ids, fp_ids, fn_ids, tn_ids)
            return {
                "geneId": gene_id,
                "classification": classification,
                "record": result,
            }
        except Exception as exc:
            return {"error": str(exc), "geneId": gene_id}

    @ai_function()
    async def get_attribute_distribution(
        self,
        attribute_name: Annotated[
            str, AIParam(desc="Attribute name to get distribution for")
        ],
    ) -> JSONObject:
        """Get the distribution of values for a given attribute across all results.

        Useful for understanding patterns in the data.
        """
        exp = self._get_experiment()
        if not exp or not exp.wdk_step_id:
            return {"error": "Experiment has no WDK strategy"}

        api = get_strategy_api(self.site_id)
        try:
            return cast(
                JSONObject,
                await api.get_filter_summary(exp.wdk_step_id, attribute_name),
            )
        except Exception as exc:
            return {"error": str(exc), "attribute": attribute_name}

    @ai_function()
    async def compare_gene_groups(
        self,
        group_a_ids: Annotated[list[str], AIParam(desc="Gene IDs for group A")],
        group_b_ids: Annotated[list[str], AIParam(desc="Gene IDs for group B")],
    ) -> JSONObject:
        """Compare attributes of two groups of genes to find distinguishing features.

        Fetches records for both groups and identifies attribute differences.
        """
        exp = self._get_experiment()
        if not exp or not exp.wdk_step_id:
            return {"error": "Experiment has no WDK strategy"}

        api = get_strategy_api(self.site_id)
        group_a_attrs = await fetch_group_records(
            api, exp.config.record_type, group_a_ids
        )
        group_b_attrs = await fetch_group_records(
            api, exp.config.record_type, group_b_ids
        )

        return cast(
            JSONObject,
            {
                "groupA": group_a_attrs,
                "groupB": group_b_attrs,
                "groupACount": len(group_a_attrs),
                "groupBCount": len(group_b_attrs),
            },
        )

    @ai_function()
    async def search_results(
        self,
        query: Annotated[str, AIParam(desc="Text pattern to search for")],
        attribute: Annotated[
            str | None,
            AIParam(desc="Specific attribute to search in"),
        ] = None,
    ) -> JSONObject:
        """Search through result records for a text pattern.

        Iterates through result pages looking for records whose attributes
        match the query string.
        """
        exp = self._get_experiment()
        if not exp or not exp.wdk_step_id:
            return {"error": "Experiment has no WDK strategy"}

        api = get_strategy_api(self.site_id)
        matches: list[JSONObject] = []
        query_lower = query.lower()
        total_scanned = 0

        for page_offset in range(0, 500, 100):
            answer = await api.get_step_records(
                step_id=exp.wdk_step_id,
                pagination={"offset": page_offset, "numRecords": 100},
            )
            records = answer.get("records", [])
            if not isinstance(records, list) or not records:
                break
            total_scanned = page_offset + len(records)

            for rec in records:
                if not isinstance(rec, dict):
                    continue
                attrs = rec.get("attributes", {})
                if not isinstance(attrs, dict):
                    continue

                if record_matches(attrs, query_lower, attribute):
                    gene_id = extract_pk(rec)
                    matches.append({"geneId": gene_id, "attributes": attrs})
                    if len(matches) >= 20:
                        return cast(
                            JSONObject,
                            {
                                "matches": matches,
                                "totalScanned": total_scanned,
                            },
                        )

        return cast(JSONObject, {"matches": matches, "totalScanned": total_scanned})

    # -- Strategy refinement tools ----------------------------------------

    @ai_function()
    async def refine_with_search(
        self,
        search_name: Annotated[str, AIParam(desc="WDK search name for the new step")],
        parameters: Annotated[
            dict[str, str], AIParam(desc="Search parameters as key-value pairs")
        ],
        operator: Annotated[
            str,
            AIParam(desc="Boolean operator: INTERSECT, UNION, or MINUS"),
        ] = "INTERSECT",
    ) -> JSONObject:
        """Add a new search step and combine it with current experiment results.

        Creates a WDK search step, then combines it with the experiment's
        current results using the specified boolean operator. The experiment
        strategy is updated so subsequent queries reflect the refined results.
        Call re_evaluate_controls afterwards to see the impact on metrics.
        """
        exp = self._get_experiment()
        if not exp or not exp.wdk_strategy_id or not exp.wdk_step_id:
            return {"error": "Experiment has no WDK strategy"}

        api = get_strategy_api(self.site_id)
        record_type = exp.config.record_type

        new_step = await api.create_step(
            record_type=record_type,
            search_name=search_name,
            parameters=parameters,
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
            AIParam(desc="Boolean operator: INTERSECT, UNION, or MINUS"),
        ] = "INTERSECT",
    ) -> JSONObject:
        """Combine experiment results with a gene ID list.

        Creates a gene ID search step using the experiment's controls search
        configuration, then combines it with the current results. Use
        INTERSECT to filter results to only these genes, UNION to add them,
        or MINUS to exclude them.
        Call re_evaluate_controls afterwards to see the impact on metrics.
        """
        exp = self._get_experiment()
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
        exp = self._get_experiment()
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
            JSONObject,
            {
                "success": True,
                "totalResults": len(result_ids),
                "metrics": metrics_to_json(metrics),
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
        assert exp.wdk_strategy_id is not None
        assert exp.wdk_step_id is not None

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
            JSONObject,
            {
                "success": True,
                "newStepId": combined_id,
                "operator": operator,
                "resultCount": count,
            },
        )
