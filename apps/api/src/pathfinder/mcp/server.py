"""veupathdb-wdk-mcp: the WDK reads and writes this deployment serves over MCP.

The server is stateless. Every tool names its site by value, and every call acts
as the credential the transport gate verified.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from assistant_core.memory.embedding import embed_text
from assistant_core.platform.logging import get_logger
from assistant_core.platform.types import JSONObject
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools import ToolResult
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.lowlevel.server import request_ctx
from mcp.types import CallToolRequestParams, ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field
from starlette.requests import Request

from pathfinder import __version__
from pathfinder.domain.parameters.values import ParamValue
from pathfinder.integrations.embeddings.embed_fn import EmbedFn
from pathfinder.mcp.auth import McpCredential, wdk_identity
from pathfinder.mcp.schemas import (
    SearchCategory,
    SearchListing,
    StepDownloadUrl,
    TransformListing,
)
from pathfinder.platform.errors import ValidationError
from pathfinder.platform.keyed_locks import KeyedLock
from pathfinder.platform.tool_errors import ToolErrorPayload
from pathfinder.services import catalog, control_tests, gene_lookup, wdk
from pathfinder.services.catalog import public_strategy_search, sites
from pathfinder.services.catalog.models import RecordTypeInfo, SearchMatch
from pathfinder.services.catalog.overview_formatting import SearchOverviewResult
from pathfinder.services.catalog.param_formatting import GetParameterOptionsResult
from pathfinder.services.catalog.search_inspection import UnknownSearchError
from pathfinder.services.catalog.searches import VagueSearchQueryError
from pathfinder.services.control_tests import IntersectionConfig
from pathfinder.services.enrichment.types import (
    BackgroundSource,
    EnrichmentAnalysisType,
)
from pathfinder.services.experiment.types.control_result import ControlTestResult
from pathfinder.services.gene_lookup import GeneResolveResult, GeneSearchResult
from pathfinder.services.gene_sets import enrichment
from pathfinder.services.gene_sets.enrichment import GeneIdEnrichment
from pathfinder.services.strategies import build
from pathfinder.services.strategies.build import StepCountResult
from pathfinder.services.wdk import WDKAnswer, step_results

logger = get_logger(__name__)

SERVER_NAME = "veupathdb-wdk-mcp"

# The wire vocabulary a consumer reads off a tool. A server states it; the
# runtime that reads it is a separate distribution and is not imported here.
STREAM_PART_META_KEY = "org.veupathdb.assistant/streamPart"
MAX_CALL_SECONDS_META_KEY = "org.veupathdb.assistant/maxCallSeconds"

ENRICHMENT_PART_KIND = "data-wdk.enrichment-results"

# Five analysis types run three at a time, and each polls WDK to 300 seconds.
ENRICHMENT_MAX_CALL_SECONDS = 600
# The same control machinery the durable step variant estimates at 180 seconds.
CONTROL_TESTS_MAX_CALL_SECONDS = 180

_MAX_GENE_IDS = 200

# A call past a bound is refused by name, not narrowed in silence.
type GeneRecordLimit = Annotated[int, Field(ge=1, le=50)]
type SampleRecordLimit = Annotated[int, Field(ge=1, le=100)]

_GENE_RECORD_TYPES = frozenset({"gene", "transcript"})
_GENE_SAMPLE_ATTRIBUTES = ("gene_product", "gene_name", "organism")

_NO_CREDENTIAL = "The call carried no verified credential."

# One precedent-embedding pass per site: a second caller queues instead of
# doubling the allocation.
_EMBEDDING_PASS = KeyedLock()

_CLIENT_GONE = "The client closed the connection before the call finished."


class _Caller:
    """The HTTP request a served call arrives on, when it arrives on one.

    A stateless streamable-HTTP call runs in the session manager's task group,
    so the ASGI request ending does not cancel it. The work has to ask.
    """

    def __init__(self) -> None:
        self._request = _http_request()

    async def is_gone(self) -> bool:
        return self._request is not None and await self._request.is_disconnected()


def _http_request() -> Request | None:
    """The Starlette request of the call in flight, or None off the transport."""
    try:
        context = request_ctx.get()
    except LookupError:
        return None
    request = context.request
    return request if isinstance(request, Request) else None


def _embed_while_connected(caller: _Caller) -> EmbedFn:
    """An embedding call that refuses once the caller has walked away."""

    async def embed(texts: Sequence[str]) -> list[list[float]]:
        if await caller.is_gone():
            raise ToolError(_CLIENT_GONE)
        return await embed_text(texts)

    return embed


_INSTRUCTIONS = (
    "VEuPathDB WDK catalog, record, step and evidence tools. Every tool takes "
    "site_id. The catalog reads run on a service credential; the record, step "
    "and evidence tools act as the VEuPathDB user whose bearer the call carries."
)

_READ = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
_ADDITIVE_WRITE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    openWorldHint=False,
)


class _SiteArgument(BaseModel):
    """The site every served tool names."""

    model_config = ConfigDict(extra="ignore")

    site_id: str


def _verified_credential() -> McpCredential:
    """The credential the transport gate verified for this call."""
    token = get_access_token()
    if token is None:
        raise ToolError(_NO_CREDENTIAL)
    return McpCredential.model_validate(token, from_attributes=True)


class WdkIdentity(Middleware):
    """Runs every tool call as the credential the gate verified."""

    async def on_call_tool(
        self,
        context: MiddlewareContext[CallToolRequestParams],
        call_next: CallNext[CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        with wdk_identity(_verified_credential()):
            return await call_next(context)


class SiteGuard(Middleware):
    """Refuses a call that names a site this deployment does not serve."""

    async def on_call_tool(
        self,
        context: MiddlewareContext[CallToolRequestParams],
        call_next: CallNext[CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        site_id = _SiteArgument.model_validate(context.message.arguments or {}).site_id
        served = sorted(site.id for site in await sites.list_sites())
        if site_id not in served:
            msg = (
                f"site_id {site_id!r} is not a site this server serves. "
                f"Valid site_id values: {served}."
            )
            raise ToolError(msg)
        return await call_next(context)


def _payload_or_error(result: JSONObject | ToolErrorPayload) -> JSONObject:
    """Turn a service's error payload into a tool error that names its cause."""
    match result:
        case ToolErrorPayload():
            raise ToolError(result.message)
        case _:
            return result


