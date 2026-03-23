"""StrategyAPI base class with shared infrastructure.

Provides initialization, parameter normalization, and session management
that all mixin classes depend on.
"""

import json

from veupath_chatbot.domain.parameters.vocab_utils import (
    collect_leaf_terms,
    find_vocab_node,
)
from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.param_utils import normalize_param_value
from veupath_chatbot.integrations.veupathdb.strategy_api.helpers import (
    CURRENT_USER,
    resolve_wdk_user_id,
)
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKAnswer
from veupath_chatbot.integrations.veupathdb.wdk_parameters import WDKParameter
from veupath_chatbot.platform.errors import AppError, validate_response
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue

logger = get_logger(__name__)

_MIN_INDENT_VOCAB_ENTRY_LEN = 2
_MIN_ENTRY_PARTS_FOR_CODE_STATE = 2
_MIN_ENTRY_PARTS_FOR_QUANTIFIER = 3


def _sort_profile_pattern(pattern: str) -> str:
    """Sort ``%code:Y%code:N%`` entries alphabetically.

    OrthoMCL requires pattern entries in alphabetical order.  The WDK
    frontend always ``.sort()``s before joining — we must too.
    """
    if not pattern.startswith("%") or not pattern.endswith("%"):
        return pattern
    parts = [p for p in pattern.strip("%").split("%") if p]
    return f"%{'%'.join(sorted(parts))}%" if parts else pattern


