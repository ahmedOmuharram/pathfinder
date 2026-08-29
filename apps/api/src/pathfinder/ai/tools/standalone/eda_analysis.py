"""Agent tools that open an EDA analysis, subset it, and count what is left."""

from __future__ import annotations

from assistant_core.platform.types import JSONObject
from pydantic import JsonValue
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import ToolReturn

from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.ai.tools.standalone._eda_models import (
    EdaAnalysisOpened,
    EdaFilterSheetEntry,
    EdaFiltersResult,
    EdaSubsetPreviewResult,
)
from pathfinder.ai.tools.standalone._eda_stream_parts import (
    eda_analysis_state_chunk,
    eda_subset_preview_chunk,
)
from pathfinder.domain.eda import (
    find_gene_entity,
    walk_entities,
)
from pathfinder.services.eda import EdaFilter, EdaStudyDetail
from pathfinder.services.eda.authoring import SubsetRejectedError, preview_subset
from pathfinder.services.eda.binding import (
    ConversationAnalysisView,
    apply_filters,
    bind_analysis,
    bound_conversation_analysis,
    read_analysis,
)
from pathfinder.services.eda.catalog import (
    UnknownEdaDatasetError,
    get_study_detail_for_dataset,
)
from pathfinder.services.eda.description import (
    EdaPermissionFacts,
    EdaVariableOut,
    children_of,
    entity_facts,
    permission_facts,
    variable_at,
    variable_facts,
    variable_out,
    with_time_part,
)

_RE_SHEET_NOTE = (
    "vocabulary shown in the first sheet for this study; ask "
    "preview_eda_subset for this variable's distribution to see the values "
    "the current subset holds"
)

_LONGITUDE_EXAMPLE = (-180.0, 180.0)


async def _study(
    site_id: str,
    dataset_id: str,
) -> tuple[EdaPermissionFacts, EdaStudyDetail]:
    """The study behind a dataset id, or the retry that names the right tool."""
    try:
        entry, study = await get_study_detail_for_dataset(site_id, dataset_id)
    except UnknownEdaDatasetError as exc:
        msg = f"{exc.guidance} Call search_eda_studies to find a real datasetId."
        raise ModelRetry(msg) from exc
    return permission_facts(entry), study


async def open_eda_analysis(
    ctx: RunContext[LeadDeps],
    dataset_id: str,
    purpose: str,
) -> ToolReturn[EdaAnalysisOpened]:
    """Open an EDA analysis on a study, so filters and computes have somewhere
    to live.

    This creates a real analysis document in the researcher's VEuPathDB
    workspace and binds it to this conversation. From then on set_eda_filters,
    preview_eda_subset, run_eda_compute and create_eda_step all act on it, and
    the researcher sees the same analysis in the EDA tab and on the VEuPathDB
    site.

    One conversation holds one open analysis at a time. Opening a second one
    replaces the binding, so open the study you actually mean, after
    describe_eda_study confirms it carries the variables the question needs.

    ``purpose`` becomes the analysis's display name in the researcher's
    workspace, so write what the subset is for in their words - "P. berghei
    rows with successful genetic modification", not "analysis 1". The
    workspace label holds 50 characters, and a longer one is cut to fit.

    Args:
        ctx: Agent run context.
        dataset_id: The ``datasetId`` from search_eda_studies. A ``DS_`` or
            ``EDAUD_`` id, never a ``STUDY_`` id.
        purpose: What this analysis is for, in the researcher's words.
    """
    site_id = ctx.deps.runtime.site_id
    _entry, study = await _study(site_id, dataset_id)
    gene = find_gene_entity(study)
    state = await bind_analysis(
        site_id,
        dataset_id=dataset_id,
        conversation_id=ctx.deps.state.conversation_id,
        display_name=purpose,
    )
    opened = EdaAnalysisOpened(
        analysis_id=state.analysis_id,
        dataset_id=dataset_id,
        study_id=state.study_id,
        display_name=state.display_name,
        study_display_name=state.study_display_name,
        gene_entity_id=gene.entity_id,
        can_export_rows=state.can_export_rows,
        guidance=_opened_guidance(
            gene_problem=gene.error, can_export=state.can_export_rows
        ),
    )
    return ToolReturn(
        return_value=opened,
        metadata=[eda_analysis_state_chunk(state)],
    )