def _bounded_gene_ids(gene_ids: list[str]) -> list[str]:
    """Trim and de-duplicate a gene list, and refuse one out of bounds."""
    ids = list(dict.fromkeys(value.strip() for value in gene_ids if value.strip()))
    if not ids:
        msg = "gene_ids holds no gene identifier."
        raise ToolError(msg)
    if len(ids) > _MAX_GENE_IDS:
        msg = (
            f"gene_ids holds {len(ids)} identifiers; one call takes at most "
            f"{_MAX_GENE_IDS}."
        )
        raise ToolError(msg)
    return ids


def _sample_attributes(record_type: str) -> list[str] | None:
    """The gene attributes to request, or None to keep the sample id-only."""
    if record_type in _GENE_RECORD_TYPES:
        return list(_GENE_SAMPLE_ATTRIBUTES)
    return None


# ---------------------------------------------------------------------------
# Catalog: user-independent reads a service credential may make.
# ---------------------------------------------------------------------------


async def list_record_types(site_id: str) -> list[RecordTypeInfo]:
    """List the record types a VEuPathDB site publishes.

    Args:
        site_id: VEuPathDB site, for example 'plasmodb'.
    """
    return await catalog.get_record_types(site_id)


async def search_for_searches(
    site_id: str,
    query: str,
    record_type: str = "transcript",
    keywords: list[str] | None = None,
    category: str | None = None,
    limit: int = 20,
) -> list[SearchMatch]:
    """Rank a site's searches against a description of what to find.

    Args:
        site_id: VEuPathDB site, for example 'plasmodb'.
        query: What you are looking for, in as much detail as you have.
        record_type: Record type to rank within. Gene searches are 'transcript'.
        keywords: Exact identifiers to match against search names.
        category: One category of the site ontology to restrict the candidates.
        limit: Largest number of matches to return.
    """
    try:
        return await catalog.search_for_searches(
            site_id,
            record_type=record_type,
            query=query,
            keywords=keywords or [],
            category=category,
            limit=limit,
        )
    except VagueSearchQueryError as exc:
        msg = f"query is not usable. {exc.rejection.message}"
        raise ToolError(msg) from exc


