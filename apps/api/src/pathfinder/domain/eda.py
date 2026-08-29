"""Pure predicates over a fetched EDA study tree and a filter array.

The shapes are structural, so this module imports no other layer.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

VEUPATHDB_GENE_ID = "VEUPATHDB_GENE_ID"

GENE_EXPRESSION_VALUE_IDS = frozenset(
    {
        "SEQUENCE_READ_COUNT",
        "SEQUENCE_READ_COUNT_SENSE",
        "SEQUENCE_READ_COUNT_ANTISENSE",
        "NORMALIZED_EXPRESSION",
        "NORMALIZED_INTENSITY",
    }
)

DIFFERENTIAL_EXPRESSION_METHODS = frozenset({"DESeq", "limma"})

_CATEGORY_TYPE = "category"
_MULTIFILTER_DISPLAY = "multifilter"
_MULTIFILTER_OPERATIONS = frozenset({"intersect", "union"})
_DATE_TIME_MARKER = "T"
_BARE_DATE_EXAMPLE = "2017-05-05T00:00:00"
_DEGENERATE_LONGITUDE = 1e-8
_LISTED_LIMIT = 20

_TYPES_FOR_FILTER: dict[str, frozenset[str]] = {
    "stringSet": frozenset({"string"}),
    "numberSet": frozenset({"number", "integer"}),
    "dateSet": frozenset({"date"}),
    "numberRange": frozenset({"number", "integer"}),
    "dateRange": frozenset({"date"}),
    "longitudeRange": frozenset({"longitude"}),
    "multiFilter": frozenset({_CATEGORY_TYPE}),
}

DeclaredRanges = Mapping[tuple[str, str], tuple[float, float]]


class VariableFacts(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def type(self) -> str: ...
    @property
    def display_name(self) -> str: ...
    @property
    def display_type(self) -> str: ...
    @property
    def parent_id(self) -> str | None: ...


@runtime_checkable
class ValueVariableFacts(VariableFacts, Protocol):
    """A variable that carries data. A ``category`` node carries none."""

    @property
    def vocabulary(self) -> Sequence[str] | None: ...
    @property
    def is_multi_valued(self) -> bool: ...


class EntityFacts(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def display_name(self) -> str: ...
    @property
    def variables(self) -> Sequence[VariableFacts]: ...
    @property
    def children(self) -> Sequence[EntityFacts]: ...


class StudyFacts(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def root_entity(self) -> EntityFacts: ...


@dataclass(frozen=True, slots=True)
class GeneEntityResult:
    """The entity carrying the reserved gene id, or why there is not one."""

    entity_id: str | None
    error: str | None


def walk_entities(root: EntityFacts) -> Iterator[EntityFacts]:
    """Yield the root and then every descendant, depth first."""
    yield root
    for child in root.children:
        yield from walk_entities(child)


def entity_by_id(root: EntityFacts, entity_id: str) -> EntityFacts | None:
    for entity in walk_entities(root):
        if entity.id == entity_id:
            return entity
    return None


def variable_by_id(entity: EntityFacts, variable_id: str) -> VariableFacts | None:
    for variable in entity.variables:
        if variable.id == variable_id:
            return variable
    return None


def ancestor_entity_ids(root: EntityFacts, entity_id: str) -> frozenset[str]:
    """Every entity strictly above ``entity_id``.

    Empty both when the id names the root and when the tree does not carry it.
    """
    return _ancestors(root, entity_id, ())


def _ancestors(
    entity: EntityFacts,
    entity_id: str,
    above: tuple[str, ...],
) -> frozenset[str]:
    if entity.id == entity_id:
        return frozenset(above)
    for child in entity.children:
        found = _ancestors(child, entity_id, (*above, entity.id))
        if found:
            return found
    return frozenset()


def find_gene_entity(study: StudyFacts) -> GeneEntityResult:
    """The study must carry exactly one ``VEUPATHDB_GENE_ID`` to export genes."""
    holders = [
        entity.id
        for entity in walk_entities(study.root_entity)
        if variable_by_id(entity, VEUPATHDB_GENE_ID) is not None
    ]
    if not holders:
        return GeneEntityResult(
            entity_id=None,
            error=(
                f"Study {study.id} carries no {VEUPATHDB_GENE_ID} variable, so it "
                f"cannot export a gene list to a strategy step."
            ),
        )
    if len(holders) > 1:
        return GeneEntityResult(
            entity_id=None,
            error=(
                f"Study {study.id} carries {VEUPATHDB_GENE_ID} on more than one "
                f"entity ({', '.join(sorted(holders))}), and the gene bridge "
                f"requires exactly one."
            ),
        )
    return GeneEntityResult(entity_id=holders[0], error=None)


class SubFilterFacts(Protocol):
    @property
    def variable_id(self) -> str: ...
    @property
    def string_set(self) -> Sequence[str]: ...


class FilterFacts(Protocol):
    @property
    def entity_id(self) -> str: ...
    @property
    def variable_id(self) -> str: ...
    @property
    def type(self) -> str: ...


@runtime_checkable
class StringSetFacts(FilterFacts, Protocol):
    @property
    def string_set(self) -> Sequence[str]: ...


@runtime_checkable
class NumberSetFacts(FilterFacts, Protocol):
    @property
    def number_set(self) -> Sequence[float]: ...


@runtime_checkable
class DateSetFacts(FilterFacts, Protocol):
    @property
    def date_set(self) -> Sequence[str]: ...


@runtime_checkable
class RangeBoundsFacts(FilterFacts, Protocol):
    @property
    def min(self) -> float | str | None: ...
    @property
    def max(self) -> float | str | None: ...


@runtime_checkable
class LongitudeBoundsFacts(FilterFacts, Protocol):
    @property
    def left(self) -> float | None: ...
    @property
    def right(self) -> float | None: ...


@runtime_checkable
class MultiFilterFacts(FilterFacts, Protocol):
    @property
    def operation(self) -> str: ...
    @property
    def sub_filters(self) -> Sequence[SubFilterFacts]: ...


@dataclass(frozen=True, slots=True)
class _Site:
    """One filter with the entity and the variable it resolved to."""

    entry: FilterFacts
    entity: EntityFacts
    variable: VariableFacts
    declared_ranges: DeclaredRanges


def _listed(values: Iterable[object]) -> str:
    items = [str(value) for value in values]
    if len(items) <= _LISTED_LIMIT:
        return ", ".join(items)
    kept = ", ".join(items[:_LISTED_LIMIT])
    return f"{kept} and {len(items) - _LISTED_LIMIT} more"


def _vocabulary(variable: VariableFacts) -> Sequence[str] | None:
    match variable:
        case ValueVariableFacts():
            return variable.vocabulary
        case _:
            return None


def _is_multi_valued(variable: VariableFacts) -> bool:
    match variable:
        case ValueVariableFacts():
            return variable.is_multi_valued
        case _:
            return False


def _strings(entry: FilterFacts) -> Sequence[str]:
    match entry:
        case StringSetFacts():
            return entry.string_set
        case _:
            return ()


def _numbers(entry: FilterFacts) -> Sequence[float]:
    match entry:
        case NumberSetFacts():
            return entry.number_set
        case _:
            return ()


def _dates(entry: FilterFacts) -> Sequence[str]:
    match entry:
        case DateSetFacts():
            return entry.date_set
        case _:
            return ()


def _bounds(entry: FilterFacts) -> tuple[float | str | None, float | str | None]:
    match entry:
        case RangeBoundsFacts():
            return entry.min, entry.max
        case _:
            return None, None


def _longitude_bounds(entry: FilterFacts) -> tuple[float | None, float | None]:
    match entry:
        case LongitudeBoundsFacts():
            return entry.left, entry.right
        case _:
            return None, None


def _multi_filter(entry: FilterFacts) -> tuple[str, Sequence[SubFilterFacts]]:
    match entry:
        case MultiFilterFacts():
            return entry.operation, entry.sub_filters
        case _:
            return "", ()


def _as_number(value: float | str | None) -> float | None:
    match value:
        case int() | float():
            return float(value)
        case _:
            return None


def _as_text(value: float | str | None) -> str | None:
    match value:
        case str():
            return value
        case _:
            return None


def _at(site: _Site) -> str:
    return (
        f"Filter {site.entry.type} on variable {site.variable.id} of entity "
        f"{site.entity.id}"
    )


def _wrong_variable_type(site: _Site) -> list[str]:
    allowed = _TYPES_FOR_FILTER[site.entry.type]
    if site.variable.type in allowed:
        return []
    return [
        f"{_at(site)} is refused: the variable type is {site.variable.type}, and "
        f"{site.entry.type} applies to a variable of type {_listed(sorted(allowed))}."
    ]


def _string_set_errors(site: _Site) -> list[str]:
    wrong = _wrong_variable_type(site)
    if wrong:
        return wrong
    values = _strings(site.entry)
    if not values:
        return [
            f"{_at(site)} carries no members, and the service refuses an empty set."
        ]
    vocabulary = _vocabulary(site.variable)
    if vocabulary is None:
        return []
    unknown = [value for value in values if value not in vocabulary]
    if not unknown:
        return []
    return [
        f"{_at(site)} names {_listed(unknown)}, which the vocabulary does not "
        f"carry. The vocabulary is {_listed(vocabulary)}. An unknown value returns "
        f"count 0 rather than an error."
    ]


def _number_set_errors(site: _Site) -> list[str]:
    wrong = _wrong_variable_type(site)
    if wrong:
        return wrong
    values = _numbers(site.entry)
    if not values:
        return [
            f"{_at(site)} carries no members, and the service refuses an empty set."
        ]
    if site.variable.type != "integer":
        return []
    fractional = [value for value in values if not float(value).is_integer()]
    if not fractional:
        return []
    return [
        f"{_at(site)} names {_listed(fractional)}, and the variable is an integer, "
        f"so every member must be whole."
    ]


def _date_set_errors(site: _Site) -> list[str]:
    wrong = _wrong_variable_type(site)
    if wrong:
        return wrong
    values = _dates(site.entry)
    if not values:
        return [
            f"{_at(site)} carries no members, and the service refuses an empty set."
        ]
    bare = [value for value in values if _DATE_TIME_MARKER not in value]
    if not bare:
        return []
    return [
        f"{_at(site)} names {_listed(bare)} without a time part. Write every member "
        f"as YYYY-MM-DDTHH:mm:ss, for example {bare[0]}T00:00:00."
    ]


def _number_range_errors(site: _Site) -> list[str]:
    wrong = _wrong_variable_type(site)
    if wrong:
        return wrong
    low_bound, high_bound = _bounds(site.entry)
    low = _as_number(low_bound)
    high = _as_number(high_bound)
    if low is None or high is None:
        return [f"{_at(site)} needs a numeric min and a numeric max."]
    if low > high:
        return [
            f"{_at(site)} has min {low} above max {high}, which returns count 0 "
            f"rather than an error."
        ]
    return _outside_declared_range(site, low, high)


def _outside_declared_range(site: _Site, low: float, high: float) -> list[str]:
    key = (site.entity.id, site.variable.id)
    if key not in site.declared_ranges:
        return []
    range_min, range_max = site.declared_ranges[key]
    outside = [bound for bound in (low, high) if bound < range_min or bound > range_max]
    if not outside:
        return []
    return [
        f"{_at(site)} has {_listed(outside)} outside the declared range "
        f"{range_min} to {range_max}."
    ]


def _date_range_errors(site: _Site) -> list[str]:
    wrong = _wrong_variable_type(site)
    if wrong:
        return wrong
    low_bound, high_bound = _bounds(site.entry)
    low = _as_text(low_bound)
    high = _as_text(high_bound)
    if low is None or high is None:
        return [
            f"{_at(site)} needs a min and a max written as YYYY-MM-DDTHH:mm:ss, "
            f"for example {_BARE_DATE_EXAMPLE}."
        ]
    bare = [
        f"{_at(site)} has the bound {bound} without a time part. Write it as "
        f"{bound}T00:00:00."
        for bound in (low, high)
        if _DATE_TIME_MARKER not in bound
    ]
    if bare:
        return bare
    if low > high:
        return [
            f"{_at(site)} has min {low} above max {high}, which returns count 0 "
            f"rather than an error."
        ]
    return []


def _longitude_range_errors(site: _Site) -> list[str]:
    wrong = _wrong_variable_type(site)
    if wrong:
        return wrong
    left, right = _longitude_bounds(site.entry)
    if left is None or right is None:
        return [f"{_at(site)} needs a numeric left and a numeric right."]
    if abs(left - right) >= _DEGENERATE_LONGITUDE:
        return []
    return [
        f"{_at(site)} has left {left} equal to right {right} within "
        f"{_DEGENERATE_LONGITUDE}, and the service reads an equal pair as a no-op "
        f"that keeps every row."
    ]


def _multi_filter_errors(site: _Site) -> list[str]:
    wrong = _wrong_multifilter_target(site)
    if wrong:
        return wrong
    operation, sub_filters = _multi_filter(site.entry)
    if not sub_filters:
        return [f"{_at(site)} carries no subFilters, which the service refuses."]
    if operation not in _MULTIFILTER_OPERATIONS:
        return [
            f"{_at(site)} names operation {operation}, and the service accepts "
            f"{_listed(sorted(_MULTIFILTER_OPERATIONS))}."
        ]
    return [error for sub in sub_filters for error in _sub_filter_errors(site, sub)]


def _wrong_multifilter_target(site: _Site) -> list[str]:
    is_category = site.variable.type in _TYPES_FOR_FILTER["multiFilter"]
    if is_category and site.variable.display_type == _MULTIFILTER_DISPLAY:
        return []
    return [
        f"{_at(site)} is refused: the target must be a category variable whose "
        f"displayType is {_MULTIFILTER_DISPLAY}, and this variable is type "
        f"{site.variable.type} with displayType {site.variable.display_type}."
    ]


def _sub_filter_errors(site: _Site, sub: SubFilterFacts) -> list[str]:
    child = variable_by_id(site.entity, sub.variable_id)
    if child is None or child.parent_id != site.variable.id:
        children = [
            variable.id
            for variable in site.entity.variables
            if variable.parent_id == site.variable.id
        ]
        return [
            f"{_at(site)} names sub-filter variable {sub.variable_id}, which is not "
            f"a child of that category. Its children are {_listed(children)}."
        ]
    if not sub.string_set:
        return [
            f"{_at(site)} gives sub-filter variable {sub.variable_id} no members, "
            f"and the service refuses an empty set."
        ]
    vocabulary = _vocabulary(child)
    if vocabulary is None:
        return []
    unknown = [value for value in sub.string_set if value not in vocabulary]
    if not unknown:
        return []
    return [
        f"{_at(site)} gives sub-filter variable {sub.variable_id} the values "
        f"{_listed(unknown)}, which its vocabulary does not carry. The vocabulary "
        f"is {_listed(vocabulary)}."
    ]


_CHECKS: dict[str, Callable[[_Site], list[str]]] = {
    "stringSet": _string_set_errors,
    "numberSet": _number_set_errors,
    "dateSet": _date_set_errors,
    "numberRange": _number_range_errors,
    "dateRange": _date_range_errors,
    "longitudeRange": _longitude_range_errors,
    "multiFilter": _multi_filter_errors,
}


def validate_filters(
    study: StudyFacts,
    filters: Sequence[FilterFacts],
    declared_ranges: DeclaredRanges | None = None,
) -> list[str]:
    """Every reason this filter array will not mean what it says.

    An empty list means the service will answer about the subset the author
    described. The service accepts several of these and answers count 0.
    """
    errors: list[str] = []
    for entry in filters:
        errors.extend(_one_filter(study, entry, declared_ranges or {}))
    errors.extend(_repeated_single_valued(study, filters))
    return errors


def _one_filter(
    study: StudyFacts,
    entry: FilterFacts,
    declared_ranges: DeclaredRanges,
) -> list[str]:
    entity = entity_by_id(study.root_entity, entry.entity_id)
    if entity is None:
        known = [known.id for known in walk_entities(study.root_entity)]
        return [
            f"Filter {entry.type} names entity {entry.entity_id}, which study "
            f"{study.id} does not carry. Its entities are {_listed(known)}."
        ]
    variable = variable_by_id(entity, entry.variable_id)
    if variable is None:
        return [
            f"Filter {entry.type} names variable {entry.variable_id}, which entity "
            f"{entity.id} does not declare. A variable id is only valid on the "
            f"entity that declares it."
        ]
    if entry.type not in _CHECKS:
        return [
            f"Filter type {entry.type} is not one the service deserializes. The "
            f"types are {_listed(sorted(_CHECKS))}."
        ]
    return _CHECKS[entry.type](_Site(entry, entity, variable, declared_ranges))


def _repeated_single_valued(
    study: StudyFacts,
    filters: Sequence[FilterFacts],
) -> list[str]:
    sets: dict[tuple[str, str], list[frozenset[str]]] = {}
    for entry in filters:
        variable = _single_valued_target(study, entry)
        if variable is None:
            continue
        members = frozenset(_strings(entry))
        if members:
            sets.setdefault((entry.entity_id, variable.id), []).append(members)
    errors: list[str] = []
    for (entity_id, variable_id), grouped in sets.items():
        if len(grouped) == 1 or frozenset.intersection(*grouped):
            continue
        written = "; ".join(f"({_listed(sorted(one))})" for one in grouped)
        errors.append(
            f"Filters on variable {variable_id} of entity {entity_id} name the "
            f"disjoint sets {written}, and the variable holds one value per row, "
            f"so the subset is empty. Express OR with one filter that holds "
            f"several members, never with two array entries."
        )
    return errors


def _single_valued_target(
    study: StudyFacts,
    entry: FilterFacts,
) -> VariableFacts | None:
    if entry.type != "stringSet":
        return None
    entity = entity_by_id(study.root_entity, entry.entity_id)
    if entity is None:
        return None
    variable = variable_by_id(entity, entry.variable_id)
    if variable is None or _is_multi_valued(variable):
        return None
    return variable


class VariableSpecFacts(Protocol):
    @property
    def entity_id(self) -> str: ...
    @property
    def variable_id(self) -> str: ...


class LabeledRangeFacts(Protocol):
    @property
    def label(self) -> str: ...


class ComparatorFacts(Protocol):
    @property
    def variable(self) -> VariableSpecFacts: ...
    @property
    def group_a(self) -> Sequence[LabeledRangeFacts]: ...
    @property
    def group_b(self) -> Sequence[LabeledRangeFacts]: ...


class ComputeConfigFacts(Protocol):
    @property
    def identifier_variable(self) -> VariableSpecFacts: ...
    @property
    def value_variable(self) -> VariableSpecFacts: ...
    @property
    def comparator(self) -> ComparatorFacts: ...
    @property
    def differential_expression_method(self) -> str: ...


def validate_compute_config(
    study: StudyFacts,
    config: ComputeConfigFacts,
) -> list[str]:
    """Every reason this differentialexpression config will fail or mislead.

    Submission validates schema shape and study permission only, so a bad
    entity pairing or an out-of-vocabulary label reaches a failed job.
    """
    comparator_variable = _variable_at(study, config.comparator.variable)
    if comparator_variable is None:
        return _unresolved_specs(study, config)
    unresolved = _unresolved_specs(study, config)
    if unresolved:
        return unresolved
    return [
        *_pairing_errors(config),
        *_comparator_errors(study, config, comparator_variable),
        *_method_errors(config),
    ]


def _variable_at(study: StudyFacts, spec: VariableSpecFacts) -> VariableFacts | None:
    entity = entity_by_id(study.root_entity, spec.entity_id)
    if entity is None:
        return None
    return variable_by_id(entity, spec.variable_id)


def _unresolved_specs(study: StudyFacts, config: ComputeConfigFacts) -> list[str]:
    named = (
        ("identifierVariable", config.identifier_variable),
        ("valueVariable", config.value_variable),
        ("comparator.variable", config.comparator.variable),
    )
    return [
        _unresolved_message(study, name, spec)
        for name, spec in named
        if _variable_at(study, spec) is None
    ]


def _unresolved_message(
    study: StudyFacts,
    name: str,
    spec: VariableSpecFacts,
) -> str:
    entity = entity_by_id(study.root_entity, spec.entity_id)
    if entity is None:
        known = [entry.id for entry in walk_entities(study.root_entity)]
        return (
            f"{name} names entity {spec.entity_id}, which study {study.id} does not "
            f"carry. Its entities are {_listed(known)}."
        )
    return (
        f"{name} names variable {spec.variable_id}, which entity {entity.id} does "
        f"not declare."
    )


def _pairing_errors(config: ComputeConfigFacts) -> list[str]:
    identifier = config.identifier_variable
    value = config.value_variable
    if identifier.entity_id != value.entity_id:
        return [
            f"identifierVariable is on entity {identifier.entity_id} and "
            f"valueVariable is on entity {value.entity_id}. The plugin needs both "
            f"on the same entity."
        ]
    errors: list[str] = []
    if identifier.variable_id != VEUPATHDB_GENE_ID:
        errors.append(
            f"identifierVariable names {identifier.variable_id}, and "
            f"differentialexpression accepts only {VEUPATHDB_GENE_ID}."
        )
    if value.variable_id not in GENE_EXPRESSION_VALUE_IDS:
        errors.append(
            f"valueVariable names {value.variable_id}, and differentialexpression "
            f"accepts {_listed(sorted(GENE_EXPRESSION_VALUE_IDS))}."
        )
    return errors


def _comparator_errors(
    study: StudyFacts,
    config: ComputeConfigFacts,
    comparator_variable: VariableFacts,
) -> list[str]:
    comparator = config.comparator
    errors = _comparator_entity_errors(study, config)
    group_a = [entry.label for entry in comparator.group_a]
    group_b = [entry.label for entry in comparator.group_b]
    for name, labels in (("groupA", group_a), ("groupB", group_b)):
        if not labels:
            errors.append(
                f"comparator {name} is empty, and the plugin needs a label in each "
                f"group to name the two sides of the comparison."
            )
    shared = sorted(set(group_a) & set(group_b))
    if shared:
        errors.append(
            f"comparator names {_listed(shared)} in both groups, and a sample "
            f"cannot be its own control."
        )
    if comparator_variable.type == _CATEGORY_TYPE:
        errors.append(
            f"comparator.variable names {comparator_variable.id}, which is a "
            f"{_CATEGORY_TYPE} variable. A category groups other variables and "
            f"holds no values, so no label can name a side of the comparison."
        )
    vocabulary = _vocabulary(comparator_variable)
    if vocabulary is None:
        return errors
    unknown = [label for label in group_a + group_b if label not in vocabulary]
    if unknown:
        errors.append(
            f"comparator names the labels {_listed(unknown)}, which the vocabulary "
            f"of {comparator_variable.id} does not carry. The vocabulary is "
            f"{_listed(vocabulary)}."
        )
    return errors


def _comparator_entity_errors(
    study: StudyFacts,
    config: ComputeConfigFacts,
) -> list[str]:
    identifier_entity = config.identifier_variable.entity_id
    ancestors = ancestor_entity_ids(study.root_entity, identifier_entity)
    comparator_entity = config.comparator.variable.entity_id
    if comparator_entity in ancestors:
        return []
    return [
        f"comparator.variable is on entity {comparator_entity}, and the plugin "
        f"reads the comparator from an ancestor entity of {identifier_entity}. "
        f"The ancestor entities are {_listed(sorted(ancestors))}."
    ]


def _method_errors(config: ComputeConfigFacts) -> list[str]:
    method = config.differential_expression_method
    if method in DIFFERENTIAL_EXPRESSION_METHODS:
        return []
    return [
        f"differentialExpressionMethod is {method}, and the service accepts "
        f"{_listed(sorted(DIFFERENTIAL_EXPRESSION_METHODS))}."
    ]
