"""Binding rules for free-text and full-default params (the GenesByText shape).

A live ``GenesByText`` run returned 0 genes for "odorant binding protein" while
the same search returns 3,789 when bound correctly. Two independent defects,
each fatal on its own (verified against VectorBase):

    *reductase              + ["Epitopes"]    -> 0   <- what PathFinder ran
    odorant binding protein + ["Epitopes"]    -> 0   <- fixing only the expression
    odorant binding protein + full field list -> 3789

1. ``text_expression`` is a visible, required, free-text ``string`` param whose
   WDK ``default_value`` is the *example* shown in the form (``*reductase``).
   Binding it silently turns an OBP search into a reductase search.
2. ``text_fields`` ships WDK's curated "search every field" default (25 entries)
   and the intent matcher replaced it with one weakly-matched option.

The discriminator for (1) is ``is_visible``: ``document_type`` is also a
required ``string`` with a default, but it is hidden -- an internal switch whose
``gene`` default is correct and must be preserved.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import pytest
from pydantic import BaseModel, Field

from pathfinder.domain.parameters.values import MultiPickValue, StringValue
from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.integrations.embeddings.prefixes import SEARCH_QUERY_PREFIX
from pathfinder.services.catalog.param_dag import (
    ParameterInfo,
    ParamFetcher,
    resolve_params_with_intent,
)
from pathfinder.services.catalog.param_intent import ParamIntent

TEXT_FIELDS = [
    "apolloCommentContent",
    "ECNumbers",
    "Epitopes",
    "GeneLinkouts",
    "product",
    "Products",
    "name",
    "Notes",
]
ORGANISM_LEAVES = [
    VocabOption(value="Aedes aegypti LVP_AGWG", display="Aedes aegypti LVP_AGWG"),
    VocabOption(value="Anopheles gambiae PEST", display="Anopheles gambiae PEST"),
]


class _Spec(BaseModel):
    """The subset of WDK param metadata these bindings actually turn on."""

    allowed: list[VocabOption] | None = None
    leaves: list[VocabOption] = Field(default_factory=list)
    default: str | None = None
    required: bool = True
    visible: bool = True


def _p(name: str, param_type: str, spec: _Spec | None = None) -> ParameterInfo:
    s = spec or _Spec()
    return ParameterInfo(
        name=name,
        display_name=name,
        type=param_type,
        required=s.required,
        is_visible=s.visible,
        help="",
        value_format="",
        default_value=s.default,
        allowed_values=s.allowed,
        vocab_leaves=s.leaves,
    )


async def _embed_matches_epitopes(texts: Sequence[str]) -> list[list[float]]:
    """Reproduce the real failure: the matcher latches onto one field option."""
    return [
        [1.0, 0.0]
        if t.startswith(SEARCH_QUERY_PREFIX) or "Epitopes" in t
        else [0.0, 1.0]
        for t in texts
    ]


def _genes_by_text_fetch() -> ParamFetcher:
    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return [
            _p(
                "text_search_organism",
                "multi-pick-vocabulary",
                _Spec(allowed=[], leaves=ORGANISM_LEAVES, default="[]"),
            ),
            _p("text_expression", "string", _Spec(default="*reductase")),
            _p("document_type", "string", _Spec(default="gene", visible=False)),
            _p(
                "text_fields",
                "multi-pick-vocabulary",
                _Spec(
                    allowed=[VocabOption(value=f, display=f) for f in TEXT_FIELDS],
                    default=json.dumps(TEXT_FIELDS),
                ),
            ),
        ]

    return fetch_at


async def _resolve(overrides: dict[str, str] | None = None):
    return await resolve_params_with_intent(
        fetch_at=_genes_by_text_fetch(),
        intent=ParamIntent(
            organism_scope="Aedes aegypti",
            text="Aedes aegypti genes annotated as odorant binding protein (OBP)",
        ),
        embed=_embed_matches_epitopes,
        overrides=overrides,
    )


@pytest.mark.asyncio
async def test_visible_free_text_param_is_never_bound_from_the_wdk_example() -> None:
    rp = await _resolve()
    assert "text_expression" not in rp.params, (
        "bound the WDK example value; an OBP search silently becomes a "
        f"reductase search: {rp.params.get('text_expression')!r}"
    )
    assert any(s.param_name == "text_expression" for s in rp.open_slots)


@pytest.mark.asyncio
async def test_hidden_string_param_keeps_its_default() -> None:
    """``document_type`` is required with a default too, but it is hidden -- an
    internal switch, not a user-facing query. Its default is correct."""
    rp = await _resolve()
    value = rp.params["document_type"]
    assert isinstance(value, StringValue)
    assert value.value == "gene"
    assert not any(s.param_name == "document_type" for s in rp.open_slots)


@pytest.mark.asyncio
async def test_free_text_param_accepts_an_explicit_override() -> None:
    rp = await _resolve(overrides={"text_expression": "odorant binding protein"})
    value = rp.params["text_expression"]
    assert isinstance(value, StringValue)
    assert value.value == "odorant binding protein"
    assert not any(s.param_name == "text_expression" for s in rp.open_slots)


@pytest.mark.asyncio
async def test_full_list_default_survives_a_single_weak_semantic_match() -> None:
    """WDK's default is "search every field". Collapsing it to one option makes
    the search miss everything -- proven live: the same expression returns 0
    against ["Epitopes"] and 3,789 against the full list."""
    rp = await _resolve()
    fields = rp.params["text_fields"]
    assert isinstance(fields, MultiPickValue)
    assert fields.values == TEXT_FIELDS, (
        f"curated 25-field default narrowed to {fields.values}"
    )


@pytest.mark.asyncio
async def test_an_explicit_override_still_narrows_the_field_list() -> None:
    rp = await _resolve(overrides={"text_fields": "product"})
    fields = rp.params["text_fields"]
    assert isinstance(fields, MultiPickValue)
    assert fields.values == ["product"]


@pytest.mark.asyncio
async def test_open_slot_offers_the_tree_vocabulary_instead_of_no_options() -> None:
    """``text_search_organism`` carries its 158 real values in ``vocab_leaves``
    (``allowed_values`` is empty for tree-box params). Offering the user a
    question with zero options is unanswerable."""
    rp = await _resolve()
    slot = next(
        (s for s in rp.open_slots if s.param_name == "text_search_organism"), None
    )
    if slot is not None:
        assert slot.options, "asked 'choose a value' while offering no values"
        assert "Aedes aegypti LVP_AGWG" in slot.options