async def browse_search_categories(
    site_id: str,
    record_type: str = "transcript",
) -> list[SearchCategory]:
    """List the site ontology's search categories with example search names.

    Args:
        site_id: VEuPathDB site, for example 'plasmodb'.
        record_type: Record type. Gene searches are 'transcript'.
    """
    rows = await catalog.browse_search_categories(site_id, record_type)
    return [SearchCategory.model_validate(row) for row in rows]


async def list_searches(
    site_id: str,
    record_type: str = "transcript",
) -> list[SearchListing]:
    """List every search name of one record type, without descriptions.

    Args:
        site_id: VEuPathDB site, for example 'plasmodb'.
        record_type: Record type. Gene searches are 'transcript'.
    """
    rows = await catalog.list_searches(site_id, record_type)
    return [SearchListing.model_validate(row) for row in rows]


async def list_transforms(
    site_id: str,
    record_type: str = "transcript",
) -> list[TransformListing]:
    """List the searches that accept an input step, with their descriptions.

    Args:
        site_id: VEuPathDB site, for example 'plasmodb'.
        record_type: Record type. Gene searches are 'transcript'.
    """
    rows = await catalog.list_transforms(site_id, record_type)
    return [TransformListing.model_validate(row) for row in rows]


async def lookup_phyletic_codes(
    site_id: str,
    query: str,
    record_type: str = "transcript",
) -> JSONObject:
    """Look up the species and clade codes GenesByOrthologPattern accepts.

    Args:
        site_id: VEuPathDB site, for example 'plasmodb'.
        query: Species or clade name, for example 'falciparum' or 'Apicomplexa'.
        record_type: Record type. Gene searches are 'transcript'.
    """
    return _payload_or_error(
        await catalog.lookup_phyletic_codes(site_id, record_type, query)
    )


async def search_example_plans(
    site_id: str,
    query: str,
    limit: int = 3,
) -> list[JSONObject]:
    """Rank the site's public strategies against a research goal.

    Args:
        site_id: VEuPathDB site, for example 'plasmodb'.
        query: The research goal to match public strategies against.
        limit: Largest number of strategies to return.
    """
    caller = _Caller()
    async with _EMBEDDING_PASS(site_id):
        if await caller.is_gone():
            raise ToolError(_CLIENT_GONE)
        strategies = await wdk.get_strategy_api(site_id).list_public_strategies()
        try:
            return await public_strategy_search.rank_public_strategies_semantic(
                strategies, query, embed=_embed_while_connected(caller), limit=limit
            )
        except (OSError, RuntimeError, ValueError) as exc:
            logger.warning("Semantic strategy ranking unavailable", error=str(exc))
            return public_strategy_search.rank_public_strategies(
                strategies, query=query, limit=limit
            )


async def get_search_overview(
    site_id: str,
    search_name: str,
    record_type: str | None = None,
    query: str | None = None,
) -> SearchOverviewResult:
    """Read one search: what it returns, and the parameters it takes.

    Args:
        site_id: VEuPathDB site, for example 'plasmodb'.
        search_name: WDK search urlSegment, for example 'GenesByMolecularWeight'.
        record_type: Record type. Omit to resolve it from the site catalog.
        query: Terms that rank an oversized parameter vocabulary.
    """
    try:
        inspection = await catalog.inspect_search(
            site_id, search_name, record_type=record_type, query=query
        )
    except UnknownSearchError as exc:
        msg = f"search_name is not on this site. {exc.guidance}"
        raise ToolError(msg) from exc
    return inspection.overview


async def get_parameter_options(
    site_id: str,
    search_name: str,
    parameter_id: str,
    record_type: str | None = None,
    context_values: dict[str, str] | None = None,
    query: str | None = None,
) -> GetParameterOptionsResult:
    """Read one parameter's vocabulary under the parent values supplied.

    Args:
        site_id: VEuPathDB site, for example 'plasmodb'.
        search_name: WDK search urlSegment the parameter belongs to.
        parameter_id: Parameter name to read.
        record_type: Record type. Omit to resolve it from the site catalog.
        context_values: Values of the parameters this one depends on.
        query: Terms that narrow a vocabulary too large to travel whole.
    """
    return await catalog.read_parameter_options(
        site_id,
        search_name,
        parameter_id,
        record_type=record_type,
        context_values=context_values,
        query=query,
    )


