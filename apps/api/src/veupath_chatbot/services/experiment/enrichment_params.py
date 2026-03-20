"""WDK enrichment parameter encoding helpers.

Pure module (no I/O). Handles vocabulary parameter encoding as JSON
arrays per WDK's ``AbstractEnumParam.convertToTerms()`` requirements,
and extraction of default parameter values from WDK form metadata.
"""

import json

from veupath_chatbot.domain.parameters.specs import unwrap_search_data
from veupath_chatbot.platform.types import JSONObject, JSONValue

# WDK ``EnumParamFormatter.getParamType()`` emits these JSON type strings
# for params extending ``AbstractEnumParam`` (``EnumParam``, ``FlatVocabParam``).
# These are the only param types whose stable values must be JSON arrays
# (via ``AbstractEnumParam.convertToTerms()`` → ``new JSONArray(stableValue)``).
# See ``org.gusdb.wdk.core.api.JsonKeys`` for the constant names
# (SINGLE_VOCAB_PARAM_TYPE and MULTI_VOCAB_PARAM_TYPE).
WDK_VOCAB_PARAM_TYPES = frozenset({"single-pick-vocabulary", "multi-pick-vocabulary"})


def _extract_param_specs(form_meta: JSONValue) -> list[JSONObject]:
    """Extract the parameters list from WDK form metadata.

    Handles the ``searchData`` wrapper that WDK uses for analysis-type
    endpoints and unwraps it if present.
    """
    if not isinstance(form_meta, dict):
        return []
    container = unwrap_search_data(form_meta) or form_meta
    params_raw = container.get("parameters")
    if not isinstance(params_raw, list):
        return []
    return [p for p in params_raw if isinstance(p, dict)]


def extract_vocab_values(form_meta: JSONValue, param_name: str) -> list[str]:
    """Extract the allowed vocabulary values for a parameter from form metadata.

    WDK vocabulary params include a ``vocabulary`` field — a list of
    ``[value, display, null]`` triples.  Returns the list of ``value``
    strings (first element of each triple).

    Returns an empty list if the parameter is not found or has no vocabulary.
    """
    for p in _extract_param_specs(form_meta):
        if p.get("name") != param_name:
            continue
        vocab = p.get("vocabulary")
        if not isinstance(vocab, list):
            return []
        return [str(entry[0]) for entry in vocab if isinstance(entry, list) and entry]
    return []


def _build_param_type_map(form_meta: JSONValue) -> dict[str, str]:
    """Build a ``{param_name: wdk_type}`` map from form metadata.

    Used by :func:`encode_vocab_params` to know which params need
    JSON array encoding after a merge with user-supplied values.
    """
    type_map: dict[str, str] = {}
    for p in _extract_param_specs(form_meta):
        name = p.get("name")
        ptype = p.get("type")
        if isinstance(name, str) and name and isinstance(ptype, str):
            type_map[name] = ptype
    return type_map


def encode_vocab_value(value: str) -> str:
    """Ensure a vocabulary param value is a JSON array string.

    ``AbstractEnumParam.convertToTerms()`` calls
    ``new JSONArray(stableValue)`` — plain strings cause a parse error.
    Multi-pick values already arrive as JSON arrays from WDK; single-pick
    values arrive as plain strings and must be wrapped.
    """
    if value.startswith("["):
        try:
            json.loads(value)
        except json.JSONDecodeError, ValueError:
            pass
        else:
            return value
    return json.dumps([value])


def encode_vocab_params(
    params: JSONObject,
    form_meta: JSONValue,
) -> JSONObject:
    """Encode vocabulary param values as JSON arrays using form metadata.

    WDK's ``AbstractEnumParam.convertToTerms()`` requires all
    ``single-pick-vocabulary`` and ``multi-pick-vocabulary`` param values
    to be JSON-encoded arrays.  This function ensures that encoding is
    applied **after** merging defaults with user params, so user-supplied
    plain strings don't bypass the encoding.

    Params whose type is not in the form metadata, or whose type is not
    a vocabulary type, are returned unchanged.
    """
    type_map = _build_param_type_map(form_meta)
    if not type_map:
        return params

    encoded: JSONObject = {}
    for name, value in params.items():
        ptype = type_map.get(name, "") if isinstance(name, str) else ""
        if ptype in WDK_VOCAB_PARAM_TYPES and isinstance(value, str):
            encoded[name] = encode_vocab_value(value)
        else:
            encoded[name] = value
    return encoded


def extract_default_params(form_meta: JSONValue) -> JSONObject:
    """Extract parameter names and default values from WDK analysis form metadata.

    WDK wraps data under ``searchData`` — the response from
    ``GET /analysis-types/{name}`` has the structure::

        { "searchData": { "parameters": [ {name, initialDisplayValue, ...}, ... ] } }

    Uses :func:`unwrap_search_data` to normalize the nesting, then
    extracts ``name``/``initialDisplayValue`` from each parameter spec.

    WDK's ``ParamFormatter.java`` emits ``initialDisplayValue`` (via
    ``JsonKeys.INITIAL_DISPLAY_VALUE``) as the stable default value.

    Vocabulary params (``single-pick-vocabulary``, ``multi-pick-vocabulary``)
    are encoded as JSON arrays per ``AbstractEnumParam.convertToTerms()``.
    """
    defaults: JSONObject = {}
    for p in _extract_param_specs(form_meta):
        name = p.get("name")
        default = p.get("initialDisplayValue")
        if not isinstance(name, str) or not name or default is None:
            continue

        value = str(default)

        # Vocab params must be JSON arrays for convertToTerms().
        param_type = str(p.get("type", ""))
        if param_type in WDK_VOCAB_PARAM_TYPES:
            value = encode_vocab_value(value)

        defaults[name] = value
    return defaults