class StrategyAPIBase:
    """Base infrastructure for :class:`StrategyAPI`.

    Provides ``__init__``, parameter normalization, and WDK session management.
    Mixin classes inherit from this to access shared state.
    """

    def __init__(self, client: VEuPathDBClient, user_id: str = CURRENT_USER) -> None:
        """Initialize the strategy API.

        :param client: VEuPathDB HTTP client (site-specific).
        :param user_id: WDK user ID; defaults to ``"current"`` (resolved at first use).
        """
        self.client = client
        self._initial_user_id = user_id
        self._resolved_user_id = user_id
        self._session_initialized = False
        self._boolean_search_cache: dict[str, str] = {}
        self._answer_param_cache: dict[str, set[str]] = {}

    def _normalize_parameters(
        self,
        parameters: JSONObject,
        *,
        keep_empty: set[str] | None = None,
    ) -> dict[str, str]:
        """Normalize parameters to WDK string values; omit empty values.

        WDK rejects params like ``hard_floor`` with value ``""`` (Cannot be empty).
        Omitting empty params avoids 422s when a required param is left blank
        in the UI; the caller should supply a valid value for required params.

        Params whose value is ``None`` are omitted (never explicitly set).
        Params whose value is ``""`` (empty string) are kept — the caller
        explicitly included them, and WDK may accept them via
        ``allowEmptyValue``.

        :param parameters: Raw parameter dict.
        :param keep_empty: Param names that must be kept even when empty
            (e.g. AnswerParams that WDK requires as ``""``).
        """
        keep = keep_empty or set()
        out: dict[str, str] = {}
        for key, value in (parameters or {}).items():
            if value is None:
                continue
            s = normalize_param_value(value)
            if s.strip() or key in keep or isinstance(value, str):
                out[key] = s if s.strip() else ""
        # OrthoMCL requires profile_pattern entries in alphabetical order.
        # The frontend monorepo always .sort()s before joining — we must too.
        if "profile_pattern" in out:
            out["profile_pattern"] = _sort_profile_pattern(out["profile_pattern"])
        return out

    async def _ensure_session(self) -> None:
        """Initialize session and resolve user id for mutation endpoints.

        Some WDK deployments allow GET/POST using `/users/current/...` but do NOT
        allow PUT/PATCH/DELETE on `/users/current/...` (405 Method Not Allowed).
        Resolve the concrete user id once and then use `/users/{userId}/...`.
        """
        if self._session_initialized:
            return
        if self._initial_user_id == CURRENT_USER:
            resolved = await resolve_wdk_user_id(self.client)
            if resolved:
                logger.info("Resolved WDK user id", resolved_user_id=resolved)
                self._resolved_user_id = resolved
        self._session_initialized = True

    async def _get_user_id(self, user_id: str | None) -> str:
        """Resolve effective user ID for a request.

        :param user_id: Explicit user ID override, or ``None`` to use resolved.
        :returns: The effective user ID string.
        """
        if user_id is not None:
            return user_id
        await self._ensure_session()
        return self._resolved_user_id

    async def _expand_tree_params_to_leaves(
        self,
        record_type: str,
        search_name: str,
        params: dict[str, str],
    ) -> dict[str, str]:
        """Expand parent tree nodes to leaf descendants for multi-pick-vocabulary params.

        WDK tree params with ``countOnlyLeaves=true`` (like organism) silently
        return 0 results when given a parent node.  The WDK frontend's
        CheckboxTree auto-selects all leaf descendants when a parent is clicked.
        We replicate that: fetch the search's param specs, find tree params
        with ``countOnlyLeaves``, and expand any parent values to their leaves.
        """
        try:
            response = await self.client.get_search_details(
                record_type, search_name, expand_params=True
            )
            wdk_params = response.search_data.parameters
            if not wdk_params:
                return params
            return self._expand_specs(wdk_params, params, search_name)
        except AppError:
            logger.debug("Failed to expand tree params (non-fatal)")
            return params

    def _expand_specs(
        self,
        wdk_params: list[WDKParameter],
        params: dict[str, str],
        search_name: str,
    ) -> dict[str, str]:
        """Expand tree param values using typed WDK parameter specs."""
        result = dict(params)
        for spec in wdk_params:
            if spec.name not in result:
                continue
            if spec.type not in ("multi-pick-vocabulary", "single-pick-vocabulary"):
                continue
            count_only_leaves = getattr(spec, "count_only_leaves", False)
            if not count_only_leaves:
                continue
            vocab = getattr(spec, "vocabulary", None)
            if not isinstance(vocab, dict):
                continue
            expanded = self._expand_single_tree_param(vocab, result[spec.name])
            if expanded is not None:
                original_raw = result[spec.name]
                original_values = self._parse_param_values(original_raw)
                if expanded != [str(v) for v in original_values]:
                    logger.info(
                        "Expanded tree param to leaves",
                        param=spec.name,
                        search=search_name,
                        original_count=len(original_values),
                        expanded_count=len(expanded),
                    )
                    result[spec.name] = json.dumps(expanded)
        return result

    def _parse_param_values(self, raw: str) -> list[JSONValue]:
        """Parse a parameter value string into a list."""
        try:
            values = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            values = [raw] if raw else []
        return values if isinstance(values, list) else []

    def _expand_single_tree_param(
        self, vocab: JSONObject, raw_value: str
    ) -> list[str] | None:
        """Expand a single tree param value to leaf terms."""
        values = self._parse_param_values(raw_value)
        if not values:
            return None

        expanded: list[str] = []
        seen: set[str] = set()
        for val in values:
            val_str = str(val)
            node = find_vocab_node(vocab, val_str)
            if node is None:
                if val_str not in seen:
                    expanded.append(val_str)
                    seen.add(val_str)
                continue
            leaves = collect_leaf_terms(node)
            if not leaves:
                if val_str not in seen:
                    expanded.append(val_str)
                    seen.add(val_str)
            else:
                for leaf in leaves:
                    if leaf not in seen:
                        expanded.append(leaf)
                        seen.add(leaf)
        return expanded

    async def _expand_profile_pattern_groups(
        self,
        record_type: str,
        pattern: str,
    ) -> str:
        """Expand group codes in a profile_pattern to leaf species codes.

        The WDK ``profile_pattern`` is matched via SQL LIKE against a stored
        profile string that only contains **leaf** species codes.  Group codes
        (e.g. ``MAMM``) never appear in the DB string and silently return 0.

        The WDK frontend expands group -> leaves automatically via the
        ``phyletic_indent_map`` tree.  We replicate that logic here so the
        LLM can use intuitive group codes like ``MAMM:N``.
        """
        if not pattern.startswith("%") or not pattern.endswith("%"):
            return pattern

        entries = [p for p in pattern.strip("%").split("%") if p]
        if not entries:
            return pattern

        try:
            indent_vocab = await self._fetch_indent_vocab(record_type)
            if not indent_vocab:
                return pattern

            children_of, leaf_codes = _build_phyletic_tree(indent_vocab)
            expanded = _expand_entries(entries, children_of, leaf_codes)
            return _sort_profile_pattern(f"%{'%'.join(expanded)}%")
        except AppError:
            logger.debug("Failed to expand profile_pattern groups (non-fatal)")
            return pattern

    async def _fetch_indent_vocab(self, record_type: str) -> list[JSONValue]:
        """Fetch the phyletic_indent_map vocabulary."""
        response = await self.client.get_search_details(
            record_type, "GenesByOrthologPattern", expand_params=True
        )
        for param in response.search_data.parameters or []:
            if param.name == "phyletic_indent_map":
                vocab = getattr(param, "vocabulary", None)
                if isinstance(vocab, list):
                    return vocab
        return []

    async def _standard_report(
        self,
        step_id: int,
        report_config: dict[str, object],
        user_id: str | None = None,
    ) -> WDKAnswer:
        """Run a standard report on a step.

        Shared helper used by report, answer, count, and preview methods.

        :param step_id: WDK step ID (must be part of a strategy).
        :param report_config: Report configuration dict.
        :param user_id: Explicit user ID override, or ``None`` to use resolved.
        :returns: Validated WDK answer.
        """
        uid = await self._get_user_id(user_id)
        result = await self.client.post(
            f"/users/{uid}/steps/{step_id}/reports/standard",
            json={"reportConfig": report_config},
        )
        return validate_response(
            WDKAnswer, result, f"WDK answer response for step {step_id}"
        )


