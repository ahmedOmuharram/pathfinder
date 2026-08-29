"""Async HTTP client for one site's EDA service."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Literal

import httpx
from pydantic import JsonValue, TypeAdapter

from pathfinder.integrations.eda.errors import eda_failure
from pathfinder.integrations.eda.models import (
    TABULAR_JSON,
    EdaAppInfo,
    EdaAppsResponse,
    EdaBinSpec,
    EdaComputeJob,
    EdaCountResponse,
    EdaDifferentialExpressionConfig,
    EdaDistributionResponse,
    EdaFilter,
    EdaPermissionEntry,
    EdaPermissionsResponse,
    EdaStudiesResponse,
    EdaStudyDetail,
    EdaStudyDetailResponse,
    EdaStudyOverview,
    VolcanoStatsResponse,
)
from pathfinder.platform.context import veupathdb_auth_token_ctx
from pathfinder.platform.errors import WDKLoginRequiredError

FILTERS: TypeAdapter[list[EdaFilter]] = TypeAdapter(list[EdaFilter])
JSON_BODY: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)

# Content negotiation is one exact string comparison; any other value is TSV.
_JSON_ONLY = "application/json"

_FIRST_ERROR_STATUS = 400


class EdaClient:
    """One site's EDA service. The request's own registered token authenticates it."""

    def __init__(self, *, base_url: str, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._transport: httpx.AsyncBaseTransport | None = None
        self._lock = asyncio.Lock()

    def install_transport(self, transport: httpx.AsyncBaseTransport) -> None:
        """Pin the transport a test drives. Production leaves it unset."""
        self._transport = transport

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    async def _http(self) -> httpx.AsyncClient:
        if self._client is not None and not self._client.is_closed:
            return self._client
        async with self._lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(
                    base_url=self.base_url,
                    timeout=httpx.Timeout(self.timeout),
                    transport=self._transport,
                    headers={"Content-Type": _JSON_ONLY},
                )
            return self._client

    def _token(self) -> str:
        token = veupathdb_auth_token_ctx.get()
        if not token:
            raise WDKLoginRequiredError
        return token

    async def request_json(
        self,
        method: Literal["GET", "POST", "PATCH", "DELETE"],
        path: str,
        *,
        json: JsonValue | None = None,
        params: dict[str, str] | None = None,
    ) -> JsonValue:
        client = await self._http()
        request = client.build_request(
            method,
            path,
            json=json,
            params=params,
            headers={"Accept": _JSON_ONLY, "Cookie": f"Authorization={self._token()}"},
        )
        response = await client.send(request)
        if response.status_code >= _FIRST_ERROR_STATUS:
            raise eda_failure(method, path, response.status_code, response.text)
        if not response.content or not response.text.strip():
            return None
        return JSON_BODY.validate_json(response.content)

    async def list_studies(self) -> list[EdaStudyOverview]:
        raw = await self.request_json("GET", "/studies")
        return EdaStudiesResponse.model_validate(raw).studies

    async def get_study(self, study_id: str) -> EdaStudyDetail:
        raw = await self.request_json("GET", f"/studies/{study_id}")
        return EdaStudyDetailResponse.model_validate(raw).study

    async def get_permissions(self) -> dict[str, EdaPermissionEntry]:
        raw = await self.request_json("GET", "/permissions")
        return EdaPermissionsResponse.model_validate(raw).per_dataset

    async def count(
        self,
        *,
        study_id: str,
        entity_id: str,
        filters: Sequence[EdaFilter],
    ) -> int:
        raw = await self.request_json(
            "POST",
            f"/studies/{study_id}/entities/{entity_id}/count",
            json={"filters": _filters(filters)},
        )
        return EdaCountResponse.model_validate(raw).count

    async def tabular(
        self,
        *,
        study_id: str,
        entity_id: str,
        filters: Sequence[EdaFilter],
        output_variable_ids: Sequence[str],
        num_rows: int | None = None,
        offset: int = 0,
    ) -> list[list[str]]:
        body: dict[str, JsonValue] = {
            "filters": _filters(filters),
            "outputVariableIds": list(output_variable_ids),
        }
        # An offset with no numRows is a server error, so both keys travel or neither.
        if num_rows is not None:
            body["reportConfig"] = {"paging": {"numRows": num_rows, "offset": offset}}
        raw = await self.request_json(
            "POST",
            f"/studies/{study_id}/entities/{entity_id}/tabular",
            json=body,
        )
        return TABULAR_JSON.validate_python(raw)

    async def distribution(
        self,
        *,
        study_id: str,
        entity_id: str,
        variable_id: str,
        filters: Sequence[EdaFilter],
        bin_spec: EdaBinSpec | None = None,
    ) -> EdaDistributionResponse:
        body: dict[str, JsonValue] = {
            "filters": _filters(filters),
            "valueSpec": "count",
        }
        # A binSpec is required for a continuous variable and refused otherwise.
        if bin_spec is not None:
            body["binSpec"] = bin_spec.model_dump(
                by_alias=True, mode="json", exclude_none=True
            )
        raw = await self.request_json(
            "POST",
            f"/studies/{study_id}/entities/{entity_id}"
            f"/variables/{variable_id}/distribution",
            json=body,
        )
        return EdaDistributionResponse.model_validate(raw)

    async def list_apps(self) -> list[EdaAppInfo]:
        raw = await self.request_json("GET", "/apps")
        return EdaAppsResponse.model_validate(raw).apps

    async def submit_compute(
        self,
        *,
        compute_name: str,
        study_id: str,
        config: EdaDifferentialExpressionConfig,
        filters: Sequence[EdaFilter],
        autostart: bool = True,
    ) -> EdaComputeJob:
        raw = await self.request_json(
            "POST",
            f"/computes/{compute_name}",
            json=_compute_body(study_id, config, filters),
            params={"autostart": "true" if autostart else "false"},
        )
        return EdaComputeJob.model_validate(raw)

    async def get_job(self, job_id: str) -> EdaComputeJob:
        raw = await self.request_json("GET", f"/jobs/{job_id}")
        return EdaComputeJob.model_validate(raw)

    async def compute_statistics(
        self,
        *,
        compute_name: str,
        study_id: str,
        config: EdaDifferentialExpressionConfig,
        filters: Sequence[EdaFilter],
    ) -> VolcanoStatsResponse:
        raw = await self.request_json(
            "POST",
            f"/computes/{compute_name}/statistics",
            json=_compute_body(study_id, config, filters),
        )
        return VolcanoStatsResponse.model_validate(raw)

    async def visualization_data(
        self,
        *,
        app: str,
        viz: str,
        study_id: str,
        compute_config: EdaDifferentialExpressionConfig,
        filters: Sequence[EdaFilter],
    ) -> VolcanoStatsResponse:
        raw = await self.request_json(
            "POST",
            f"/apps/{app}/visualizations/{viz}",
            json={
                "studyId": study_id,
                "filters": _filters(filters),
                "computeConfig": compute_config.model_dump(
                    by_alias=True, mode="json", exclude_none=True
                ),
                "config": {},
            },
        )
        return VolcanoStatsResponse.model_validate(raw)


def _filters(filters: Sequence[EdaFilter]) -> JsonValue:
    dumped: JsonValue = FILTERS.dump_python(list(filters), by_alias=True, mode="json")
    return dumped


def _compute_body(
    study_id: str,
    config: EdaDifferentialExpressionConfig,
    filters: Sequence[EdaFilter],
) -> dict[str, JsonValue]:
    """The submit body addresses the job, so a reader sends the same one."""
    return {
        "studyId": study_id,
        "filters": _filters(filters),
        "derivedVariables": [],
        "config": config.model_dump(by_alias=True, mode="json", exclude_none=True),
    }
