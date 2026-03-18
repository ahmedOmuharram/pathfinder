"""StrategyAPI base class with shared infrastructure.

Provides initialization, parameter normalization, and session management
that all mixin classes depend on.
"""

from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.param_utils import normalize_param_value
from veupath_chatbot.integrations.veupathdb.strategy_api.helpers import (
    CURRENT_USER,
    resolve_wdk_user_id,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue

logger = get_logger(__name__)


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
        self.user_id = user_id
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
        if self.user_id == CURRENT_USER:
            resolved = await resolve_wdk_user_id(self.client)
            if resolved:
                logger.info("Resolved WDK user id", resolved_user_id=resolved)
                self.user_id = resolved
        self._session_initialized = True

    async def _expand_profile_pattern_groups(
        self,
        record_type: str,
        pattern: str,
    ) -> str:
        """Expand group codes in a profile_pattern to leaf species codes.

        The WDK ``profile_pattern`` is matched via SQL LIKE against a stored
        profile string that only contains **leaf** species codes.  Group codes
        (e.g. ``MAMM``) never appear in the DB string and silently return 0.

        The WDK frontend expands group → leaves automatically via the
        ``phyletic_indent_map`` tree.  We replicate that logic here so the
        LLM can use intuitive group codes like ``MAMM:N``.
        """
        if not pattern.startswith("%") or not pattern.endswith("%"):
            return pattern

        # Parse entries: ["MAMM:N", "pfal:Y", ...]
        entries = [p for p in pattern.strip("%").split("%") if p]
        if not entries:
            return pattern

        # Fetch the phyletic tree to identify group vs leaf codes.
        try:
            search_def = await self.client.get(
                f"/record-types/{record_type}/searches/GenesByOrthologPattern",
                params={"expandParams": "true"},
            )
            if not isinstance(search_def, dict):
                return pattern

            # Unwrap searchData wrapper if present.
            search_data = search_def.get("searchData", search_def)
            if not isinstance(search_data, dict):
                return pattern

            params = search_data.get("parameters", [])
            if not isinstance(params, list):
                return pattern
            indent_vocab: list[JSONValue] = []
            for spec in params:
                if isinstance(spec, dict) and spec.get("name") == "phyletic_indent_map":
                    vocab = spec.get("vocabulary")
                    if isinstance(vocab, list):
                        indent_vocab = vocab
                    break

            if not indent_vocab:
                return pattern

            # Build parent→children map from the indentation tree.
            # Each entry is [code, depth, null].
            codes_at_depth: list[tuple[str, int]] = []
            for item in indent_vocab:
                if isinstance(item, list) and len(item) >= 2:
                    codes_at_depth.append(
                        (str(item[0]), int(str(item[1])) if item[1] is not None else 0)
                    )

            # For each code, find its leaf descendants.
            children_of: dict[str, list[str]] = {}
            leaf_codes: set[str] = set()
            for i, (code, depth) in enumerate(codes_at_depth):
                # Collect all descendants until we hit same or lower depth.
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

            # Expand group codes using CODE:STATE[:QUANTIFIER] encoding.
            #
            # Quantifier semantics for groups:
            #   :N:all → absent from ALL members → expand to leaf :N (default for :N)
            #   :N:any → absent from ANY member → cannot express in WDK, drop
            #   :Y:all → present in ALL members → expand to leaf :Y (rare, usually 0)
            #   :Y:any → present in ANY member → cannot express in WDK, drop (default for :Y)
            #
            # Leaf codes ignore the quantifier (single species).
            expanded: list[str] = []
            for entry in entries:
                parts = entry.split(":")
                if len(parts) < 2:
                    expanded.append(entry)
                    continue

                code = parts[0]
                state = parts[1]  # Y or N
                quantifier = parts[2] if len(parts) >= 3 else None

                if code not in children_of:
                    # Leaf code — pass through (strip quantifier).
                    expanded.append(f"{code}:{state}")
                    continue

                # Group code — apply quantifier defaults.
                if quantifier is None:
                    quantifier = "all" if state == "N" else "any"

                if quantifier == "all":
                    # Expand to all leaf descendants.
                    for desc in children_of[code]:
                        if desc in leaf_codes:
                            expanded.append(f"{desc}:{state}")
                else:
                    # "any" — cannot express in WDK profile_pattern (OR logic).
                    logger.info(
                        "Dropping group:%s:%s:any from profile_pattern "
                        "(cannot express 'any' in WDK)",
                        code,
                        state,
                    )

            return _sort_profile_pattern(f"%{'%'.join(expanded)}%")

        except Exception:
            logger.debug("Failed to expand profile_pattern groups (non-fatal)")
            return pattern

    async def _standard_report(
        self,
        step_id: int,
        report_config: JSONObject,
    ) -> JSONObject:
        """Run a standard report on a step.

        Shared helper used by report, answer, count, and preview methods.

        :param step_id: WDK step ID (must be part of a strategy).
        :param report_config: Report configuration dict.
        :returns: Standard report response.
        """
        result = await self.client.post(
            f"/users/{self.user_id}/steps/{step_id}/reports/standard",
            json={"reportConfig": report_config},
        )
        return result if isinstance(result, dict) else {}