def _build_phyletic_tree(
    indent_vocab: list[JSONValue],
) -> tuple[dict[str, list[str]], set[str]]:
    """Build parent->children and leaf sets from the phyletic indent vocabulary."""
    codes_at_depth = [
        (str(item[0]), int(str(item[1])) if item[1] is not None else 0)
        for item in indent_vocab
        if isinstance(item, list) and len(item) >= _MIN_INDENT_VOCAB_ENTRY_LEN
    ]

    children_of: dict[str, list[str]] = {}
    leaf_codes: set[str] = set()
    for i, (code, depth) in enumerate(codes_at_depth):
        descendants: list[str] = []
        for j in range(i + 1, len(codes_at_depth)):
            d_code, d_depth = codes_at_depth[j]
            if d_depth <= depth:
                break
            descendants.append(d_code)
        if descendants:
            children_of[code] = descendants
        else:
            leaf_codes.add(code)
    return children_of, leaf_codes


def _expand_entries(
    entries: list[str],
    children_of: dict[str, list[str]],
    leaf_codes: set[str],
) -> list[str]:
    """Expand group codes in profile_pattern entries to leaf codes."""
    expanded: list[str] = []
    for entry in entries:
        parts = entry.split(":")
        if len(parts) < _MIN_ENTRY_PARTS_FOR_CODE_STATE:
            expanded.append(entry)
            continue

        code = parts[0]
        state = parts[1]  # Y or N
        quantifier = parts[2] if len(parts) >= _MIN_ENTRY_PARTS_FOR_QUANTIFIER else None

        if code not in children_of:
            # Leaf code — pass through (strip quantifier).
            expanded.append(f"{code}:{state}")
            continue

        # Group code — apply quantifier defaults.
        if quantifier is None:
            quantifier = "all" if state == "N" else "any"

        if quantifier == "all":
            expanded.extend(
                f"{desc}:{state}" for desc in children_of[code] if desc in leaf_codes
            )
        else:
            # "any" — cannot express in WDK profile_pattern (OR logic).
            logger.info(
                "Dropping group:%s:%s:any from profile_pattern "
                "(cannot express 'any' in WDK)",
                code,
                state,
            )
    return expanded
