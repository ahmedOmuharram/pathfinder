"""Step analysis lifecycle for the Strategy API.

Provides :class:`AnalysisMixin` with methods to list analysis types,
create, run, poll, and retrieve step analysis results.
"""

import asyncio
from dataclasses import dataclass

from veupath_chatbot.integrations.veupathdb.strategy_api.base import StrategyAPIBase
from veupath_chatbot.platform.errors import InternalError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject

logger = get_logger(__name__)


@dataclass
class AnalysisPollConfig:
    """Polling options for :meth:`AnalysisMixin.run_step_analysis`."""

    poll_interval: float = 2.0
    max_wait: float = 300.0
    max_retries: int = 3


# Background tasks kept alive to prevent garbage collection.
_background_tasks: set[asyncio.Task[None]] = set()


class AnalysisMixin(StrategyAPIBase):
    """Mixin providing step analysis lifecycle methods."""

    _RETRIABLE_STATUSES = frozenset({"ERROR", "OUT_OF_DATE", "STEP_REVISED"})

    async def list_analysis_types(self, step_id: int) -> JSONArray:
        """List available analysis types for a step."""
        await self._ensure_session()
        return await self.client.list_analysis_types(self._resolved_user_id, step_id)

    async def get_analysis_type(self, step_id: int, analysis_type: str) -> JSONObject:
        """Get analysis form metadata for a step."""
        await self._ensure_session()
        return await self.client.get_analysis_type(self._resolved_user_id, step_id, analysis_type)

    async def list_step_analyses(self, step_id: int) -> JSONArray:
        """List analyses that have been run on a step."""
        await self._ensure_session()
        return await self.client.list_step_analyses(self._resolved_user_id, step_id)

    async def _warmup_step(self, step_id: int) -> None:
        """Warm up the step answer before running an analysis.

        Boolean/combined steps need their answer materialized before WDK
        will run analyses.  A zero-record standard report forces WDK to
        compute and cache the answer for the step (and all sub-steps).
        """
        logger.info("Warming up step answer", step_id=step_id)
        warmup = await self._standard_report(
            step_id, {"pagination": {"offset": 0, "numRecords": 0}}
        )
        logger.info(
            "Step answer warmed up",
            step_id=step_id,
            total_count=warmup.meta.total_count,
        )

    async def _create_analysis(
        self,
        step_id: int,
        analysis_type: str,
        parameters: JSONObject | None = None,
        custom_name: str | None = None,
    ) -> int:
        """Create a step analysis instance and return its ID.

        :param step_id: WDK step ID.
        :param analysis_type: Analysis plugin name (e.g. ``go-enrichment``).
        :param parameters: Analysis parameters.
        :param custom_name: Optional display name.
        :returns: The ``analysisId`` from WDK.
        :raises InternalError: If the response lacks an ``analysisId``.
        """
        payload: JSONObject = {
            "analysisName": analysis_type,
            "parameters": parameters or {},
        }
        if custom_name:
            payload["displayName"] = custom_name

        instance = await self.client.create_step_analysis(
            self._resolved_user_id, step_id, payload
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
        return analysis_id

    async def _poll_analysis(
        self,
        step_id: int,
        analysis_id: int,
        poll_interval: float,
        max_wait: float,
        max_retries: int,
    ) -> None:
        """Poll an analysis instance until completion, retrying on transient errors.

        :param step_id: WDK step ID.
        :param analysis_id: Analysis instance ID.
        :param poll_interval: Seconds between status polls.
        :param max_wait: Maximum seconds to wait before giving up.
        :param max_retries: Maximum re-run attempts for retriable statuses.
        :raises InternalError: If the analysis fails, expires, or times out.
        """
        elapsed = 0.0
        retries = 0
        while elapsed < max_wait:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            status_resp = await self.client.get_analysis_status(
                self._resolved_user_id, step_id, analysis_id
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
                return
            if status in ("EXPIRED", "INTERRUPTED"):
                raise InternalError(
                    title="Step analysis failed",
                    detail=f"Analysis {analysis_id} ended with status: {status}",
                )
            if status in self._RETRIABLE_STATUSES:
                retries += 1
                logger.warning(
                    "Analysis returned retriable status",
                    analysis_id=analysis_id,
                    status=status,
                    status_response=status_resp,
                    retry=retries,
                )
                if retries > max_retries:
                    self._log_analysis_failure(step_id, analysis_id)
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
                    self._resolved_user_id, step_id, analysis_id
                )

        raise InternalError(
            title="Step analysis timed out",
            detail=f"Analysis {analysis_id} did not complete within {max_wait}s",
        )

    def _log_analysis_failure(self, step_id: int, analysis_id: int) -> None:
        """Best-effort logging of analysis failure details.

        Fires off async tasks to fetch the analyses list and error result
        for debugging. Exceptions are caught and logged rather than propagated.
        """

        async def _fetch_debug_info() -> None:
            try:
                analyses = await self.client.list_step_analyses(self._resolved_user_id, step_id)
                logger.error(
                    "Step analyses list on failure",
                    step_id=step_id,
                    analysis_id=analysis_id,
                    analyses=analyses,
                )
            except Exception as exc:
                logger.exception(
                    "Could not list step analyses",
                    error=str(exc),
                )
            try:
                err_result = await self.client.get_analysis_result(
                    self._resolved_user_id, step_id, analysis_id
                )
                logger.error(
                    "Analysis error result",
                    analysis_id=analysis_id,
                    error_result=err_result,
                )
            except Exception as exc:
                logger.exception(
                    "Could not fetch analysis result",
                    analysis_id=analysis_id,
                    error=str(exc),
                )

        # Schedule but don't await -- fire and forget for debugging.
        # Store a reference to prevent garbage collection (RUF006).
        task = asyncio.create_task(_fetch_debug_info())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    async def run_step_analysis(
        self,
        step_id: int,
        analysis_type: str,
        parameters: JSONObject | None = None,
        custom_name: str | None = None,
        poll_config: AnalysisPollConfig | None = None,
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
        re-run the **same** instance -- the WDK backend resets to ``PENDING``
        and re-executes.

        :param step_id: WDK step ID (must be part of a strategy).
        :param analysis_type: Analysis plugin name (e.g. ``go-enrichment``).
        :param parameters: Analysis parameters.
        :param custom_name: Optional display name.
        :param poll_config: Polling options (interval, max_wait, max_retries).
        :returns: Analysis result JSON.
        :raises InternalError: If the analysis fails or times out.
        """
        await self._ensure_session()
        cfg = poll_config or AnalysisPollConfig()

        # Phase 0: Warm up step answer
        await self._warmup_step(step_id)

        # Phase 1: Create analysis instance
        analysis_id = await self._create_analysis(
            step_id, analysis_type, parameters, custom_name
        )

        # Phase 2: Kick off execution
        await self.client.run_analysis_instance(self._resolved_user_id, step_id, analysis_id)

        # Phase 3: Poll for completion (raises on failure/timeout)
        await self._poll_analysis(
            step_id, analysis_id, cfg.poll_interval, cfg.max_wait, cfg.max_retries
        )

        # Phase 4: Retrieve results
        result = await self.client.get_analysis_result(
            self._resolved_user_id, step_id, analysis_id
        )
        return result if isinstance(result, dict) else {}