def _opened_guidance(*, gene_problem: str | None, can_export: bool) -> str:
    """What to do next, and what this study cannot do."""
    lines = [
        "Call set_eda_filters with no filters to read the filter sheet, then "
        "again with the whole filter array.",
    ]
    if gene_problem is not None:
        lines.append(
            f"{gene_problem} This analysis cannot export rows into a strategy "
            f"step; report the counts and the distributions instead."
        )
    elif not can_export:
        lines.append(
            "This account cannot export this study's rows, so the analysis "
            "cannot export rows into a strategy step."
        )
    return " ".join(lines)


async def bound_analysis(
    ctx: RunContext[LeadDeps],
) -> ConversationAnalysisView | None:
    """The analysis this conversation has open, or None when it has none."""
    return await bound_conversation_analysis(
        conversation_id=ctx.deps.state.conversation_id
    )


def _example(entry: EdaVariableOut, *, first_values: dict[str, str]) -> JSONObject:
    """One complete filter object for this variable, built from what it declares."""
    example: JSONObject = {
        "entityId": entry.entity_id,
        "variableId": entry.variable_id,
        "type": entry.filter_type,
    }
    strings: list[JsonValue] = list(entry.vocabulary[:1])
    match entry.filter_type:
        case "stringSet":
            example["stringSet"] = strings
        case "numberSet":
            numbers: list[JsonValue] = [float(v) for v in entry.vocabulary[:1]]
            example["numberSet"] = numbers
        case "dateSet":
            dates: list[JsonValue] = [with_time_part(v) for v in entry.vocabulary[:1]]
            example["dateSet"] = dates
        case "numberRange":
            example["min"] = entry.range_min
            example["max"] = entry.range_max
        case "dateRange":
            example["min"] = entry.date_min
            example["max"] = entry.date_max
        case "longitudeRange":
            example["left"], example["right"] = _LONGITUDE_EXAMPLE
        case _:
            sub_filters: list[JsonValue] = [
                _sub_filter_example(child, first_values)
                for child in entry.sub_filter_variable_ids[:2]
            ]
            example["operation"] = "union"
            example["subFilters"] = sub_filters
    return example


def _sub_filter_example(variable_id: str, first_values: dict[str, str]) -> JSONObject:
    """One sub-filter, with a value the child variable really carries."""
    value = first_values.get(variable_id)
    members: list[JsonValue] = [] if value is None else [value]
    return {"variableId": variable_id, "stringSet": members}


def _sheet_entries(study: EdaStudyDetail) -> list[EdaFilterSheetEntry]:
    """Every filterable variable of the study, with an example to copy."""
    described: list[tuple[str, EdaVariableOut]] = []
    first_values: dict[str, str] = {}
    for entity in walk_entities(study.root_entity):
        entity_name = entity_facts(entity).display_name
        for variable in entity.variables:
            facts = variable_facts(variable)
            if facts.vocabulary:
                first_values[facts.id] = facts.vocabulary[0]
            out = variable_out(
                entity_id=entity.id,
                facts=facts,
                sub_filter_variable_ids=children_of(entity, variable.id),
            )
            if out is not None:
                described.append((entity_name, out))
    return [
        EdaFilterSheetEntry(
            **out.model_dump(),
            entity_display_name=entity_name,
            example=_example(out, first_values=first_values),
        )
        for entity_name, out in described
    ]


def _sheet_for(
    ctx: RunContext[LeadDeps],
    study: EdaStudyDetail,
    dataset_id: str,
) -> list[EdaFilterSheetEntry]:
    """The sheet for one study, without repeating a vocabulary."""
    entries = _sheet_entries(study)
    domain = ctx.deps.state.domain
    if not domain.was_eda_sheet_shown(dataset_id):
        domain.mark_eda_sheet_shown(dataset_id)
        return entries
    return [
        entry.model_copy(update={"vocabulary": [], "vocabulary_note": _RE_SHEET_NOTE})
        if entry.vocabulary_total
        else entry
        for entry in entries
    ]


_SHEET_GUIDANCE = (
    "Copy the entityId, the variableId and the type from one entry, and send "
    "the whole array back in filters. The array replaces the subset, so "
    "include every filter that should apply. Then call preview_eda_subset."
)

_APPLIED_GUIDANCE = (
    "Call preview_eda_subset before you state any count. The filters can "
    "select nothing, and the service reports that as a plain zero."
)


