"""Canonicalize parameter values (API-friendly) using WDK parameter specs.

This module is the counterpart to ``domain/parameters/normalize``:

- ``normalize`` produces WDK wire-safe values (often strings/JSON strings).
- ``canonicalize`` produces API-friendly canonical JSON shapes:
  multi-pick values become ``list[str]``, scalars become strings,
  range values become ``{min, max}``, filter values become dict/list.

Delegates validation and decoding to the shared dispatch chain in
``_value_helpers.process_value()``, then applies canonicalizer-specific
post-processing (FAKE_ALL_SENTINEL rejection, leaf enforcement).

Used at API boundaries (plan normalization, validation) so the frontend
can consume stable shapes without re-implementing coercion.
"""

from dataclasses import dataclass
from typing import cast

from veupath_chatbot.domain.parameters._value_helpers import (
    ParamKind,
    process_value,
)
from veupath_chatbot.domain.parameters.specs import ParamSpecNormalized
from veupath_chatbot.domain.parameters.vocab_utils import (
    collect_leaf_terms,
    find_vocab_node,
    get_node_term,
    get_vocab_children,
)
from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.platform.types import (
    JSONArray,
    JSONObject,
    JSONValue,
)

FAKE_ALL_SENTINEL = "@@fake@@"


@dataclass(frozen=True)
class ParameterCanonicalizer:
    """Canonicalize parameter values using canonical parameter specs."""

    specs: dict[str, ParamSpecNormalized]

    def canonicalize(self, parameters: JSONObject) -> JSONObject:
        canonical: JSONObject = {}
        for name, value in (parameters or {}).items():
            spec = self.specs.get(name)
            if not spec:
                available = sorted(self.specs.keys())
                raise ValidationError(
                    title="Unknown parameter",
                    detail=f"Parameter '{name}' does not exist for this search. Available parameters: {', '.join(available)}",
                    errors=[{"param": name, "value": value}],
                )
            if spec.param_type == "input-step":
                continue
            canonical[name] = self._canonicalize_value(spec, value)
        return canonical

    def _canonicalize_value(
        self, spec: ParamSpecNormalized, value: JSONValue
    ) -> JSONValue:
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

        # Use shared dispatch for common param-type routing
        result = process_value(spec, value)

        # Canonicalizer-specific post-processing: leaf enforcement
        if result.kind is ParamKind.MULTI_PICK and isinstance(result.value, list):
            values = cast("list[str]", result.value)
            return cast("JSONValue", self._enforce_leaf_values(spec, values))

        if (
            result.kind is ParamKind.SINGLE_PICK
            and isinstance(result.value, str)
            and result.value
        ):
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
