"""Canonicalize parameter values using WDK parameter specs.

The canonicalizer takes a typed ``dict[str, ParamValue]`` (the discriminated
union over the 11 WDK parameter types), validates each value against the
matching spec (vocab matching, leaf enforcement, range bounds, length
limits), and returns a fresh ``dict[str, ParamValue]`` with normalized
contents. Vocab-matched terms replace fuzzy user input, multi-pick parents
expand to their leaf set, and number/date scalars round-trip through
``float()``/``str()`` so the AST holds exactly what WDK will accept.

Validation lives in :mod:`pathfinder.domain.parameters._value_helpers`
``process_value()``; this module owns the post-processing steps that depend
on the canonical *spec* (FAKE_ALL_SENTINEL rejection, leaf enforcement) and
the round-trip back into typed ``ParamValue``.
"""

from dataclasses import dataclass

from pydantic import JsonValue

from pathfinder.domain.parameters._value_helpers import (
    MultiPickProcessed,
    SinglePickProcessed,
    process_value,
)
from pathfinder.domain.parameters.specs import ParamSpecNormalized
from pathfinder.domain.parameters.values import (
    ParamValue,
    as_param_kind,
    from_decoded,
    to_decoded,
)
from pathfinder.domain.parameters.vocab_utils import (
    collect_leaf_terms,
    find_vocab_node,
    get_node_term,
    get_vocab_children,
)
from pathfinder.platform.errors import ValidationError
from pathfinder.platform.types import JSONArray, JSONObject

FAKE_ALL_SENTINEL = "@@fake@@"


@dataclass(frozen=True)
class ParameterCanonicalizer:
    """Canonicalize ``ParamValue`` parameters using canonical parameter specs."""

    specs: dict[str, ParamSpecNormalized]

    def canonicalize(
        self, parameters: dict[str, ParamValue],
    ) -> dict[str, ParamValue]:
        canonical: dict[str, ParamValue] = {}
        for name, value in (parameters or {}).items():
            spec = self.specs.get(name)
            if not spec:
                available = sorted(self.specs.keys())
                raise ValidationError(
                    title="Unknown parameter",
                    detail=f"Parameter '{name}' does not exist for this search. Available parameters: {', '.join(available)}",
                    errors=[{"param": name, "value": to_decoded(value)}],
                )
            if spec.param_type == "input-step":
                continue
            decoded_value = self._canonicalize_value(spec, to_decoded(value))
            canonical[name] = from_decoded(as_param_kind(spec.param_type), decoded_value)
        return canonical

    def _canonicalize_value(
        self, spec: ParamSpecNormalized, value: JsonValue
    ) -> JsonValue:
        # Reject FAKE_ALL_SENTINEL at top level
        if value == FAKE_ALL_SENTINEL:
            raise ValidationError(
                title="Invalid parameter value",
                detail=f"Parameter '{spec.name}' does not accept '{FAKE_ALL_SENTINEL}'.",
                errors=[{"param": spec.name, "value": value}],
            )

        # Reject sentinel inside list/tuple/set values before dispatch
        if isinstance(value, (list, tuple, set)) and any(
            v == FAKE_ALL_SENTINEL for v in value
        ):
            raise ValidationError(
                title="Invalid parameter value",
                detail=f"Parameter '{spec.name}' does not accept '{FAKE_ALL_SENTINEL}'.",
                errors=[{"param": spec.name, "value": value}],
            )

        result = process_value(spec, value)

        if isinstance(result, MultiPickProcessed):
            enforced = self._enforce_leaf_values(spec, result.value)
            return list(enforced)

        if isinstance(result, SinglePickProcessed) and result.value:
            return self._enforce_leaf_value(spec, result.value)

        return result.value

    # -- leaf enforcement (canonicalizer-only) --------------------------------

    def _enforce_leaf_values(
        self, spec: ParamSpecNormalized, values: list[str]
    ) -> list[str]:
        if not spec.count_only_leaves:
            return values
        enforced: list[str] = []
        seen: set[str] = set()
        for value in values:
            leaves = self._expand_leaf_terms_for_match(spec.vocabulary, value)
            if not leaves:
                raise ValidationError(
                    title="Invalid parameter value",
                    detail=f"Parameter '{spec.name}' requires leaf selections.",
                    errors=[{"param": spec.name, "value": value}],
                )
            for leaf in leaves:
                if leaf in seen:
                    continue
                seen.add(leaf)
                enforced.append(leaf)
        return enforced

    def _enforce_leaf_value(self, spec: ParamSpecNormalized, value: str) -> str:
        if not spec.count_only_leaves or not value:
            return value
        leaf = self._find_leaf_term_for_match(spec.vocabulary, value)
        if not leaf:
            raise ValidationError(
                title="Invalid parameter value",
                detail=f"Parameter '{spec.name}' requires leaf selections.",
                errors=[{"param": spec.name, "value": value}],
            )
        return leaf

    def _expand_leaf_terms_for_match(
        self, vocabulary: JSONObject | JSONArray | None, match: str
    ) -> list[str]:
        if not isinstance(vocabulary, dict) or not match:
            return []
        matched_node = find_vocab_node(vocabulary, match)
        if not matched_node:
            return []
        return collect_leaf_terms(matched_node)

    def _find_leaf_term_for_match(
        self, vocabulary: JSONObject | JSONArray | None, match: str
    ) -> str | None:
        if not isinstance(vocabulary, dict) or not match:
            return None
        matched_node = find_vocab_node(vocabulary, match)
        if not matched_node or get_vocab_children(matched_node):
            return None
        return get_node_term(matched_node)
