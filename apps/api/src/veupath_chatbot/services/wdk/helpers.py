"""Shared WDK helpers for record parsing, attribute inspection, and param merging.

These functions are used by experiment results, gene set, and workbench
endpoints to work with WDK record types, primary keys, and analysis
parameters. Previously duplicated across multiple router modules.
"""

from veupath_chatbot.platform.types import JSONObject, JSONValue

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
from veupath_chatbot.services.experiment.enrichment_params import (
    encode_vocab_params,
    extract_default_params,
)

_SORTABLE_WDK_TYPES = {"number", "float", "integer", "double"}

DETAIL_ATTRIBUTE_LIMIT = 50
"""Max attributes to request when fetching a single record detail.

WDK record types can have thousands of attributes (e.g. 3000+ expression
columns on transcript).  Requesting all would timeout.  The first ~50
``isInReport`` attributes cover core gene/record fields.
"""

_SCORE_ATTRIBUTE_KEYWORDS = {
    "score",
    "e_value",
    "evalue",
    "bit_score",
    "bitscore",
    "p_value",
    "pvalue",
    "fold_change",
    "log_fc",
    "confidence",
}


# ---------------------------------------------------------------------------
# Attribute classification
# ---------------------------------------------------------------------------


def is_sortable(attr_type: str | None) -> bool:
    """Return ``True`` if a WDK attribute type supports numeric sorting."""
    if not attr_type:
        return False
    return attr_type.lower() in _SORTABLE_WDK_TYPES


def is_suggested_score(name: str) -> bool:
    """Heuristic: flag well-known score attributes as suggested for ranking."""
    lower = name.lower()
    return any(kw in lower for kw in _SCORE_ATTRIBUTE_KEYWORDS)


# ---------------------------------------------------------------------------
# Primary key extraction
# ---------------------------------------------------------------------------


def extract_pk(record: JSONObject) -> str | None:
    """Extract primary key string from a WDK record.

    WDK records use ``"id": [{name, value}, ...]`` for the composite
    primary key.  Returns the first part's value, stripped.
    """
    pk = record.get("id")
    if isinstance(pk, list) and pk:
        first = pk[0]
        if isinstance(first, dict):
            val = first.get("value")
            if isinstance(val, str):
                return val.strip()
    return None


def extract_record_ids(
    records: object,
    *,
    preferred_key: str | None = None,
) -> list[str]:
    """Extract gene/record IDs from WDK standard report records.

    If *preferred_key* is given, looks it up in each record's
    ``attributes`` dict first; falls back to the primary-key array.

    Accepts ``object`` so callers do not need to narrow the type before
    calling (e.g. ``answer.get("records")`` may return ``None``).

    :param records: WDK answer records (expected ``list[dict]``).
    :param preferred_key: Attribute name to prefer over primary key.
    :returns: List of non-empty record IDs.
    """
    if not isinstance(records, list):
        return []
    ids: list[str] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        extracted: str | None = None

        if preferred_key:
            attrs = rec.get("attributes")
            if isinstance(attrs, dict):
                val = attrs.get(preferred_key)
                if isinstance(val, str) and val.strip():
                    extracted = val.strip()

        if extracted is None:
            extracted = extract_pk(rec)

        if extracted:
            ids.append(extracted)
    return ids


# ---------------------------------------------------------------------------
# Primary key ordering
# ---------------------------------------------------------------------------


def order_primary_key(
    pk_parts: list[JSONObject],
    pk_refs: list[str],
    pk_defaults: dict[str, str],
) -> list[JSONObject]:
    """Reorder and fill primary key parts to match WDK record class definition.

    WDK requires PK columns in the exact order defined by
    ``primaryKeyColumnRefs``.  Step reports may omit columns like
    ``project_id`` and may return them in a different order.

    :param pk_parts: Client-provided PK parts (``[{name, value}, ...]``).
    :param pk_refs: Column names in record-class order.
    :param pk_defaults: Default values for missing columns (e.g. ``project_id``).
    :returns: Ordered PK parts matching ``pk_refs``.
    """
    pk_by_name: dict[str, str] = {
        str(p.get("name", "")): str(p.get("value", ""))
        for p in pk_parts
        if isinstance(p, dict)
    }
    ordered: list[JSONObject] = []
    for col in pk_refs:
        if not isinstance(col, str):
            continue
        value = pk_by_name.get(col) or pk_defaults.get(col) or ""
        ordered.append({"name": col, "value": value})
    return ordered