# ---------------------------------------------------------------------------
# Records: gene lookups that act as the calling user.
# ---------------------------------------------------------------------------


async def lookup_gene_records(
    site_id: str,
    query: str,
    organism: str | None = None,
    limit: GeneRecordLimit = 10,
) -> GeneSearchResult:
    """Find gene records by name, symbol, product description or keyword.

    Args:
        site_id: VEuPathDB site, for example 'plasmodb'.
        query: Free text, for example 'PfAP2-G' or 'gametocyte surface antigen'.
        organism: Organism to restrict to, for example 'Plasmodium falciparum 3D7'.
        limit: Largest number of records to return.
    """
    return await gene_lookup.lookup_genes_by_text(
        site_id, query, organism=organism, limit=limit
    )


async def resolve_gene_ids_to_records(
    site_id: str,
    gene_ids: list[str],
    record_type: str = "transcript",
    search_name: str = "GeneByLocusTag",
    param_name: str = "ds_gene_ids",
) -> GeneResolveResult:
    """Resolve gene identifiers to full records.

    Args:
        site_id: VEuPathDB site, for example 'plasmodb'.
        gene_ids: Gene or locus tag identifiers, for example ['PF3D7_1222600'].
        record_type: Record type. Gene searches are 'transcript'.
        search_name: WDK search that accepts an identifier list.
        param_name: Parameter of that search which carries the identifier list.
    """
    return await gene_lookup.resolve_gene_ids(
        site_id,
        _bounded_gene_ids(gene_ids),
        record_type=record_type,
        search_name=search_name,
        param_name=param_name,
    )


# ---------------------------------------------------------------------------
# Step reads: they name a user's own step, so they need that user's bearer.
# ---------------------------------------------------------------------------


async def get_step_estimated_size(
    site_id: str,
    wdk_step_id: int,
    wdk_strategy_id: int | None = None,
) -> StepCountResult:
    """Count the results of a step that is already built in WDK.

    Args:
        site_id: VEuPathDB site, for example 'plasmodb'.
        wdk_step_id: WDK step id.
        wdk_strategy_id: WDK strategy id, which an imported strategy requires.
    """
    return await build.get_estimated_size_for_site(
        site_id, wdk_step_id, wdk_strategy_id
    )


async def get_step_sample_records(
    site_id: str,
    wdk_step_id: int,
    record_type: str,
    limit: SampleRecordLimit = 5,
) -> WDKAnswer:
    """Read the first records of a step that is already built in WDK.

    Args:
        site_id: VEuPathDB site, for example 'plasmodb'.
        wdk_step_id: WDK step id.
        record_type: Record type of the step. Gene steps are 'transcript'.
        limit: Number of records to return.
    """
    results = step_results.StepResultsService(
        wdk.get_strategy_api(site_id),
        step_id=wdk_step_id,
        record_type=record_type,
    )
    return await results.get_records(
        limit=limit, attributes=_sample_attributes(record_type)
    )


async def get_step_download_url(
    site_id: str,
    wdk_step_id: int,
    output_format: Literal["csv", "tab", "json"] = "csv",
    attributes: list[str] | None = None,
) -> StepDownloadUrl:
    """Create a temporary download URL for a step's results.

    Args:
        site_id: VEuPathDB site, for example 'plasmodb'.
        wdk_step_id: WDK step id.
        output_format: Download format.
        attributes: Attributes to include. Omit for the WDK default set.
    """
    url = await wdk.get_results_api(site_id).get_download_url(
        wdk_step_id,
        output_format=output_format,
        attributes=attributes,
    )
    return StepDownloadUrl(step_id=wdk_step_id, format=output_format, download_url=url)


# ---------------------------------------------------------------------------
# Evidence: the two tools that write into the calling user's account.
# ---------------------------------------------------------------------------


