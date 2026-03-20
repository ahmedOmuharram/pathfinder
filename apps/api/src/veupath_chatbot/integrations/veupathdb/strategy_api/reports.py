"""Core report and answer methods for the Strategy API.

Provides :class:`ReportsMixin` with methods to run reports, fetch step
answers and records, and get step counts.
"""

from typing import cast

from veupath_chatbot.integrations.veupathdb.strategy_api.base import StrategyAPIBase
from veupath_chatbot.platform.errors import DataParsingError
from veupath_chatbot.platform.types import JSONObject, JSONValue


class ReportsMixin(StrategyAPIBase):
    """Mixin providing report, answer, and step count methods."""

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

        Convenience wrapper around :meth:`get_step_records`.

        :param step_id: Step ID.
        :param attributes: Attributes to include in response.
        :param pagination: Offset and numRecords.
        :returns: Answer data with records.
        """
        return await self.get_step_records(
            step_id, attributes=attributes, pagination=pagination
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
            report_config["attributes"] = cast("JSONValue", attributes)
        if tables:
            report_config["tables"] = cast("JSONValue", tables)
        if pagination:
            report_config["pagination"] = cast("JSONValue", pagination)
        if sorting:
            report_config["sorting"] = cast("JSONValue", sorting)

        await self._ensure_session()
        return await self._standard_report(step_id, report_config)

    async def get_step_count(self, step_id: int) -> int:
        """Get result count for a step.

        Uses the standard report endpoint and reads ``meta.totalCount``
        (``JsonKeys.TOTAL_COUNT``).
        """
        await self._ensure_session()
        answer = await self._standard_report(
            step_id, {"pagination": {"offset": 0, "numRecords": 0}}
        )
        meta_raw = answer.get("meta")
        if not isinstance(meta_raw, dict):
            msg = "Step count: response missing 'meta' dict"
            raise DataParsingError(msg)
        total_count_raw = meta_raw.get("totalCount")
        if not isinstance(total_count_raw, int):
            msg = (
                f"Step count: 'meta.totalCount' is not an int "
                f"(got {type(total_count_raw).__name__}: {total_count_raw!r})"
            )
            raise DataParsingError(msg)
        return total_count_raw
