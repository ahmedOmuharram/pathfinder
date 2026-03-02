"""AI tools for deep experiment result analysis.

Provides function-calling tools that let the AI assistant access
experiment data: paginate through records, look up individual genes,
get attribute distributions, compare gene groups, and search results.
"""

from __future__ import annotations

from typing import Annotated, cast

from kani import AIParam, ChatMessage, ai_function
from kani.engines.base import BaseEngine

from veupath_chatbot.ai.agents.experiment import ExperimentAssistantAgent
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.ai_analysis_helpers import (
    classify_gene,
    extract_pk,
    fetch_group_records,
    record_matches,
)
from veupath_chatbot.services.experiment.ai_refinement_tools import (
    RefinementToolsMixin,
)
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import (
    Experiment,
)


class ExperimentAnalysisAgent(RefinementToolsMixin, ExperimentAssistantAgent):
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
            return await api.get_filter_summary(exp.wdk_step_id, attribute_name)
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
