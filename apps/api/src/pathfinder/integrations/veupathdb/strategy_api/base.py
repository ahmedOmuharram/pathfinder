import json
from dataclasses import dataclass
from typing import NoReturn

from pathfinder.domain.parameters.phyletic import TriState, encode_profile_pattern
from pathfinder.domain.parameters.value_utils import decode_values
from pathfinder.domain.parameters.wdk_vocab import (
    FAKE_ALL_SENTINEL,
    WDKTreeBoxVocabNode,
    collect_leaf_terms,
    find_vocab_node,
)
from pathfinder.integrations.veupathdb.client import VEuPathDBClient
from pathfinder.integrations.veupathdb.param_utils import normalize_param_value
from pathfinder.integrations.veupathdb.phyletic_tree import phyletic_tree_of
from pathfinder.integrations.veupathdb.strategy_api.helpers import (
    CURRENT_USER,
    resolve_wdk_user_id,
)
from pathfinder.integrations.veupathdb.wdk_models import WDKAnswer
from pathfinder.integrations.veupathdb.wdk_parameters import WDKParameter
from pathfinder.platform.errors import AppError, ErrorCode, validate_response
from pathfinder.platform.logging import get_logger
from pathfinder.platform.types import JSONObject

logger = get_logger(__name__)

_CENSUS_STATES: dict[str, TriState] = {"Y": "include", "N": "exclude"}


@dataclass(frozen=True)
class _CensusRead:
    """The states a profile_pattern holds, or why it holds none.

    ``states`` is ``None`` when the value is not built from census tokens.
    ``repeated_code`` names the code that appears twice, which is a different
    fault and gets a different message.
    """

    states: dict[str, TriState] | None
    repeated_code: str | None = None


def _read_census(pattern: str) -> _CensusRead:
    """Read the species state each census token states.

    The value is a LIKE pattern over ``code:Y``/``code:N`` entries separated by
    the wildcard. Anything else matches nothing, and WDK reports that as a count
    rather than as an error. One code states one state, so a code that appears
    twice describes a census that cannot exist.
    """
    if not pattern.startswith("%") or not pattern.endswith("%"):
        return _CensusRead(states=None)
    states: dict[str, TriState] = {}
    for entry in pattern.strip("%").split("%"):
        token = entry.strip()
        if not token:
            continue
        code, _, raw_state = token.partition(":")
        state = _CENSUS_STATES.get(raw_state)
        if not code or state is None:
            return _CensusRead(states=None)
        if code in states:
            return _CensusRead(states=None, repeated_code=code)
        states[code] = state
    return _CensusRead(states=states)


def _refuse_repeated_code(code: str, pattern: str) -> NoReturn:
    """Both paths to the wire refuse a repeated code with the same message."""
    raise AppError(
        code=ErrorCode.VALIDATION_ERROR,
        title="profile_pattern states one code twice",
        status=422,
        detail=(
            f"{code!r} appears twice in {pattern!r}. A species is either "
            f"present or absent, so state it once: '%{code}:Y%' for present "
            f"or '%{code}:N%' for absent."
        ),
    )


def _sort_profile_pattern(pattern: str) -> str:
    """Rewrite a census pattern with its codes in ascending order.

    The pattern is matched against a census that lists codes ascending, and
    ``%A%B%`` means "A, then later B", so entries out of that order describe a
    census that cannot exist. A repeated code is refused here as well as on the
    expansion path, because both of them reach the wire.
    """
    read = _read_census(pattern)
    if read.repeated_code is not None:
        _refuse_repeated_code(read.repeated_code, pattern)
    return pattern if read.states is None else encode_profile_pattern(read.states)


def _validate_phyletic_codes(codes: list[str], all_known_codes: set[str]) -> None:
    """Refuse a code the phyletic tree does not carry.

    WDK matches the pattern with LIKE, so an unknown code returns a count
    instead of an error.
    """
    invalid_codes = [code for code in codes if code not in all_known_codes]
    if invalid_codes:
        raise AppError(
            code=ErrorCode.VALIDATION_ERROR,
            title="Invalid species codes in profile_pattern",
            status=422,
            detail=(
                f"Unknown codes: {', '.join(invalid_codes[:5])}. "
                f"Use lookup_phyletic_codes() to find valid codes "
                f"(e.g. 'pfal' for P. falciparum, 'hsap' for H. sapiens)."
            ),
        )