async def set_eda_filters(
    ctx: RunContext[LeadDeps],
    *,
    dataset_id: str,
    filters: list[EdaFilter] | None = None,
) -> EdaFiltersResult | ToolReturn[EdaFiltersResult]:
    """Set the whole subset of the open EDA analysis, in two calls.

    Call this ONCE with no ``filters`` to receive ``decide``, the FILTER SHEET:
    every filterable variable of the study with its entity, its exact filter
    type, its vocabulary or its range, and one complete example filter object
    you can copy. Nothing is recorded by that call.

    Then call it AGAIN with ``filters`` set to the whole array you want. The
    array REPLACES the analysis's subset; it is not a patch, so send every
    filter that should apply. An empty array clears the subset and means the
    whole study.

    Writing the array, and every rule here is one the service will not enforce:

    - Copy ``entityId`` and ``variableId`` together from one sheet entry. A
      variableId is only valid on the entity that declares it.
    - Take ``type`` from the entry's ``filterType``, never from what the value
      looks like. A longitude variable is not a number variable, and a category
      variable holds no values at all.
    - For a string variable, every value must appear in the entry's
      ``vocabulary``. An invented value returns a count of zero with no error,
      so it looks like a real empty result.
    - For a date variable, append ``T00:00:00`` to every bound. The sheet
      already shows the bounds in that form. A bare ``2017-05-05`` is a server
      error.
    - The array is AND, always, across variables and across entities. To say
      "berghei OR falciparum", write ONE stringSet holding both. Two entries on
      one single-valued variable select nothing.
    - ``isMultiValued`` true means one record holds several values, so the
      per-value counts do not add up to the record count and two filters on
      that variable mean "has both".
    - A multiFilter targets a category whose ``filterType`` is ``multiFilter``
      and names its ``subFilterVariableIds``; its ``operation`` is ``union``
      for OR or ``intersect`` for AND. It is the only OR in the algebra.
    - Never put a range's ``min`` above its ``max``, and never set a
      longitudeRange's ``left`` equal to its ``right``. Both are accepted and
      both mean something other than what they look like.

    A rejected array comes back as a retry naming the offending value and the
    valid ones. Fix that value and re-send the whole array; do not ask for the
    sheet again.

    Args:
        ctx: Agent run context.
        dataset_id: The dataset of the open analysis.
        filters: The complete filter array, or omit it to read the sheet.
    """
    site_id = ctx.deps.runtime.site_id
    bound = await _bound_or_retry(ctx, dataset_id)
    if filters is None:
        _entry, study = await _study(site_id, dataset_id)
        return EdaFiltersResult(
            analysis_id=bound.analysis_id,
            dataset_id=dataset_id,
            decide=_sheet_for(ctx, study, dataset_id),
            guidance=_SHEET_GUIDANCE,
        )
    try:
        state = await apply_filters(
            site_id,
            conversation_id=ctx.deps.state.conversation_id,
            analysis_id=bound.analysis_id,
            dataset_id=dataset_id,
            filters=filters,
        )
    except SubsetRejectedError as exc:
        msg = (
            f"{' '.join(exc.messages)} The valid values are listed above; do not "
            f"request the sheet again."
        )
        raise ModelRetry(msg) from exc
    return ToolReturn(
        return_value=EdaFiltersResult(
            applied=True,
            analysis_id=bound.analysis_id,
            dataset_id=dataset_id,
            num_filters=state.num_filters,
            filter_summaries=state.filter_summaries,
            guidance=_APPLIED_GUIDANCE,
        ),
        metadata=[eda_analysis_state_chunk(state)],
    )


async def _bound_or_retry(
    ctx: RunContext[LeadDeps],
    dataset_id: str,
) -> ConversationAnalysisView:
    """The open analysis, or the retry that tells the model to open one."""
    bound = await bound_analysis(ctx)
    if bound is None:
        msg = (
            f"This conversation has no open EDA analysis. Call "
            f"open_eda_analysis on dataset {dataset_id!r} first."
        )
        raise ModelRetry(msg)
    if bound.dataset_id != dataset_id:
        msg = (
            f"The open analysis is {bound.analysis_id} on dataset "
            f"{bound.dataset_id!r}, and this call names {dataset_id!r}. Act on "
            f"the open analysis, or call open_eda_analysis to change it."
        )
        raise ModelRetry(msg)
    return bound


