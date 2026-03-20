"""Shared service for browsing WDK step results.

Used by both experiment and gene set endpoints to avoid duplicating
attribute listing, record browsing, distribution, and analysis logic.
"""

from typing import cast

from veupath_chatbot.integrations.veupathdb.factory import get_site
from veupath_chatbot.integrations.veupathdb.strategy_api.api import StrategyAPI
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.experiment.enrichment_parser import (
    is_enrichment_analysis,
    parse_enrichment_from_raw,
)
from veupath_chatbot.services.experiment.types import to_json
from veupath_chatbot.services.wdk.helpers import (
    build_attribute_list,
    extract_detail_attributes,
    merge_analysis_params,
    order_primary_key,
)

logger = get_logger(__name__)


class StepResultsService:
    """Provides read-only access to WDK step results.

    Encapsulates the shared logic for attributes, records, distributions,
    and analyses that both experiments and gene sets need.
    """

    def __init__(
        self,
        api: StrategyAPI,
        *,
        step_id: int,
        record_type: str,
    ) -> None:
        self._api = api
        self._step_id = step_id
        self._record_type = record_type

    async def get_attributes(self) -> JSONObject:
        """Get available attributes for the record type."""
        info = await self._api.get_record_type_info(self._record_type)
        attrs_raw = info.get("attributes") or info.get("attributesMap") or {}
        attr_list = cast("JSONValue", build_attribute_list(attrs_raw))
        return {
            "attributes": attr_list,
            "recordType": self._record_type,
        }

    async def get_records(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        sort: str | None = None,
        direction: str = "ASC",
        attributes: list[str] | None = None,
    ) -> JSONObject:
        """Get paginated result records."""
        sorting: list[JSONObject] | None = None
        if sort:
            sorting = [{"attributeName": sort, "direction": direction.upper()}]

        answer = await self._api.get_step_records(
            step_id=self._step_id,
            attributes=attributes,
            pagination={"offset": offset, "numRecords": limit},
            sorting=sorting,
        )
        records = answer.get("records", [])
        meta = answer.get("meta", {})
        return {"records": records, "meta": meta}

    async def get_distribution(self, attribute_name: str) -> JSONObject:
        """Get distribution data for an attribute."""
        return await self._api.get_column_distribution(self._step_id, attribute_name)

    async def list_analysis_types(self) -> JSONObject:
        """List available WDK step analysis types."""
        types = await self._api.list_analysis_types(self._step_id)
        return {"analysisTypes": types}

    async def get_strategy(self, strategy_id: int) -> JSONObject:
        """Get the WDK strategy tree."""
        return await self._api.get_strategy(strategy_id)

    async def run_analysis_raw(
        self,
        analysis_name: str,
        parameters: JSONObject,
    ) -> tuple[JSONObject, JSONObject]:
        """Run a WDK step analysis with merged defaults.

        Returns (raw_result, merged_params) so callers can handle
        enrichment parsing and persistence as needed.
        """
        form_meta = await self._api.get_analysis_type(self._step_id, analysis_name)
        params = merge_analysis_params(form_meta, parameters)

        logger.info(
            "Running WDK step analysis",
            step_id=self._step_id,
            analysis_type=analysis_name,
        )

        result = await self._api.run_step_analysis(
            step_id=self._step_id,
            analysis_type=analysis_name,
            parameters=params,
        )

        return result, params

    async def run_analysis(
        self,
        analysis_name: str,
        parameters: JSONObject,
    ) -> JSONObject:
        """Run a WDK step analysis, auto-parsing enrichment results."""
        result, params = await self.run_analysis_raw(analysis_name, parameters)

        if is_enrichment_analysis(analysis_name):
            er = parse_enrichment_from_raw(analysis_name, params, result)
            return {
                "_resultType": "enrichment",
                "enrichmentResults": [to_json(er)],
            }

        return result

    async def get_record_detail(
        self,
        primary_key: list[JSONObject],
        site_id: str,
    ) -> JSONObject:
        """Get a single record's full details by primary key.

        Fetches record type info to reorder PK parts and to extract
        a capped set of ``isInReport`` attribute names.  WDK interprets
        ``"attributes": []`` as "return zero attributes", so we must
        always pass explicit names.
        """
        pk_parts = primary_key
        detail_attrs: list[str] = []
        display_names: dict[str, str] = {}
        try:
            info = await self._api.get_record_type_info(self._record_type)

            pk_refs = info.get("primaryKeyColumnRefs") or info.get("primaryKey") or []
            if isinstance(pk_refs, list) and pk_refs:
                ref_strings = [str(r) for r in pk_refs if isinstance(r, str)]
                if ref_strings:
                    site = get_site(site_id)
                    pk_parts = order_primary_key(
                        pk_parts,
                        ref_strings,
                        pk_defaults={"project_id": site.project_id},
                    )

            attrs_raw = info.get("attributes") or info.get("attributesMap") or {}
            detail_attrs, display_names = extract_detail_attributes(attrs_raw)
        except Exception:
            logger.warning(
                "Failed to fetch record type info; falling back to raw PK",
                record_type=self._record_type,
                site_id=site_id,
                exc_info=True,
            )

        record = await self._api.get_single_record(
            record_type=self._record_type,
            primary_key=pk_parts,
            attributes=detail_attrs or None,
        )
        record["attributeNames"] = cast("JSONValue", display_names)
        return record
