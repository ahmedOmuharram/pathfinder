"""Per-tool result extractors that compress a prior turn's tool calls into short notes."""

import json
from collections.abc import Callable

from pydantic import ValidationError

from pathfinder.ai.context.models import ToolCallRecord
from pathfinder.ai.tools.standalone._result_models import (
    DownloadUrlResult,
    EstimatedSizeResult,
    SampleRecordsResult,
)
from pathfinder.ai.tools.standalone._validation_helpers import StepOkResponse
from pathfinder.ai.tools.standalone._workbench_models import (
    EnrichmentResultsResponse,
    EvaluationSummaryResult,
    GeneSetCreatedResponse,
    GeneSetListResponse,
)
from pathfinder.services.catalog.overview_formatting import SearchOverviewResult
from pathfinder.services.catalog.param_formatting import ParameterInfo

ToolResultExtractor = Callable[[ToolCallRecord], str]

_GENERIC_MAX = 80
_OVERVIEW_NAME_PREVIEW = 3
_DISCOVERY_NAME_PREVIEW = 5


# ---------------------------------------------------------------------------
# Error + generic fallback
# ---------------------------------------------------------------------------


def _extract_error(record: ToolCallRecord) -> str:
    raw = record.result[:_GENERIC_MAX]
    if len(record.result) > _GENERIC_MAX:
        raw += "..."
    return f"error: {raw}"


def _extract_generic(record: ToolCallRecord) -> str:
    if len(record.result) <= _GENERIC_MAX:
        return record.result
    return record.result[:_GENERIC_MAX] + "..."


# ---------------------------------------------------------------------------
# Group 1: Graph mutation
# ---------------------------------------------------------------------------


def _extract_graph_mutation(record: ToolCallRecord) -> str:
    resp = StepOkResponse.model_validate_json(record.result)
    step = resp.step
    step_id = step.id
    # A combine step carries an operator. Every other step carries a search name.
    label = step.operator or step.search_name or step.display_name or "?"
    size_part = (
        f", {step.estimated_size} genes" if step.estimated_size is not None else ""
    )
    return f"{step_id}, {label}{size_part}"


# ---------------------------------------------------------------------------
# Group 2: Search overview
# ---------------------------------------------------------------------------


def _extract_search_overview(record: ToolCallRecord) -> str:
    overview = SearchOverviewResult.model_validate_json(record.result)
    required_names = [p.name for p in overview.required]
    optional_count = len(overview.optional)
    if required_names:
        req_str = ", ".join(required_names)
        parts = f"required=[{req_str}]"
        if optional_count:
            parts += f", {optional_count} optional"
        return parts
    total = len(overview.required) + optional_count
    names = [
        p.name for p in (overview.required + overview.optional)[:_OVERVIEW_NAME_PREVIEW]
    ]
    return f"{total} params ({', '.join(names)})"


# ---------------------------------------------------------------------------
# Group 3: Parameter options
# ---------------------------------------------------------------------------


def _extract_parameter_options(record: ToolCallRecord) -> str:
    info = ParameterInfo.model_validate_json(record.result)
    name = info.name
    if info.allowed_values is not None:
        count = len(info.allowed_values)
        return f"{count} values for {name}"
    if info.allowed_values_tree is not None:
        lines = info.allowed_values_tree.count("\n") + 1
        return f"tree vocab for {name} ({lines} lines)"
    return f"info for {name}"


# ---------------------------------------------------------------------------
# Group 4: Search discovery (all return JSON arrays)
# ---------------------------------------------------------------------------


def _extract_search_discovery(record: ToolCallRecord) -> str:
    parsed = json.loads(record.result)
    if not isinstance(parsed, list):
        return "0 results"
    count = len(parsed)
    names: list[str] = []
    for item in parsed[:_DISCOVERY_NAME_PREVIEW]:
        if isinstance(item, dict):
            name = item.get("name") or item.get("displayName") or ""
            if name:
                names.append(str(name))
    if not names:
        return f"{count} results"
    names_str = ", ".join(names)
    if count > _DISCOVERY_NAME_PREVIEW:
        names_str += ", ..."
    return f"{count} results: {names_str}"


# ---------------------------------------------------------------------------
# Group 5: Result data
# ---------------------------------------------------------------------------


def _extract_sample_records(record: ToolCallRecord) -> str:
    result = SampleRecordsResult.model_validate_json(record.result)
    attr_count = len(result.attributes)
    return f"{result.total_count} records, {attr_count} attributes"


def _extract_estimated_size(record: ToolCallRecord) -> str:
    result = EstimatedSizeResult.model_validate_json(record.result)
    return f"{result.count} results"


def _extract_download_url(record: ToolCallRecord) -> str:
    result = DownloadUrlResult.model_validate_json(record.result)
    return f"{result.format} download ready"


# ---------------------------------------------------------------------------
# Group 6: Workbench
# ---------------------------------------------------------------------------


def _extract_create_gene_set(record: ToolCallRecord) -> str:
    result = GeneSetCreatedResponse.model_validate_json(record.result)
    gs = result.gene_set_created
    return f"created '{gs.name}' ({gs.gene_count} genes)"


def _extract_list_gene_sets(record: ToolCallRecord) -> str:
    result = GeneSetListResponse.model_validate_json(record.result)
    return f"{result.total_sets} gene sets"


def _extract_enrichment_results(record: ToolCallRecord) -> str:
    result = EnrichmentResultsResponse.model_validate_json(record.result)
    return f"{result.count} enrichment results"


def _extract_evaluation_summary(record: ToolCallRecord) -> str:
    result = EvaluationSummaryResult.model_validate_json(record.result)
    return f"evaluation: {result.status}"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_GRAPH_MUTATION_TOOLS = frozenset(
    {
        "delete_step",
        "add_step_filter",
        "add_step_analysis",
        "add_step_report",
    }
)

_SEARCH_DISCOVERY_TOOLS = frozenset(
    {
        "search_for_searches",
        "browse_search_categories",
        "list_searches",
        "list_transforms",
    }
)

_EXTRACTOR_REGISTRY: dict[str, ToolResultExtractor] = {
    "get_search_overview": _extract_search_overview,
    "get_parameter_options": _extract_parameter_options,
    "get_sample_records": _extract_sample_records,
    "get_estimated_size": _extract_estimated_size,
    "get_download_url": _extract_download_url,
    "create_workbench_gene_set": _extract_create_gene_set,
    "list_workbench_gene_sets": _extract_list_gene_sets,
    "get_enrichment_results": _extract_enrichment_results,
    "get_evaluation_summary": _extract_evaluation_summary,
}

for _tool in _GRAPH_MUTATION_TOOLS:
    _EXTRACTOR_REGISTRY[_tool] = _extract_graph_mutation

for _tool in _SEARCH_DISCOVERY_TOOLS:
    _EXTRACTOR_REGISTRY[_tool] = _extract_search_discovery


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def extract_tool_summary(record: ToolCallRecord) -> str:
    """Return a short summary of a completed tool call.

    A tool with no registered extractor, or an unparsable result, falls back
    to truncation.
    """
    if record.is_error:
        return _extract_error(record)
    extractor = _EXTRACTOR_REGISTRY.get(record.name, _extract_generic)
    try:
        return extractor(record)
    except ValidationError, ValueError, KeyError:
        return _extract_generic(record)
