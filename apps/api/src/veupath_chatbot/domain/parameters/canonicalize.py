"""Canonicalize parameter values (API-friendly) using WDK parameter specs.

This module is the counterpart to ``domain/parameters/normalize``:

- ``normalize`` produces WDK wire-safe values (often strings/JSON strings).
- ``canonicalize`` produces API-friendly canonical JSON shapes:
  multi-pick values become ``list[str]``, scalars become strings,
  range values become ``{min, max}``, filter values become dict/list.

Used at API boundaries (plan normalization, validation) so the frontend
can consume stable rules without re-implementing coercion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from veupath_chatbot.domain.parameters._decode_values import decode_values
from veupath_chatbot.domain.parameters.specs import ParamSpecNormalized
from veupath_chatbot.domain.parameters.vocab_utils import flatten_vocab
from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.platform.types import (
    JSONArray,
    JSONObject,
    JSONValue,
    as_json_array,
    as_json_object,
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
                raise ValidationError(
                    title="Unknown parameter",
                    detail=f"Parameter '{name}' does not exist for this search.",
                    errors=[{"param": name, "value": value}],
                )
            if spec.param_type == "input-step":
                continue
            canonical[name] = self._canonicalize_value(spec, value)
        return canonical

    def _canonicalize_value(
        self, spec: ParamSpecNormalized, value: JSONValue
    ) -> JSONValue:
        if value == FAKE_ALL_SENTINEL:
            raise ValidationError(
                title="Invalid parameter value",
                detail=f"Parameter '{spec.name}' does not accept '{FAKE_ALL_SENTINEL}'.",
                errors=[{"param": spec.name, "value": value}],
            )

        param_type = spec.param_type
        if value is None:
            return self._handle_empty(spec, value)

        if param_type == "multi-pick-vocabulary":
            values = [self._stringify(v) for v in decode_values(value, spec.name)]
            if any(v == FAKE_ALL_SENTINEL for v in values):
                raise ValidationError(
                    title="Invalid parameter value",
                    detail=f"Parameter '{spec.name}' does not accept '{FAKE_ALL_SENTINEL}'.",
                    errors=[{"param": spec.name, "value": value}],
                )
            values = [self._match_vocab_value(spec, v) for v in values]
            values = self._enforce_leaf_values(spec, values)
            self._validate_multi_count(spec, values)
            # list[str] is compatible with JSONValue (which includes list[JSONValue])
            # Since str is a JSONValue, list[str] is compatible with list[JSONValue]
            from typing import cast

            return cast(JSONValue, values)

        if param_type == "single-pick-vocabulary":
            decoded = decode_values(value, spec.name)
            if len(decoded) > 1:
                raise ValidationError(
                    title="Invalid parameter value",
                    detail=f"Parameter '{spec.name}' allows only one value.",
                    errors=[{"param": spec.name, "value": value}],
                )
            selected = self._stringify(decoded[0]) if decoded else ""
            if selected == FAKE_ALL_SENTINEL:
                raise ValidationError(
                    title="Invalid parameter value",
                    detail=f"Parameter '{spec.name}' does not accept '{FAKE_ALL_SENTINEL}'.",
                    errors=[{"param": spec.name, "value": value}],
                )
            if not selected:
                self._validate_single_required(spec)
                return ""
            selected = self._match_vocab_value(spec, selected)
            selected = self._enforce_leaf_value(spec, selected)
            if not selected:
                self._validate_single_required(spec)
            return self._stringify(selected)

        if param_type in {"number", "date", "timestamp", "string"}:
            if isinstance(value, (list, dict, tuple, set)):
                raise ValidationError(
                    title="Invalid parameter value",
                    detail=f"Parameter '{spec.name}' must be a scalar value.",
                    errors=[{"param": spec.name, "value": value}],
                )
            return self._stringify(value)

        if param_type in {"number-range", "date-range"}:
            if isinstance(value, dict):
                return value
            if isinstance(value, (list, tuple)) and len(value) == 2:
                return {"min": value[0], "max": value[1]}
            raise ValidationError(
                title="Invalid parameter value",
                detail=f"Parameter '{spec.name}' must be a range.",
                errors=[{"param": spec.name, "value": value}],
            )

        if param_type == "filter":
            if isinstance(value, (dict, list)):
                return value
            return self._stringify(value)

        if param_type in {"input-dataset"}:
            if isinstance(value, list):
                if len(value) != 1:
                    raise ValidationError(
                        title="Invalid parameter value",
                        detail=f"Parameter '{spec.name}' must be a single value.",
                        errors=[{"param": spec.name, "value": value}],
                    )
                return self._stringify(value[0])
            return self._stringify(value)

        # Unknown param type: preserve value as-is (best-effort).
        return value

    def _handle_empty(self, spec: ParamSpecNormalized, value: JSONValue) -> JSONValue:
        if spec.allow_empty_value:
            return ""
        if spec.param_type in {"multi-pick-vocabulary", "single-pick-vocabulary"}:
            self._validate_single_required(spec)
        return value

    def _validate_multi_count(
        self, spec: ParamSpecNormalized, values: list[str]
    ) -> None:
        if not values and spec.allow_empty_value:
            return
        min_count = spec.min_selected_count or 0
        max_count = spec.max_selected_count
        if len(values) < min_count:
            raise ValidationError(
                title="Invalid parameter value",
                detail=f"Parameter '{spec.name}' requires at least {min_count} value(s).",
                errors=[{"param": spec.name, "value": list(values)}],
            )
        if max_count is not None and len(values) > max_count:
            raise ValidationError(
                title="Invalid parameter value",
                detail=f"Parameter '{spec.name}' allows at most {max_count} value(s).",
                errors=[{"param": spec.name, "value": list(values)}],
            )

    def _validate_single_required(self, spec: ParamSpecNormalized) -> None:
        if spec.allow_empty_value:
            return
        min_count = spec.min_selected_count
        if min_count is not None and min_count <= 0:
            return
        raise ValidationError(
            title="Invalid parameter value",
            detail=f"Parameter '{spec.name}' requires a value.",
            errors=[{"param": spec.name}],
        )

    def _match_vocab_value(self, spec: ParamSpecNormalized, value: str) -> str:
        vocab = spec.vocabulary
        if not vocab:
            return value
        value_norm = value.strip() if isinstance(value, str) else str(value)

        def numeric_equivalent(a: str | None, b: str | None) -> bool:
            if not a or not b:
                return False
            try:
                fa = float(str(a).strip())
                fb = float(str(b).strip())
            except Exception:
                return False
            if not (math.isfinite(fa) and math.isfinite(fb)):
                return False
            return math.isclose(fa, fb, rel_tol=1e-9, abs_tol=1e-12)

        entries = flatten_vocab(vocab, prefer_term=True)
        for entry in entries:
            display = entry.get("display")
            raw_value = entry.get("value")
            if value_norm == (display or ""):
                return raw_value or display or value
            if value_norm == (raw_value or ""):
                return raw_value or value
            if numeric_equivalent(value_norm, display):
                return raw_value or display or value
            if numeric_equivalent(value_norm, raw_value):
                return raw_value or value
        raise ValidationError(
            title="Invalid parameter value",
            detail=f"Parameter '{spec.name}' does not accept '{value}'.",
            errors=[{"param": spec.name, "value": value}],
        )

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

        def find_node(node: JSONObject) -> JSONObject | None:
            data_value = node.get("data", {})
            data = as_json_object(data_value) if isinstance(data_value, dict) else {}
            term_value = data.get("term")
            term = str(term_value) if term_value is not None else None
            display_value = data.get("display")
            display = str(display_value) if display_value is not None else None
            if match in (term, display):
                return node
            children_value = node.get("children", [])
            if isinstance(children_value, list):
                children_list = as_json_array(children_value)
                for child_value in children_list:
                    if isinstance(child_value, dict):
                        child = as_json_object(child_value)
                        found = find_node(child)
                        if found:
                            return found
            return None

        def collect_leaf_terms(node: JSONObject) -> list[str]:
            children_value = node.get("children", [])
            children: list[JSONObject] = []
            if isinstance(children_value, list):
                children_list = as_json_array(children_value)
                for child_value in children_list:
                    if isinstance(child_value, dict):
                        children.append(as_json_object(child_value))
            if not children:
                data_value = node.get("data", {})
                data = (
                    as_json_object(data_value) if isinstance(data_value, dict) else {}
                )
                term_value = data.get("term")
                term = str(term_value) if term_value is not None else None
                return [term] if term else []
            leaves: list[str] = []
            for child in children:
                leaves.extend(collect_leaf_terms(child))
            return leaves

        matched_node = find_node(vocabulary)
        if not matched_node:
            return []
        children_value = matched_node.get("children", [])
        children: list[JSONObject] = []
        if isinstance(children_value, list):
            children_list = as_json_array(children_value)
            for child_value in children_list:
                if isinstance(child_value, dict):
                    children.append(as_json_object(child_value))
        if not children:
            data_value = matched_node.get("data", {})
            data = as_json_object(data_value) if isinstance(data_value, dict) else {}
            term_value = data.get("term")
            term = str(term_value) if term_value is not None else None
            return [term] if term else []
        return collect_leaf_terms(matched_node)

    def _find_leaf_term_for_match(
        self, vocabulary: JSONObject | JSONArray | None, match: str
    ) -> str | None:
        if not isinstance(vocabulary, dict) or not match:
            return None

        def find_node(node: JSONObject) -> JSONObject | None:
            data_value = node.get("data", {})
            data = as_json_object(data_value) if isinstance(data_value, dict) else {}
            term = data.get("term")
            display = data.get("display")
            if match in (term, display):
                return node
            children_value = node.get("children", [])
            if isinstance(children_value, list):
                children_list = as_json_array(children_value)
                for child_value in children_list:
                    if isinstance(child_value, dict):
                        child = as_json_object(child_value)
                        found = find_node(child)
                        if found:
                            return found
            return None

        matched_node = find_node(vocabulary)
        if not matched_node:
            return None
        children_value = matched_node.get("children", [])
        children = (
            as_json_array(children_value) if isinstance(children_value, list) else []
        )
        if children:
            return None
        data_value = matched_node.get("data", {})
        data = as_json_object(data_value) if isinstance(data_value, dict) else {}
        term = data.get("term")
        return str(term) if isinstance(term, str) else None

    def _stringify(self, value: JSONValue) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)
