"""AI tools for deep experiment result analysis.

Provides function-calling tools that let the AI assistant access
experiment data: paginate through records, look up individual genes,
get attribute distributions, compare gene groups, and search results.
"""

from typing import Annotated, cast

from kani import AIParam, ai_function

from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.ai_analysis_helpers import (
    build_primary_key,
    classify_gene,
    fetch_group_records,
    record_matches,
)
from veupath_chatbot.services.experiment.types import (
    Experiment,
)
from veupath_chatbot.services.wdk.helpers import extract_pk

# Cap search_results early to avoid bloating the LLM context window
# and to save unnecessary WDK API page fetches on broad queries.
_MAX_SEARCH_MATCHES = 20


class _AnalysisToolsMixin:
    """Mixin providing data-access @ai_function methods for analysis.

    Classes using this mixin must provide:
    - site_id: str
    - experiment_id: str
    - _get_experiment() -> Experiment | None  (async)
    """

    site_id: str = ""
    experiment_id: str = ""

    async def _get_experiment(self) -> Experiment | None: ...

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
        exp = await self._get_experiment()
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

        tp_ids, fp_ids, fn_ids, tn_ids = exp.classification_id_sets()

        classified: list[JSONObject] = []
        for rec in answer.records:
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

        total = answer.meta.total_count
        return cast(
            "JSONObject",
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
        exp = await self._get_experiment()
        if not exp:
            return {"error": "Experiment not found"}

        api = get_strategy_api(self.site_id)
        try:
            pk_parts = await build_primary_key(
                api, self.site_id, exp.config.record_type, gene_id
            )
            result = await api.get_single_record(
                record_type=exp.config.record_type,
                primary_key=pk_parts,
            )
            tp_ids, fp_ids, fn_ids, tn_ids = exp.classification_id_sets()
            classification = classify_gene(gene_id, tp_ids, fp_ids, fn_ids, tn_ids)
        except AppError as exc:
            return {"error": str(exc), "geneId": gene_id}
        else:
            return {
                "geneId": gene_id,
                "classification": classification,
                "record": result,
            }

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
        exp = await self._get_experiment()
        if not exp or not exp.wdk_step_id:
            return {"error": "Experiment has no WDK strategy"}

        api = get_strategy_api(self.site_id)
        try:
            return await api.get_column_distribution(exp.wdk_step_id, attribute_name)
        except AppError as exc:
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
        exp = await self._get_experiment()
        if not exp or not exp.wdk_step_id:
            return {"error": "Experiment has no WDK strategy"}

        api = get_strategy_api(self.site_id)
        group_a_attrs = await fetch_group_records(
            api, exp.config.record_type, group_a_ids, site_id=self.site_id
        )
        group_b_attrs = await fetch_group_records(
            api, exp.config.record_type, group_b_ids, site_id=self.site_id
        )

        return cast(
            "JSONObject",
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
        exp = await self._get_experiment()
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
            records = answer.records
            if not records:
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
                    if len(matches) >= _MAX_SEARCH_MATCHES:
                        return cast(
                            "JSONObject",
                            {
                                "matches": matches,
                                "totalScanned": total_scanned,
                            },
                        )

        return cast("JSONObject", {"matches": matches, "totalScanned": total_scanned})
