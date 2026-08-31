"""The EDA filter sheet: every filterable variable, with one example to copy."""

from __future__ import annotations

from assistant_core.platform.types import JSONObject
from pydantic import JsonValue

from pathfinder.ai.graph.state import StrategyDomainState
from pathfinder.ai.tools.standalone._eda_models import EdaFilterSheetEntry
from pathfinder.domain.eda_study import walk_entities
from pathfinder.services.eda import EdaStudyDetail
from pathfinder.services.eda.description import (
    EdaVariableOut,
    children_of,
    entity_facts,
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


def sheet_for(
    domain: StrategyDomainState,
    study: EdaStudyDetail,
    dataset_id: str,
) -> list[EdaFilterSheetEntry]:
    """The sheet for one study, without repeating a vocabulary."""
    entries = _sheet_entries(study)
    if not domain.was_eda_sheet_shown(dataset_id):
        domain.mark_eda_sheet_shown(dataset_id)
        return entries
    return [
        entry.model_copy(update={"vocabulary": [], "vocabulary_note": _RE_SHEET_NOTE})
        if entry.vocabulary_total
        else entry
        for entry in entries
    ]
