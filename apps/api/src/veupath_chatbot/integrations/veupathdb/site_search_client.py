"""HTTP client for VEuPathDB's site-search microservice (SOLR facade).

This module contains the Pydantic response models and the SiteSearchClient class.
It has no dependency on site_router to avoid circular imports — site_router manages
SiteSearchClient lifecycle alongside VEuPathDBClient instances.

The site-search service is distinct from the WDK service:
- Different repo: VEuPathDB/SiteSearchService
- Different deployment: own Docker image, own port
- Different URL root: /site-search (not /{prefix}/service)
- Different auth model: no cookies, no JSESSIONID
- Different protocol: POST with JSON body

Reference:
    https://github.com/VEuPathDB/SiteSearchService
    https://github.com/VEuPathDB/web-monorepo/blob/main/packages/libs/web-common/src/SiteSearch/Types.ts
"""

import asyncio
from dataclasses import dataclass

import httpx
from pydantic import Field, field_validator
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from veupath_chatbot.platform.errors import AppError, ErrorCode
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.pydantic_base import CamelModel

logger = get_logger(__name__)


class SiteSearchDocumentTypeField(CamelModel):
    """A field descriptor within a document type (search or summary field).

    Aligned with web-monorepo SiteSearchDocumentTypeField type:
    packages/libs/web-common/src/SiteSearch/Types.ts
    """

    name: str
    display_name: str
    term: str
    is_subtitle: bool = False


class SiteSearchDocumentType(CamelModel):
    """A document type returned in the site-search response.

    Discriminated union in TypeScript: when ``is_wdk_record_type`` is True,
    ``wdk_search_name`` contains the WDK search name (e.g. ``"GenesByText"``)
    that bridges site-search results to WDK strategy creation.

    Aligned with web-monorepo SiteSearchDocumentType type:
    packages/libs/web-common/src/SiteSearch/Types.ts
    """

    id: str
    display_name: str
    display_name_plural: str
    count: int = 0
    has_organism_field: bool = False
    search_fields: list[SiteSearchDocumentTypeField] = Field(default_factory=list)
    summary_fields: list[SiteSearchDocumentTypeField] = Field(default_factory=list)
    is_wdk_record_type: bool = False
    wdk_search_name: str | None = None


class SiteSearchCategory(CamelModel):
    """A category grouping document types.

    Aligned with web-monorepo SiteSearchCategory type:
    packages/libs/web-common/src/SiteSearch/Types.ts
    """

    name: str
    document_types: list[str] = Field(default_factory=list)


class SiteSearchDocument(CamelModel):
    """A single document from site-search results.

    Aligned with web-monorepo SiteSearchDocument type:
    packages/libs/web-common/src/SiteSearch/Types.ts
    """

    document_type: str = ""
    primary_key: list[str] = Field(default_factory=list)
    wdk_primary_key_string: str = ""
    hyperlink_name: str = ""
    organism: list[str] = Field(default_factory=list)
    score: float = 0.0
    summary_field_data: dict[str, str | list[str]] = Field(default_factory=dict)
    found_in_fields: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("organism", mode="before")
    @classmethod
    def _coerce_organism(cls, v: object) -> list[str]:
        """Handle both string and list forms (API returns list, TS type says string)."""
        if isinstance(v, str):
            return [v] if v else []
        if isinstance(v, list):
            return [str(x) for x in v if x]
        return []


class SiteSearchResults(CamelModel):
    """The searchResults portion of a site-search response."""

    total_count: int = 0
    documents: list[SiteSearchDocument] = Field(default_factory=list)


class SiteSearchResponse(CamelModel):
    """Full response from the VEuPathDB site-search service.

    All five top-level fields aligned with web-monorepo SiteSearchResponse type:
    packages/libs/web-common/src/SiteSearch/Types.ts
    """

    search_results: SiteSearchResults = Field(default_factory=SiteSearchResults)
    organism_counts: dict[str, int] = Field(default_factory=dict)
    document_types: list[SiteSearchDocumentType] = Field(default_factory=list)
    categories: list[SiteSearchCategory] = Field(default_factory=list)
    field_counts: dict[str, int] = Field(default_factory=dict)


