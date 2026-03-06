"""Report, answer, filter, and analysis methods for the Strategy API.

Provides :class:`ReportsMixin` with methods to run reports, fetch answers,
manage filters, and execute step analyses.
"""

from __future__ import annotations

import asyncio
from typing import cast

from veupath_chatbot.integrations.veupathdb.strategy_api.base import StrategyAPIBase
from veupath_chatbot.platform.errors import InternalError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue

logger = get_logger(__name__)


class ReportsMixin(StrategyAPIBase):
    """Mixin providing report, answer, filter, and analysis methods."""

    async def set_step_filter(
        self, step_id: int, filter_name: str, value: JSONValue, disabled: bool = False
    ) -> JSONValue:
        """Create or update a filter on a step."""
        await self._ensure_session()
        payload = {"name": filter_name, "value": value, "disabled": disabled}
        return await self.client.set_step_filter(
            self.user_id, step_id, filter_name, payload
        )

    async def delete_step_filter(self, step_id: int, filter_name: str) -> JSONValue:
        """Remove a filter from a step."""
        await self._ensure_session()
        return await self.client.delete_step_filter(self.user_id, step_id, filter_name)

    async def list_analysis_types(self, step_id: int) -> JSONArray:
        """List available analysis types for a step."""
        await self._ensure_session()
        return await self.client.list_analysis_types(self.user_id, step_id)

    async def get_analysis_type(self, step_id: int, analysis_type: str) -> JSONObject:
        """Get analysis form metadata for a step."""
        await self._ensure_session()
        return await self.client.get_analysis_type(self.user_id, step_id, analysis_type)

    async def list_step_analyses(self, step_id: int) -> JSONArray:
        """List analyses that have been run on a step."""
        await self._ensure_session()
        return await self.client.list_step_analyses(self.user_id, step_id)

    async def list_step_filters(self, step_id: int) -> JSONArray:
        """List available filters for a step."""
        await self._ensure_session()
        return await self.client.list_step_filters(self.user_id, step_id)

    _RETRIABLE_STATUSES = frozenset({"ERROR", "OUT_OF_DATE", "STEP_REVISED"})

    async def run_step_analysis(
        self,
        step_id: int,
        analysis_type: str,
        parameters: JSONObject | None = None,
        custom_name: str | None = None,
        poll_interval: float = 2.0,
        max_wait: float = 300.0,
        max_retries: int = 3,
    ) -> JSONObject:
        """Create, run, and wait for a WDK step analysis to complete.

        WDK step analysis is a multi-phase process:

        1. ``POST .../analyses`` -- create instance (returns ``analysisId``)
        2. ``POST .../analyses/{id}/result`` -- kick off execution
        3. ``GET  .../analyses/{id}/result/status`` -- poll until COMPLETE
        4. ``GET  .../analyses/{id}/result`` -- retrieve results

        Boolean/combined steps may return ``ERROR`` on the first run because
        sub-step answers haven't been computed yet.  Per the WDK source
        (``ExecutionStatus.requiresRerun``), the correct strategy is to
        re-run the **same** instance — the WDK backend resets to ``PENDING``
        and re-executes.

        :param step_id: WDK step ID (must be part of a strategy).
        :param analysis_type: Analysis plugin name (e.g. ``go-enrichment``).
        :param parameters: Analysis parameters.
        :param custom_name: Optional display name.
        :param poll_interval: Seconds between status polls.
        :param max_wait: Maximum seconds to wait before giving up.
        :param max_retries: Maximum re-run attempts for retriable statuses.
        :returns: Analysis result JSON.
        :raises InternalError: If the analysis fails or times out.
        """
        await self._ensure_session()

        # Phase 0: Warm up the step answer.
        # Boolean/combined steps need their answer materialized before WDK
        # will run analyses.  A zero-record standard report forces WDK to
        # compute and cache the answer for the step (and all sub-steps).
        logger.info("Warming up step answer", step_id=step_id)
        warmup = await self.client.post(
            f"/users/{self.user_id}/steps/{step_id}/reports/standard",
            json={"reportConfig": {"pagination": {"offset": 0, "numRecords": 0}}},
        )
        warmup_count = None
        if isinstance(warmup, dict):
            meta = warmup.get("meta")
            if isinstance(meta, dict):
                warmup_count = meta.get("totalCount")
        logger.info("Step answer warmed up", step_id=step_id, total_count=warmup_count)

        # Phase 1: Create the analysis instance
        payload: JSONObject = {
            "analysisName": analysis_type,
            "parameters": parameters or {},
        }
        if custom_name:
            payload["displayName"] = custom_name

        instance = await self.client.create_step_analysis(
            self.user_id, step_id, payload
        )
        analysis_id = instance.get("analysisId") if isinstance(instance, dict) else None
        if not isinstance(analysis_id, int):
            raise InternalError(
                title="Step analysis creation failed",
                detail=f"No analysisId in response: {instance!r}",
            )

        logger.info(
            "Created step analysis instance",
            step_id=step_id,
            analysis_type=analysis_type,
            analysis_id=analysis_id,
        )

        # Phase 2: Kick off execution
        await self.client.run_analysis_instance(self.user_id, step_id, analysis_id)

        # Phase 3: Poll for completion
        elapsed = 0.0
        retries = 0
        while elapsed < max_wait:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            status_resp = await self.client.get_analysis_status(
                self.user_id, step_id, analysis_id
            )
            status = (
                str(status_resp.get("status", ""))
                if isinstance(status_resp, dict)
                else ""
            )
            logger.debug(
                "Analysis status poll",
                analysis_id=analysis_id,
                status=status,
                elapsed=elapsed,
            )

            if status == "COMPLETE":
                break
            if status in ("EXPIRED", "INTERRUPTED"):
                raise InternalError(
                    title="Step analysis failed",
                    detail=f"Analysis {analysis_id} ended with status: {status}",
                )
            if status in self._RETRIABLE_STATUSES:
                retries += 1
                # Log the full status response for debugging
                logger.warning(
                    "Analysis returned retriable status",
                    analysis_id=analysis_id,
                    status=status,
                    status_response=status_resp,
                    retry=retries,
                )
                if retries > max_retries:
                    # Try to fetch the analysis instance and result for error details
                    try:
                        analyses = await self.client.list_step_analyses(
                            self.user_id, step_id
                        )
                        logger.error(
                            "Step analyses list on failure",
                            step_id=step_id,
                            analysis_id=analysis_id,
                            analyses=analyses,
                        )
                    except Exception as exc:
                        logger.error(
                            "Could not list step analyses",
                            error=str(exc),
                        )
                    try:
                        err_result = await self.client.get_analysis_result(
                            self.user_id, step_id, analysis_id
                        )
                        logger.error(
                            "Analysis error result",
                            analysis_id=analysis_id,
                            error_result=err_result,
                        )
                    except Exception as exc:
                        logger.error(
                            "Could not fetch analysis result",
                            analysis_id=analysis_id,
                            error=str(exc),
                        )
                    raise InternalError(
                        title="Analysis unavailable",
                        detail=(
                            f"VEuPathDB could not complete this analysis "
                            f"(returned {status} after {retries} attempts). "
                            f"This typically happens when the gene set is too "
                            f"small or lacks the required annotations."
                        ),
                    )
                # WDK's requiresRerun flag means re-running the same instance
                # resets it to PENDING and re-executes automatically.
                logger.warning(
                    "Re-running same analysis instance",
                    analysis_id=analysis_id,
                    status=status,
                    retry=retries,
                )
                await self.client.run_analysis_instance(
                    self.user_id, step_id, analysis_id
                )

        if elapsed >= max_wait:
            raise InternalError(
                title="Step analysis timed out",
                detail=f"Analysis {analysis_id} did not complete within {max_wait}s",
            )

        # Phase 4: Retrieve results
        result = await self.client.get_analysis_result(
            self.user_id, step_id, analysis_id
        )
        return result if isinstance(result, dict) else {}

    async def run_step_report(
        self, step_id: int, report_name: str, config: JSONObject | None = None
    ) -> JSONValue:
        """Run a report on a step."""
        await self._ensure_session()
        # reportConfig is a nested JSONObject, which is valid JSONValue
        report_config: JSONValue = config or {}
        payload: JSONObject = {"reportConfig": report_config}
        return await self.client.run_step_report(
            self.user_id, step_id, report_name, payload
        )

    async def get_step_answer(
        self,
        step_id: int,
        attributes: list[str] | None = None,
        pagination: dict[str, int] | None = None,
    ) -> JSONObject:
        """Get answer records for a step via the standard report endpoint.

        :param step_id: Step ID.
        :param attributes: Attributes to include in response.
        :param pagination: Offset and numRecords.
        :returns: Answer data with records.
        """
        report_config: JSONObject = {}
        if attributes:
            report_config["attributes"] = cast(JSONValue, attributes)
        if pagination:
            report_config["pagination"] = cast(JSONValue, pagination)

        await self._ensure_session()
        return cast(
            JSONObject,
            await self.client.post(
                f"/users/{self.user_id}/steps/{step_id}/reports/standard",
                json={"reportConfig": report_config},
            ),
        )

    async def get_step_records(
        self,
        step_id: int,
        attributes: list[str] | None = None,
        tables: list[str] | None = None,
        pagination: dict[str, int] | None = None,
        sorting: list[JSONObject] | None = None,
    ) -> JSONObject:
        """Get paginated records for a step with configurable attributes and sorting.

        :param step_id: WDK step ID (must be part of a strategy).
        :param attributes: Attribute names to include.
        :param tables: Table names to include.
        :param pagination: ``{offset, numRecords}`` for server-side paging.
        :param sorting: List of ``{attributeName, direction}`` dicts.
        :returns: Standard report response with ``records`` and ``meta``.
        """
        report_config: JSONObject = {}
        if attributes:
            report_config["attributes"] = cast(JSONValue, attributes)
        if tables:
            report_config["tables"] = cast(JSONValue, tables)
        if pagination:
            report_config["pagination"] = cast(JSONValue, pagination)
        if sorting:
            report_config["sorting"] = cast(JSONValue, sorting)

        await self._ensure_session()
        return cast(
            JSONObject,
            await self.client.post(
                f"/users/{self.user_id}/steps/{step_id}/reports/standard",
                json={"reportConfig": report_config},
            ),
        )

    async def get_record_type_info(self, record_type: str) -> JSONObject:
        """Get expanded record type info including attributes and tables.

        :param record_type: WDK record type (e.g. "gene").
        :returns: Record type metadata with attribute fields.
        """
        await self._ensure_session()
        return cast(
            JSONObject,
            await self.client.get(
                f"/record-types/{record_type}",
                params={"format": "expanded"},
            ),
        )

    async def get_single_record(
        self,
        record_type: str,
        primary_key: list[JSONObject],
        attributes: list[str] | None = None,
        tables: list[str] | None = None,
    ) -> JSONObject:
        """Fetch a single record by its primary key.

        WDK's ``POST /record-types/{type}/records`` requires ``primaryKey``,
        ``attributes``, and ``tables`` arrays in the request body.  When
        ``attributes`` or ``tables`` are not provided we send empty arrays
        which tells WDK to return the default set.

        :param record_type: WDK record type.
        :param primary_key: List of ``{name, value}`` primary key parts.
        :param attributes: Attribute names to include (empty = default set).
        :param tables: Table names to include (empty = none).
        :returns: Full record with requested attributes/tables.
        """
        payload: JSONObject = {
            "primaryKey": cast(JSONValue, primary_key),
            "attributes": cast(JSONValue, attributes or []),
            "tables": cast(JSONValue, tables or []),
        }

        await self._ensure_session()
        return cast(
            JSONObject,
            await self.client.post(
                f"/record-types/{record_type}/records",
                json=payload,
            ),
        )

    async def get_column_distribution(
        self, step_id: int, column_name: str
    ) -> JSONObject:
        """Get distribution data for a column using the byValue column reporter.

        Uses ``POST .../columns/{col}/reports/byValue`` which returns a
        ``histogram`` array and ``statistics`` object.  This replaces the
        deprecated ``filter-summary`` endpoint.

        Not all columns support the byValue reporter (e.g. overview or
        composite columns).  When WDK returns an error, an empty result
        is returned so the frontend can show a friendly message.

        :param step_id: WDK step ID (must be part of a strategy).
        :param column_name: Attribute/column name.
        :returns: ``{histogram: [...], statistics: {...}}``
        """
        from veupath_chatbot.platform.errors import WDKError

        await self._ensure_session()
        try:
            result = await self.client.post(
                f"/users/{self.user_id}/steps/{step_id}"
                f"/columns/{column_name}/reports/byValue",
                json={"reportConfig": {}},
            )
            return result if isinstance(result, dict) else {}
        except WDKError:
            logger.warning(
                "Column reporter unavailable",
                step_id=step_id,
                column_name=column_name,
            )
            return {"histogram": [], "statistics": {}}

    async def get_step_count(self, step_id: int) -> int:
        """Get result count for a step.

        Uses the standard report endpoint and reads ``meta.totalCount``
        (``JsonKeys.TOTAL_COUNT``).
        """
        await self._ensure_session()
        answer = await self.client.post(
            f"/users/{self.user_id}/steps/{step_id}/reports/standard",
            json={
                "reportConfig": {"pagination": {"offset": 0, "numRecords": 0}},
            },
        )
        if not isinstance(answer, dict):
            raise ValueError(
                f"Step count: expected dict response, got {type(answer).__name__}"
            )
        meta_raw = answer.get("meta")
        if not isinstance(meta_raw, dict):
            raise ValueError("Step count: response missing 'meta' dict")
        total_count_raw = meta_raw.get("totalCount")
        if not isinstance(total_count_raw, int):
            raise ValueError(
                f"Step count: 'meta.totalCount' is not an int "
                f"(got {type(total_count_raw).__name__}: {total_count_raw!r})"
            )
        return total_count_raw
