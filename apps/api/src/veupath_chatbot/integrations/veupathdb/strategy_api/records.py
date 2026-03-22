"""Record type info, single record, and column distribution methods.

Provides :class:`RecordsMixin` with methods for record type metadata,
individual record retrieval, and column value distributions.
"""

import pydantic

from veupath_chatbot.integrations.veupathdb.strategy_api.base import StrategyAPIBase
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKRecordInstance,
    WDKRecordType,
)
from veupath_chatbot.platform.errors import DataParsingError, WDKError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

logger = get_logger(__name__)


class RecordsMixin(StrategyAPIBase):
    """Mixin providing record type info, single record, and distribution methods."""

    async def get_record_type_info(self, record_type: str) -> WDKRecordType:
        """Get expanded record type info including attributes and tables.

        :param record_type: WDK record type (e.g. "gene").
        :returns: Validated record type metadata with attribute fields.
        """
        await self._ensure_session()
        raw = await self.client.get(
            f"/record-types/{record_type}",
            params={"format": "expanded"},
        )
        try:
            return WDKRecordType.model_validate(raw)
        except pydantic.ValidationError as e:
            msg = f"Unexpected WDK record type response for {record_type}: {e}"
            raise DataParsingError(msg) from e

    async def get_single_record(
        self,
        record_type: str,
        primary_key: list[dict[str, str]],
        *,
        attributes: list[str] | None = None,
        tables: list[str] | None = None,
    ) -> WDKRecordInstance:
        """Fetch a single record by its primary key.

        WDK's ``POST /record-types/{type}/records`` requires ``primaryKey``,
        ``attributes``, and ``tables`` arrays in the request body.  When
        ``attributes`` or ``tables`` are not provided we send empty arrays
        which tells WDK to return the default set.

        :param record_type: WDK record type.
        :param primary_key: List of ``{name, value}`` primary key parts.
        :param attributes: Attribute names to include (empty = default set).
        :param tables: Table names to include (empty = none).
        :returns: Validated record instance with requested attributes/tables.
        """
        payload: dict[str, object] = {
            "primaryKey": primary_key,
            "attributes": attributes or [],
            "tables": tables or [],
        }

        await self._ensure_session()
        raw = await self.client.post(
            f"/record-types/{record_type}/records",
            json=payload,
        )
        try:
            return WDKRecordInstance.model_validate(raw)
        except pydantic.ValidationError as e:
            msg = f"Unexpected WDK record response for {record_type}: {e}"
            raise DataParsingError(msg) from e

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
        await self._ensure_session()
        try:
            result = await self.client.post(
                f"/users/{self._resolved_user_id}/steps/{step_id}"
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