async def preview_eda_subset(
    ctx: RunContext[LeadDeps],
    *,
    entity_id: str,
    distribution_variable_id: str | None = None,
) -> ToolReturn[EdaSubsetPreviewResult]:
    """Count what the open analysis's filters select, on one entity.

    Call this after every set_eda_filters, before you tell the researcher a
    number and before you create a step. It returns the filtered count and the
    unfiltered count for that entity, so the effect of the subset is visible.

    ``entityId`` decides WHAT is counted, and it is independent of which
    entities the filters name: a filter on a child entity restricts the parent
    to parents that still have a surviving child, and a filter on a parent
    restricts the child to children under a surviving parent.

    Name ``distributionVariableId`` to also get that variable's histogram under
    the subset. That is what shows the researcher the shape of what is left.

    A count of zero is a real answer, not an error. Say which filter emptied
    the subset and offer one concrete way to widen it.

    Args:
        ctx: Agent run context.
        entity_id: The entity whose records are counted.
        distribution_variable_id: A variable on that entity to histogram.
    """
    site_id = ctx.deps.runtime.site_id
    bound = await bound_analysis(ctx)
    if bound is None:
        msg = (
            "This conversation has no open EDA analysis, so there is no subset "
            "to count. Call open_eda_analysis first."
        )
        raise ModelRetry(msg)
    analysis = await read_analysis(site_id, analysis_id=bound.analysis_id)
    filters = analysis.descriptor.subset.descriptor
    preview = await preview_subset(
        site_id,
        dataset_id=bound.dataset_id,
        entity_id=entity_id,
        filters=filters,
        distribution_variable_id=distribution_variable_id,
    )
    _entry, study = await _study(site_id, bound.dataset_id)
    variable = variable_at(study, entity_id, distribution_variable_id)
    statistics = (
        None if preview.distribution is None else preview.distribution.statistics
    )
    result = EdaSubsetPreviewResult(
        entity_id=preview.entity_id,
        entity_display_name=preview.entity_display_name,
        count=preview.count,
        unfiltered_count=preview.unfiltered_count,
        variable_id=distribution_variable_id,
        variable_display_name="" if variable is None else variable.display_name,
        is_multi_valued=variable is not None and variable.is_multi_valued,
        labels=[]
        if preview.distribution is None
        else [bin_.bin_label for bin_ in preview.distribution.histogram],
        values=[]
        if preview.distribution is None
        else [bin_.value for bin_ in preview.distribution.histogram],
        num_var_values=0 if statistics is None else statistics.num_var_values,
        num_missing_cases=0 if statistics is None else statistics.num_missing_cases,
        distribution_note=preview.distribution_note,
        guidance=_preview_guidance(
            preview_count=preview.count,
            unfiltered_count=preview.unfiltered_count,
            entity_display_name=preview.entity_display_name,
            has_filters=bool(filters),
            is_multi_valued=variable is not None and variable.is_multi_valued,
            num_missing_cases=0 if statistics is None else statistics.num_missing_cases,
        ),
    )
    chunk = eda_subset_preview_chunk(
        dataset_id=bound.dataset_id,
        analysis_id=bound.analysis_id,
        preview=preview,
        variable_id=distribution_variable_id,
        variable_display_name=result.variable_display_name,
        is_multi_valued=result.is_multi_valued,
    )
    return ToolReturn(return_value=result, metadata=[chunk])


def _preview_guidance(
    *,
    preview_count: int,
    unfiltered_count: int,
    entity_display_name: str,
    has_filters: bool,
    is_multi_valued: bool,
    num_missing_cases: int,
) -> str:
    """What this count means, and what it does not mean."""
    lines: list[str] = []
    if preview_count == 0:
        lines.append(
            f"This subset selects no records on {entity_display_name}. Name the "
            f"filter that emptied it and offer one way to widen it."
        )
    elif preview_count == unfiltered_count and has_filters:
        lines.append(
            "The subset is the whole entity, so these filters narrow nothing "
            "here. They may still narrow another entity."
        )
    if is_multi_valued:
        lines.append(
            "This variable holds several values per record, so the histogram's "
            "values sum above the record count. State which denominator any "
            "percentage uses."
        )
    if num_missing_cases:
        lines.append(
            f"{num_missing_cases} records on this entity have no value for that "
            f"variable."
        )
    return " ".join(lines)