class StrategyAPIBase:
    def __init__(self, client: VEuPathDBClient, user_id: str = CURRENT_USER) -> None:
        self.client = client
        self._initial_user_id = user_id
        self._resolved_user_id = user_id
        self._session_initialized = False
        self._boolean_search_cache: dict[str, str] = {}
        self._answer_param_cache: dict[str, set[str]] = {}

    def _normalize_parameters(self, parameters: JSONObject) -> dict[str, str]:
        """Normalize parameters to WDK string values; drop ``None``.

        ``None`` values are dropped (caller never set them). Every other
        value is coerced via :func:`normalize_param_value`. Empty strings
        are preserved: callers pass them explicitly (e.g. AnswerParams
        that WDK requires as ``""``) and WDK accepts them via
        ``allowEmptyValue``.
        """
        out: dict[str, str] = {
            key: normalize_param_value(value)
            for key, value in (parameters or {}).items()
            if value is not None
        }
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
        result = dict(params)
        for spec in wdk_params:
            if spec.name not in result:
                continue
            if spec.type not in ("multi-pick-vocabulary", "single-pick-vocabulary"):
                continue
            if not spec.count_only_leaves:
                continue
            vocab = spec.vocabulary
            if not isinstance(vocab, WDKTreeBoxVocabNode):
                continue
            expanded = self._expand_single_tree_param(vocab, result[spec.name])
            if expanded is not None:
                original_values = decode_values(result[spec.name], spec.name)
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

    def _expand_single_tree_param(
        self, vocab: WDKTreeBoxVocabNode, raw_value: str
    ) -> list[str] | None:
        values = decode_values(raw_value, "tree-param")
        if not values:
            return None

        expanded: list[str] = []
        seen: set[str] = set()
        for val in values:
            val_str = str(val)
            # The synthetic root names no real term. Expanding it would select
            # the whole vocabulary instead of failing.
            node = (
                None
                if val_str == FAKE_ALL_SENTINEL
                else find_vocab_node(vocab, val_str)
            )
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
        """Expand clade codes in a profile_pattern to their leaf species codes.

        The pattern is matched via SQL LIKE against a census that holds only
        leaf species codes, so a clade code never matches and the search
        silently returns 0. An explicit species overrides the clade above it.

        Raises ``AppError`` when the value is not a census pattern, states one
        code twice, or names a code the phyletic tree does not carry.
        """
        # A non-census string reaches LIKE and matches nothing, which WDK
        # answers with a count. The published default is one of these.
        read = _read_census(pattern)
        if read.repeated_code is not None:
            _refuse_repeated_code(read.repeated_code, pattern)
        states = read.states
        if states is None:
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                title="profile_pattern is not a census pattern",
                status=422,
                detail=(
                    f"{pattern!r} is not built from census tokens. Use "
                    f"'%code:Y%' for present and '%code:N%' for absent, in "
                    f"ascending code order, or '%' for no constraint. Call "
                    f"lookup_phyletic_codes() for the codes."
                ),
            )
        if not states:
            return pattern

        response = await self.client.get_search_details(
            record_type, "GenesByOrthologPattern", expand_params=True
        )
        tree = phyletic_tree_of(response.search_data.parameters or [])
        if tree is None:
            logger.debug("The phyletic tree is unreadable; the pattern stands")
            return encode_profile_pattern(states)
        _validate_phyletic_codes(list(states), {node.code for node in tree.nodes()})
        return encode_profile_pattern(
            tree.leaf_states(
                [code for code, s in states.items() if s == "include"],
                [code for code, s in states.items() if s == "exclude"],
            )
        )

    async def _standard_report(
        self,
        step_id: int,
        report_config: dict[str, object],
        user_id: str | None = None,
    ) -> WDKAnswer:
        uid = await self._get_user_id(user_id)
        result = await self.client.post(
            f"/users/{uid}/steps/{step_id}/reports/standard",
            json={"reportConfig": report_config},
        )
        return validate_response(
            WDKAnswer, result, f"WDK answer response for step {step_id}"
        )
