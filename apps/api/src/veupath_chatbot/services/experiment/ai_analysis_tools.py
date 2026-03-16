"""AI tools for deep experiment result analysis.

Provides function-calling tools that let the AI assistant access
experiment data: paginate through records, look up individual genes,
get attribute distributions, compare gene groups, and search results.

The agent class is built dynamically via :func:`build_analysis_agent_class`
so that the services layer never needs a static import from
``veupath_chatbot.ai``.  The configured experiment-agent base class
is injected at startup.
"""

from typing import Annotated, Any, cast

from kani import AIParam, ChatMessage, Kani, ai_function
from kani.engines.base import BaseEngine

from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.ai_analysis_helpers import (
    build_primary_key,
    classify_gene,
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
from veupath_chatbot.services.wdk.helpers import extract_pk

# ── Injected base class ─────────────────────────────────────────────
# Set once at startup via configure().
_experiment_agent_cls: type[Kani] | None = None


def configure(*, experiment_agent_cls: type[Kani]) -> None:
    """Wire the experiment agent base class.

    Called once at application startup from the composition root.
    """
    global _experiment_agent_cls
    _experiment_agent_cls = experiment_agent_cls


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
        exp = await self._get_experiment()
        if not exp or not exp.wdk_step_id:
            return {"error": "Experiment has no WDK strategy"}

        api = get_strategy_api(self.site_id)
        try:
            return await api.get_column_distribution(exp.wdk_step_id, attribute_name)
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


class ExperimentAnalysisAgent(RefinementToolsMixin, _AnalysisToolsMixin, Kani):
    """AI agent with data-access and strategy-refinement tools.

    Combines analysis tools (data browsing, gene lookup, distributions)
    with refinement tools (add steps, filter, re-evaluate) and the
    experiment assistant's catalog/research tools (inherited via the
    injected base class).

    The base class is set dynamically at startup; if not configured,
    instantiation falls back to plain Kani.
    """

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)

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

        # If the experiment agent base was configured, delegate to its
        # __init__ (which sets up catalog tools, research tools, etc.).
        if _experiment_agent_cls is not None and _experiment_agent_cls is not Kani:
            # Dynamic dispatch: the actual class (ExperimentAssistantAgent)
            # accepts site_id, but the static type is type[Kani].
            init_fn = cast(Any, _experiment_agent_cls.__init__)
            init_fn(
                self,
                engine=engine,
                site_id=site_id,
                system_prompt=system_prompt,
                chat_history=chat_history,
            )
        else:
            super().__init__(
                engine=engine,
                system_prompt=system_prompt,
                chat_history=chat_history or [],
            )

    async def _get_experiment(self) -> Experiment | None:
        store = get_experiment_store()
        return await store.aget(self.experiment_id)
