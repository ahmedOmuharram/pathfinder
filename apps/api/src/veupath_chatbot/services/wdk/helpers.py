"""Shared WDK helpers for record parsing, attribute inspection, and param merging.

These functions are used by experiment results, gene set, and workbench
endpoints to work with WDK record types, primary keys, and analysis
parameters. Previously duplicated across multiple router modules.
"""

from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKAttributeField,
    WDKRecordInstance,
)
from veupath_chatbot.platform.types import JSONObject, JSONValue

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
from veupath_chatbot.services.enrichment.params import (
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


def extract_pk(record: WDKRecordInstance) -> str | None:
    """Extract primary key string from a WDK record.

    WDK records use ``id: [{name, value}, ...]`` for the composite
    primary key.  Returns the first part's value, stripped.
    """
    if not record.id:
        return None
    first = record.id[0]
    val = first.get("value", "")
    return val.strip() or None


def extract_record_ids(
    records: list[WDKRecordInstance],
    *,
    preferred_key: str | None = None,
) -> list[str]:
    """Extract gene/record IDs from WDK standard report records.

    If *preferred_key* is given, looks it up in each record's
    ``attributes`` dict first; falls back to the primary-key array.
    """
    ids: list[str] = []
    for rec in records:
        extracted: str | None = None
        if preferred_key:
            val = rec.attributes.get(preferred_key)
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
    pk_parts: list[dict[str, str]],
    pk_refs: list[str],
    pk_defaults: dict[str, str],
) -> list[dict[str, str]]:
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
        p.get("name", ""): p.get("value", "") for p in pk_parts
    }
    ordered: list[dict[str, str]] = []
    for col in pk_refs:
        value = pk_by_name.get(col) or pk_defaults.get(col) or ""
        ordered.append({"name": col, "value": value})
    return ordered


# ---------------------------------------------------------------------------
# Attribute list building
# ---------------------------------------------------------------------------


def build_attribute_list(attrs: list[WDKAttributeField]) -> list[JSONValue]:
    """Build a normalized attribute list from WDK attribute fields.

    Each entry includes: ``name``, ``displayName``, ``help``, ``type``,
    ``isDisplayable``, ``isSortable``, ``isSuggested``.
    """
    attributes: list[JSONValue] = []
    for field in attrs:
        sortable = is_sortable(field.type)
        attributes.append(
            {
                "name": field.name,
                "displayName": field.display_name or field.name,
                "help": field.help,
                "type": field.type,
                "isDisplayable": field.is_displayable,
                "isSortable": sortable,
                "isSuggested": sortable and is_suggested_score(field.name),
            }
        )
    return attributes


# ---------------------------------------------------------------------------
# Detail attribute extraction
# ---------------------------------------------------------------------------


def extract_detail_attributes(
    attrs: list[WDKAttributeField],
) -> tuple[list[str], dict[str, str]]:
    """Extract attribute names and display names for the record detail view.

    Uses ``is_in_report`` as primary signal; falls back to ``is_displayable``
    only when ``is_in_report`` is False (preserving original WDK semantics).
    Caps at :data:`DETAIL_ATTRIBUTE_LIMIT`.
    """
    names: list[str] = []
    display_names: dict[str, str] = {}
    for field in attrs:
        if not field.is_in_report and not field.is_displayable:
            continue
        names.append(field.name)
        display_names[field.name] = field.display_name or field.name
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
