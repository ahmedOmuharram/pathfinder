"""AI tools for deep experiment result analysis.

Provides function-calling tools that let the AI assistant access
experiment data: paginate through records, look up individual genes,
get attribute distributions, and compare gene groups.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast

from kani import AIParam, ChatMessage, ai_function
from kani.engines.base import BaseEngine

if TYPE_CHECKING:
    from veupath_chatbot.ai.stubs.kani import Kani
else:
    from kani import Kani

from veupath_chatbot.ai.tools.catalog_tools import CatalogTools
from veupath_chatbot.ai.tools.research_registry import ResearchToolsMixin
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import Experiment
from veupath_chatbot.services.gene_lookup import lookup_genes_by_text
from veupath_chatbot.services.research import (
    LiteratureSearchService,
    WebSearchService,
)


class ExperimentAnalysisAgent(ResearchToolsMixin, Kani):
    """AI agent with data-access tools for experiment result analysis.

    Extends the base wizard tools with functions to browse records,
    look up gene details, compute attribute distributions, and
    compare gene subsets.
    """

    def __init__(
        self,
        engine: BaseEngine,
        site_id: str,
        experiment_id: str,
        system_prompt: str,
        chat_history: list[ChatMessage] | None = None,
    ) -> None:
        self.site_id = site_id
        self.experiment_id = experiment_id
        self._catalog = CatalogTools()
        self.web_search_service = WebSearchService()
        self.literature_search_service = LiteratureSearchService()

        self.strategy_session = type(
            "_Stub", (), {"get_graph": staticmethod(lambda: None)}
        )()

        super().__init__(
            engine=engine,
            system_prompt=system_prompt,
            chat_history=chat_history or [],
        )

    def _get_experiment(self) -> Experiment | None:
        store = get_experiment_store()
        return store.get(self.experiment_id)

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
                gene_id = _extract_pk(rec)
                classification = None
                if gene_id:
                    if gene_id in tp_ids:
                        classification = "TP"
                    elif gene_id in fp_ids:
                        classification = "FP"
                    elif gene_id in fn_ids:
                        classification = "FN"
                    elif gene_id in tn_ids:
                        classification = "TN"
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
            classification = None
            tp_ids = {g.id for g in exp.true_positive_genes}
            fp_ids = {g.id for g in exp.false_positive_genes}
            fn_ids = {g.id for g in exp.false_negative_genes}
            tn_ids = {g.id for g in exp.true_negative_genes}
            if gene_id in tp_ids:
                classification = "TP"
            elif gene_id in fp_ids:
                classification = "FP"
            elif gene_id in fn_ids:
                classification = "FN"
            elif gene_id in tn_ids:
                classification = "TN"
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
        group_a_attrs: list[JSONObject] = []
        group_b_attrs: list[JSONObject] = []

        for gene_id in group_a_ids[:20]:
            try:
                rec = await api.get_single_record(
                    record_type=exp.config.record_type,
                    primary_key=cast(
                        list[JSONObject], [{"name": "source_id", "value": gene_id}]
                    ),
                )
                if isinstance(rec, dict):
                    group_a_attrs.append(
                        {
                            "geneId": gene_id,
                            "attributes": rec.get("attributes", {}),
                        }
                    )
            except Exception:
                continue

        for gene_id in group_b_ids[:20]:
            try:
                rec = await api.get_single_record(
                    record_type=exp.config.record_type,
                    primary_key=cast(
                        list[JSONObject], [{"name": "source_id", "value": gene_id}]
                    ),
                )
                if isinstance(rec, dict):
                    group_b_attrs.append(
                        {
                            "geneId": gene_id,
                            "attributes": rec.get("attributes", {}),
                        }
                    )
            except Exception:
                continue

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

        for page_offset in range(0, 500, 100):
            answer = await api.get_step_records(
                step_id=exp.wdk_step_id,
                pagination={"offset": page_offset, "numRecords": 100},
            )
            records = answer.get("records", [])
            if not isinstance(records, list) or not records:
                break

            for rec in records:
                if not isinstance(rec, dict):
                    continue
                attrs = rec.get("attributes", {})
                if not isinstance(attrs, dict):
                    continue

                found = False
                if attribute:
                    val = attrs.get(attribute)
                    if isinstance(val, str) and query_lower in val.lower():
                        found = True
                else:
                    for val in attrs.values():
                        if isinstance(val, str) and query_lower in val.lower():
                            found = True
                            break

                if found:
                    gene_id = _extract_pk(rec)
                    matches.append(
                        {
                            "geneId": gene_id,
                            "attributes": attrs,
                        }
                    )
                    if len(matches) >= 20:
                        return cast(
                            JSONObject,
                            {"matches": matches, "totalScanned": page_offset + 100},
                        )

        return cast(
            JSONObject,
            {"matches": matches, "totalScanned": min(page_offset + 100, 500)},
        )

    @ai_function()
    async def lookup_genes(
        self,
        query: Annotated[
            str,
            AIParam(desc="Free-text query — gene name, symbol, or description"),
        ],
        organism: Annotated[
            str | None,
            AIParam(desc="Optional organism name to filter results"),
        ] = None,
        limit: Annotated[int, AIParam(desc="Max results (1-30)")] = 10,
    ) -> JSONObject:
        """Search for gene records on the current VEuPathDB site."""
        return await lookup_genes_by_text(
            self.site_id,
            query,
            organism=organism,
            limit=min(limit, 30),
        )


def _extract_pk(record: JSONObject) -> str | None:
    """Extract primary key string from a WDK record."""
    pk = record.get("id")
    if isinstance(pk, list) and pk:
        first = pk[0]
        if isinstance(first, dict):
            val = first.get("value")
            if isinstance(val, str):
                return val.strip()
    return None