async def run_control_tests_on_search(
    site_id: str,
    target_search_name: str,
    target_parameters: dict[str, ParamValue],
    positive_controls: list[str] | None = None,
    negative_controls: list[str] | None = None,
    record_type: str = "transcript",
) -> ControlTestResult:
    """Intersect a search's results with known control genes.

    Creates a temporary WDK strategy in the calling user's account.

    Args:
        site_id: VEuPathDB site, for example 'plasmodb'.
        target_search_name: WDK search urlSegment to test.
        target_parameters: Parameter values, each in its typed shape.
        positive_controls: Gene ids the search should return.
        negative_controls: Gene ids the search should not return.
        record_type: Record type. Gene searches are 'transcript'.
    """
    positives = [value.strip() for value in (positive_controls or []) if value.strip()]
    negatives = [value.strip() for value in (negative_controls or []) if value.strip()]
    if not positives and not negatives:
        msg = "positive_controls or negative_controls must name a gene id."
        raise ToolError(msg)
    config = IntersectionConfig(
        site_id=site_id,
        record_type=record_type,
        target_search_name=target_search_name,
        target_parameters=dict(target_parameters),
        controls_search_name="GeneByLocusTag",
        controls_param_name="ds_gene_ids",
        controls_value_format="newline",
    )
    return await control_tests.run_positive_negative_controls(
        config,
        positive_controls=positives,
        negative_controls=negatives,
    )


async def enrich_gene_ids(
    site_id: str,
    gene_ids: list[str],
    background: BackgroundSource | None = None,
    enrichment_types: list[EnrichmentAnalysisType] | None = None,
) -> GeneIdEnrichment:
    """Run over-representation analysis on a gene list given by value.

    Creates a temporary WDK dataset and step in the calling user's account.

    Args:
        site_id: VEuPathDB site, for example 'plasmodb'.
        gene_ids: The genes to test, for example ['PF3D7_1222600'].
        background: The annotated genome the test runs against.
        enrichment_types: Analyses to run. Omit to run all five.
    """
    try:
        return await enrichment.enrich_gene_ids(
            site_id,
            gene_ids,
            background or BackgroundSource(),
            enrichment_types,
        )
    except ValidationError as exc:
        raise ToolError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class _ToolRow:
    """One served tool: what it does, what it claims, and what it declares."""

    fn: Callable[..., Any]
    annotations: ToolAnnotations
    meta: dict[str, Any] | None = None


TOOLS: tuple[_ToolRow, ...] = (
    _ToolRow(list_record_types, _READ),
    _ToolRow(search_for_searches, _READ),
    _ToolRow(browse_search_categories, _READ),
    _ToolRow(list_searches, _READ),
    _ToolRow(list_transforms, _READ),
    _ToolRow(lookup_phyletic_codes, _READ),
    _ToolRow(search_example_plans, _READ),
    _ToolRow(get_search_overview, _READ),
    _ToolRow(get_parameter_options, _READ),
    _ToolRow(lookup_gene_records, _READ),
    _ToolRow(resolve_gene_ids_to_records, _READ),
    _ToolRow(get_step_estimated_size, _READ),
    _ToolRow(get_step_sample_records, _READ),
    _ToolRow(get_step_download_url, _READ),
    _ToolRow(
        run_control_tests_on_search,
        _ADDITIVE_WRITE,
        {MAX_CALL_SECONDS_META_KEY: CONTROL_TESTS_MAX_CALL_SECONDS},
    ),
    _ToolRow(
        enrich_gene_ids,
        _ADDITIVE_WRITE,
        {
            STREAM_PART_META_KEY: {"kind": ENRICHMENT_PART_KIND, "version": 1},
            MAX_CALL_SECONDS_META_KEY: ENRICHMENT_MAX_CALL_SECONDS,
        },
    ),
)


def build_server() -> FastMCP[None]:
    """Build veupathdb-wdk-mcp with its sixteen tools and its per-call guards."""
    server: FastMCP[None] = FastMCP(
        name=SERVER_NAME,
        version=__version__,
        instructions=_INSTRUCTIONS,
        middleware=[WdkIdentity(), SiteGuard()],
    )
    for row in TOOLS:
        server.tool(row.fn, annotations=row.annotations, meta=row.meta)
    return server


__all__ = [
    "MAX_CALL_SECONDS_META_KEY",
    "SERVER_NAME",
    "STREAM_PART_META_KEY",
    "TOOLS",
    "SiteGuard",
    "WdkIdentity",
    "build_server",
]