@dataclass(frozen=True)
class DocumentTypeFilter:
    """Filter for restricting site-search to a specific document type.

    Mirrors the ``documentTypeFilter`` object in the SiteSearchService
    POST request body.
    """

    document_type: str
    found_only_in_fields: list[str] | None = None


class SiteSearchClient:
    """HTTP client for VEuPathDB's site-search microservice (SOLR facade).

    Separate from VEuPathDBClient because site-search is a separate service
    in the VEuPathDB ecosystem:
    - Different repo: VEuPathDB/SiteSearchService
    - Different deployment: own Docker image, own port
    - Different URL root: /site-search (not /{prefix}/service)
    - Different auth model: no cookies, no JSESSIONID
    - Different protocol: POST with JSON body (not mixed GET/POST)

    Lifecycle managed by SiteRouter alongside VEuPathDBClient instances.

    Reference:
        https://github.com/VEuPathDB/SiteSearchService
        https://github.com/VEuPathDB/web-monorepo/blob/main/packages/libs/web-common/src/SiteSearch/Types.ts
    """

    def __init__(
        self,
        base_url: str,
        project_id: str,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._project_id = project_id
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is not None and not self._client.is_closed:
            return self._client
        async with self._client_lock:
            if self._client is not None and not self._client.is_closed:
                return self._client
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout, read=90.0),
                follow_redirects=True,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
            return self._client

    async def search(
        self,
        search_text: str,
        *,
        document_type_filter: DocumentTypeFilter | None = None,
        organisms: list[str] | None = None,
        restrict_metadata_to_organisms: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SiteSearchResponse:
        """Query the site-search service via POST.

        Uses POST with JSON body, matching the VEuPathDB frontend:
        packages/libs/web-common/src/controllers/SiteSearchController.tsx

        Field names match SearchRequest.java:
        https://github.com/VEuPathDB/SiteSearchService

        Wraps all errors (including RetryError after exhausted retries) into
        AppError so callers only need ``except AppError``.
        """
        try:
            return await self._search_with_retry(
                search_text,
                document_type_filter=document_type_filter,
                organisms=organisms,
                restrict_metadata_to_organisms=restrict_metadata_to_organisms,
                limit=limit,
                offset=offset,
            )
        except RetryError as exc:
            raise AppError(
                ErrorCode.WDK_ERROR,
                f"Site-search request failed after retries: {exc}",
            ) from exc

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _search_with_retry(
        self,
        search_text: str,
        *,
        document_type_filter: DocumentTypeFilter | None = None,
        organisms: list[str] | None = None,
        restrict_metadata_to_organisms: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SiteSearchResponse:
        """Raw POST with tenacity retry on transient errors."""
        url = f"{self._base_url}/site-search"
        body: dict[str, object] = {
            "searchText": search_text or "*",
            "pagination": {
                "offset": offset,
                "numRecords": limit,
            },
            "restrictToProject": self._project_id,
        }
        if organisms:
            body["restrictSearchToOrganisms"] = organisms
        if restrict_metadata_to_organisms:
            body["restrictMetadataToOrganisms"] = restrict_metadata_to_organisms
        if document_type_filter:
            doc_filter: dict[str, object] = {
                "documentType": document_type_filter.document_type,
            }
            if document_type_filter.found_only_in_fields:
                doc_filter["foundOnlyInFields"] = (
                    document_type_filter.found_only_in_fields
                )
            body["documentTypeFilter"] = doc_filter

        try:
            client = await self._get_client()
            resp = await client.post(url, json=body)
            resp.raise_for_status()
            if not resp.content:
                return SiteSearchResponse()
            return SiteSearchResponse.model_validate(resp.json())
        except (httpx.TimeoutException, httpx.ConnectError):
            raise
        except httpx.HTTPError as exc:
            raise AppError(
                ErrorCode.WDK_ERROR,
                f"Site-search request failed: {exc}",
            ) from exc

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