# ---------------------------------------------------------------------------
# Attribute list building
# ---------------------------------------------------------------------------


def build_attribute_list(attrs_raw: object) -> list[JSONObject]:
    """Build a normalized attribute list from WDK record type info.

    Handles both dict (``attributesMap``) and list (expanded) formats.
    Each entry includes: ``name``, ``displayName``, ``help``, ``type``,
    ``isDisplayable``, ``isSortable``, ``isSuggested``.

    This consolidates the 40+ line if/elif blocks previously copy-pasted
    in both ``get_experiment_attributes`` and ``get_gene_set_attributes``.

    :param attrs_raw: Raw attributes value from the record type info.
    :returns: Normalized attribute list.
    """
    attributes: list[JSONObject] = []

    if isinstance(attrs_raw, dict):
        for name, meta in attrs_raw.items():
            if isinstance(meta, dict):
                attr = _build_single_attribute(str(name), meta, name_fallback=str(name))
                attributes.append(attr)
    elif isinstance(attrs_raw, list):
        for meta in attrs_raw:
            if isinstance(meta, dict):
                attr_name = str(meta.get("name", ""))
                attr = _build_single_attribute(attr_name, meta, name_fallback=attr_name)
                attributes.append(attr)

    return attributes


def _build_single_attribute(
    name: str,
    meta: JSONObject,
    *,
    name_fallback: str,
) -> JSONObject:
    """Build a single normalized attribute dict from WDK metadata."""
    raw_type = meta.get("type")
    attr_type = str(raw_type) if isinstance(raw_type, str) else None
    sortable = is_sortable(attr_type)
    return {
        "name": name,
        "displayName": meta.get("displayName", name_fallback),
        "help": meta.get("help"),
        "type": attr_type,
        "isDisplayable": meta.get("isDisplayable", True),
        "isSortable": sortable,
        "isSuggested": sortable and is_suggested_score(name),
    }


# ---------------------------------------------------------------------------
# Detail attribute extraction
# ---------------------------------------------------------------------------


def extract_detail_attributes(
    attrs_raw: object,
) -> tuple[list[str], dict[str, str]]:
    """Extract attribute names and display names for the record detail view.

    Filters to attributes with ``isInReport=True`` (skipping composite
    overview fields) and caps at :data:`DETAIL_ATTRIBUTE_LIMIT` so that
    record types with thousands of attributes don't timeout WDK.

    Handles both dict (``attributesMap``) and list (expanded) formats.

    :returns: ``(attribute_names, display_name_map)``
    """
    items: list[tuple[str, JSONObject]] = []
    if isinstance(attrs_raw, dict):
        items = [
            (str(name), meta)
            for name, meta in attrs_raw.items()
            if isinstance(meta, dict)
        ]
    elif isinstance(attrs_raw, list):
        items = [
            (str(meta.get("name", "")), meta)
            for meta in attrs_raw
            if isinstance(meta, dict)
        ]

    names: list[str] = []
    display_names: dict[str, str] = {}
    for name, meta in items:
        if not meta.get("isInReport", meta.get("isDisplayable", False)):
            continue
        names.append(name)
        dn = meta.get("displayName")
        display_names[name] = str(dn) if isinstance(dn, str) else name
        if len(names) >= DETAIL_ATTRIBUTE_LIMIT:
            break

    return names, display_names


# ---------------------------------------------------------------------------
# Analysis parameter merging
# ---------------------------------------------------------------------------


def merge_analysis_params(
    form_meta: JSONValue,
    user_params: JSONObject,
) -> JSONObject:
    """Merge WDK form defaults with user-supplied parameters.

    Always extracts defaults from the WDK form metadata and layers
    user-supplied parameters on top so that required fields are never
    missing (which would cause WDK 422 errors).

    After merging, vocabulary params (``single-pick-vocabulary``,
    ``multi-pick-vocabulary``) are re-encoded as JSON arrays using
    the form metadata.  This ensures that user-supplied plain strings
    don't bypass the encoding required by
    ``AbstractEnumParam.convertToTerms()``.
    """
    defaults = extract_default_params(form_meta)
    merged: JSONObject = {**defaults, **user_params}
    return encode_vocab_params(merged, form_meta)
