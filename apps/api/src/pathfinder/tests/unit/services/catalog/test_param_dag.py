"""Tests for the parameter DAG resolver: auto-resolution, choices, and the
dependent-vocabulary walk."""

from __future__ import annotations

from collections.abc import Sequence
from unittest.mock import AsyncMock, MagicMock

import pytest

from pathfinder.domain.parameters.values import (
    FilterValue,
    MultiPickValue,
    NumberValue,
    SinglePickValue,
)
from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.integrations.embeddings.prefixes import SEARCH_QUERY_PREFIX
from pathfinder.services.catalog import param_dag
from pathfinder.services.catalog.param_dag import (
    AutoResolved,
    Choice,
    ResolvedParams,
    _apply_override,
    classify_param,
    param_value_for,
    resolve_dag,
    resolve_parameter_dag,
    resolve_params_with_intent,
)
from pathfinder.services.catalog.param_formatting import (
    FilterFieldInfo,
    ParameterInfo,
)
from pathfinder.services.catalog.param_intent import ParamIntent


def _typed(name: str, param_type: str) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type=param_type,
        required=True,
        is_visible=True,
        help="",
        value_format="",
    )


def test_param_value_for_multipick_wraps_bare_term_as_json_array() -> None:
    v = param_value_for(
        _typed("organism", "multi-pick-vocabulary"), "Plasmodium falciparum 3D7"
    )
    assert isinstance(v, MultiPickValue)
    assert v.values == ["Plasmodium falciparum 3D7"]
    assert v.to_wire() == '["Plasmodium falciparum 3D7"]'


def test_param_value_for_scalars() -> None:
    n = param_value_for(_typed("min_tm", "number"), "2")
    assert isinstance(n, NumberValue)
    assert n.value == 2.0
    s = param_value_for(_typed("go_term_evidence", "single-pick-vocabulary"), "Curated")
    assert isinstance(s, SinglePickValue)
    assert s.value == "Curated"


def _p(
    name: str,
    param_type: str,
    *,
    allowed: list[VocabOption] | None = None,
    default: str | None = None,
    required: bool = True,
    depends_on: list[str] | None = None,
) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type=param_type,
        required=required,
        is_visible=True,
        help="",
        value_format="",
        default_value=default,
        allowed_values=allowed,
        vocab_depends_on=depends_on,
    )


async def _embed_orthogonal(texts: Sequence[str]) -> list[list[float]]:
    return [[1.0, 0.0]] + [[0.0, 1.0]] * (len(texts) - 1)


async def _embed_prefers_female(texts: Sequence[str]) -> list[list[float]]:
    # The query aligns with "female" and stays orthogonal to "male".
    return [
        [1.0, 0.0] if t.startswith(SEARCH_QUERY_PREFIX) or "female" in t else [0.0, 1.0]
        for t in texts
    ]


async def _embed_prefers_group1(texts: Sequence[str]) -> list[list[float]]:
    # The query aligns with "Group 1" and stays orthogonal to "Group 2".
    return [
        [1.0, 0.0]
        if t.startswith(SEARCH_QUERY_PREFIX) or "Group 1" in t
        else [0.0, 1.0]
        for t in texts
    ]


def test_apply_override_snaps_to_tree_box_leaf() -> None:
    # A tree-box param carries its values as flattened leaves, not as allowed
    # values, and an override snaps to a leaf string.
    info = ParameterInfo(
        name="organism",
        display_name="organism",
        type="multi-pick-vocabulary",
        required=True,
        is_visible=True,
        help="",
        value_format="",
        allowed_values=None,
        vocab_leaves=[
            VocabOption(value="Plasmodium vivax P01", display="Plasmodium vivax P01"),
            VocabOption(
                value="Plasmodium falciparum 3D7", display="Plasmodium falciparum 3D7"
            ),
        ],
    )
    assert _apply_override(info, "Plasmodium vivax") == "Plasmodium vivax P01"


def _filter(name: str, fields: list[FilterFieldInfo]) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type="filter",
        required=True,
        is_visible=True,
        help="",
        value_format="",
        filter_fields=fields,
    )


_SAMPLE_FACETS = [
    FilterFieldInfo(
        term="Sample type",
        display="Sample type",
        type="string",
        values=["specimen from organism", "culture", "blood"],
    ),
    FilterFieldInfo(term="Country", display="Country", type="string", values=["India"]),
]


@pytest.mark.asyncio
async def test_filter_param_defaults_to_include_all() -> None:
    """The WDK default for a filter param is the empty filter set, and it
    resolves rather than opening a slot."""

    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        return [_filter("ngsSnp_strain_meta", _SAMPLE_FACETS)]

    rp = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=ParamIntent(organism_scope=None, text="all samples"),
        embed=_embed_orthogonal,
    )
    value = rp.params["ngsSnp_strain_meta"]
    assert isinstance(value, FilterValue)
    assert value.filters == []
    assert value.to_wire() == '{"filters": []}'
    assert rp.unresolved_required == []
    assert rp.open_slots == []


_LOFFLER_FACETS = [
    FilterFieldInfo(
        term="PCR result",
        display="PCR result",
        type="string",
        values=["Negative", "Positive"],
    )
]


async def _resolve_loffler(overrides: dict[str, str] | None) -> ResolvedParams:
    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return [
            _filter("ref_samples_filter_metadata_loffler", _LOFFLER_FACETS),
            _filter("comp_samples_filter_metadata_loffler", _LOFFLER_FACETS),
        ]

    return await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=ParamIntent(organism_scope=None, text="immunogenic in infection"),
        embed=_embed_orthogonal,
        overrides=overrides,
    )


@pytest.mark.asyncio
async def test_ref_comp_filter_pair_surfaces_instead_of_degenerate_all_vs_all() -> None:
    # A reference and comparison filter pair must not both take the empty
    # filter, because that compares a set against itself.
    rp = await _resolve_loffler(None)
    assert "ref_samples_filter_metadata_loffler" not in rp.params
    assert "comp_samples_filter_metadata_loffler" not in rp.params
    assert set(rp.unresolved_required) == {
        "ref_samples_filter_metadata_loffler",
        "comp_samples_filter_metadata_loffler",
    }


@pytest.mark.asyncio
async def test_ref_comp_filter_pair_resolves_to_distinct_groups_when_overridden() -> (
    None
):
    rp = await _resolve_loffler(
        {
            "ref_samples_filter_metadata_loffler": "PCR result=Negative",
            "comp_samples_filter_metadata_loffler": "PCR result=Positive",
        }
    )
    ref = rp.params["ref_samples_filter_metadata_loffler"]
    comp = rp.params["comp_samples_filter_metadata_loffler"]
    assert isinstance(ref, FilterValue)
    assert isinstance(comp, FilterValue)
    assert ref.filters[0].value == ["Negative"]
    assert comp.filters[0].value == ["Positive"]
    assert rp.unresolved_required == []


@pytest.mark.asyncio
async def test_filter_param_override_builds_typed_clause() -> None:
    """A field-and-values override selects members of one facet and takes its
    type from the parameter ontology."""

    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        return [_filter("ngsSnp_strain_meta", _SAMPLE_FACETS)]

    rp = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=ParamIntent(organism_scope=None, text="cultured and blood samples"),
        embed=_embed_orthogonal,
        overrides={"ngsSnp_strain_meta": "Sample type=culture,blood"},
    )
    value = rp.params["ngsSnp_strain_meta"]
    assert isinstance(value, FilterValue)
    assert len(value.filters) == 1
    clause = value.filters[0]
    assert clause.field == "Sample type"
    assert clause.type == "string"
    assert clause.is_range is False
    assert clause.value == ["culture", "blood"]


@pytest.mark.asyncio
async def test_filter_param_override_matches_field_case_insensitively() -> None:
    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        return [_filter("ngsSnp_strain_meta", _SAMPLE_FACETS)]

    rp = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=ParamIntent(organism_scope=None, text="x"),
        embed=_embed_orthogonal,
        overrides={"ngsSnp_strain_meta": "sample type=culture"},
    )
    value = rp.params["ngsSnp_strain_meta"]
    assert isinstance(value, FilterValue)
    clause = value.filters[0]
    assert clause.field == "Sample type"
    assert clause.value == ["culture"]


async def _resolve_filter_override(override: str) -> FilterValue:
    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return [_filter("ngsSnp_strain_meta", _SAMPLE_FACETS)]

    rp = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=ParamIntent(organism_scope=None, text="x"),
        embed=_embed_orthogonal,
        overrides={"ngsSnp_strain_meta": override},
    )
    value = rp.params["ngsSnp_strain_meta"]
    assert isinstance(value, FilterValue)
    return value


@pytest.mark.asyncio
async def test_filter_override_accepts_full_wdk_filter_json_string() -> None:
    # An override can be a full WDK filter value as a JSON string.
    value = await _resolve_filter_override(
        '{"filters": [{"field": "Sample type", "type": "string", '
        '"isRange": false, "includeUnknown": false, "value": ["culture", "blood"]}]}'
    )
    assert len(value.filters) == 1
    clause = value.filters[0]
    assert clause.field == "Sample type"
    assert clause.value == ["culture", "blood"]


@pytest.mark.asyncio
async def test_filter_override_enriches_partial_clause_from_ontology() -> None:
    # A partial clause takes its type from the ontology, and a scalar value
    # becomes a member list.
    value = await _resolve_filter_override(
        '{"filters": [{"field": "Sample type", "value": "specimen from organism"}]}'
    )
    clause = value.filters[0]
    assert clause.field == "Sample type"
    assert clause.type == "string"
    assert clause.is_range is False
    assert clause.value == ["specimen from organism"]


@pytest.mark.asyncio
async def test_filter_override_empty_filters_json_means_include_all() -> None:
    value = await _resolve_filter_override('{"filters": []}')
    assert value.filters == []


@pytest.mark.asyncio
async def test_filter_override_garbage_degrades_to_include_all() -> None:
    value = await _resolve_filter_override("not a filter at all")
    assert value.filters == []


@pytest.mark.asyncio
async def test_resolve_params_with_intent_tiers_and_dependent_chain() -> None:
    def schema_for(context: dict[str, str]) -> list[ParameterInfo]:
        params = [
            _p("organism", "multi-pick-vocabulary"),
            _p(
                "strand",
                "single-pick-vocabulary",
                allowed=[VocabOption(value="sense", display="Sense")],
            ),
            _p("min_tm", "number", default="1"),
            # A resolved profileset reveals the samples parameter.
            _p(
                "profileset",
                "single-pick-vocabulary",
                allowed=[VocabOption(value="ds_x", display="DS X")],
            ),
        ]
        if "profileset" in context:
            params.append(
                _p(
                    "samples",
                    "multi-pick-vocabulary",
                    allowed=[
                        VocabOption(value="s1", display="Sample 1"),
                        VocabOption(value="s2", display="Sample 2"),
                    ],
                    depends_on=["profileset"],
                )
            )
        return params

    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        return schema_for(context)

    intent = ParamIntent(organism_scope="P. falciparum", text="gametocyte expression")
    rp = await resolve_params_with_intent(
        fetch_at=fetch_at, intent=intent, embed=_embed_orthogonal
    )
    assert isinstance(rp, ResolvedParams)
    assert isinstance(rp.params["organism"], MultiPickValue)
    assert rp.params["organism"].values == ["Plasmodium falciparum 3D7"]
    assert isinstance(rp.params["strand"], SinglePickValue)
    assert rp.params["strand"].value == "sense"
    assert isinstance(rp.params["min_tm"], NumberValue)
    assert rp.params["min_tm"].value == 1.0
    assert isinstance(rp.params["profileset"], SinglePickValue)
    assert rp.params["profileset"].value == "ds_x"
    # The samples parameter appears after profileset resolves, and it stays
    # open.
    assert "samples" not in rp.params
    assert any(s.param_name == "samples" for s in rp.open_slots)
    assert "samples" in rp.unresolved_required


@pytest.mark.asyncio
async def test_same_vocab_default_not_duplicated_into_degenerate_pair() -> None:
    # Two selectors that share a vocabulary must not take the same default,
    # because that compares a group against itself.
    groups = [
        VocabOption(value="g1", display="Group 1"),
        VocabOption(value="g2", display="Group 2"),
    ]

    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return [
            _p(
                "samples_de_ref", "single-pick-vocabulary", allowed=groups, default="g1"
            ),
            _p(
                "samples_de_comp",
                "single-pick-vocabulary",
                allowed=groups,
                default="g1",
            ),
        ]

    intent = ParamIntent(organism_scope=None, text="no matching comparison terms")
    rp = await resolve_params_with_intent(
        fetch_at=fetch_at, intent=intent, embed=_embed_orthogonal
    )
    # WDK measures the comparator against the reference, so the comparator
    # takes the default and the reference becomes the open question.
    assert isinstance(rp.params["samples_de_comp"], SinglePickValue)
    assert rp.params["samples_de_comp"].value == "g1"
    assert "samples_de_ref" not in rp.params
    assert any(s.param_name == "samples_de_ref" for s in rp.open_slots)


@pytest.mark.asyncio
async def test_same_vocab_intent_match_not_duplicated_into_degenerate_pair() -> None:
    # The guard against a same-value pair also covers values that come from the
    # intent, not defaults alone.
    groups = [
        VocabOption(value="g1", display="Group 1"),
        VocabOption(value="g2", display="Group 2"),
    ]

    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return [
            _p(
                "samples_de_ref_generic_deseq", "single-pick-vocabulary", allowed=groups
            ),
            _p(
                "samples_de_comp_generic_deseq",
                "single-pick-vocabulary",
                allowed=groups,
            ),
        ]

    intent = ParamIntent(organism_scope=None, text="group 1 gametocytes")
    rp = await resolve_params_with_intent(
        fetch_at=fetch_at, intent=intent, embed=_embed_prefers_group1
    )
    # The intent names the enriched group, so it binds the comparator and the
    # remaining group becomes the reference.
    comp = rp.params["samples_de_comp_generic_deseq"]
    ref = rp.params["samples_de_ref_generic_deseq"]
    assert isinstance(comp, SinglePickValue)
    assert isinstance(ref, SinglePickValue)
    assert comp.value == "g1"
    assert ref.value == "g2"
    assert rp.open_slots == []


@pytest.mark.asyncio
async def test_user_override_fills_an_open_slot() -> None:
    # A required selector with no auto-resolution opens a slot, and an override
    # that matches the vocabulary closes it.
    groups = [
        VocabOption(value="gametocyte", display="Gametocyte"),
        VocabOption(value="asexual", display="Asexual blood stage"),
    ]

    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return [_p("samples_de_comp", "single-pick-vocabulary", allowed=groups)]

    intent = ParamIntent(organism_scope=None, text="no matching comparison")
    without = await resolve_params_with_intent(
        fetch_at=fetch_at, intent=intent, embed=_embed_orthogonal
    )
    assert any(s.param_name == "samples_de_comp" for s in without.open_slots)

    filled = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=intent,
        embed=_embed_orthogonal,
        overrides={"samples_de_comp": "Gametocyte"},
    )
    assert filled.open_slots == []
    value = filled.params["samples_de_comp"]
    assert isinstance(value, SinglePickValue)
    assert value.value == "gametocyte"


@pytest.mark.asyncio
async def test_filter_override_without_field_eq_means_include_all() -> None:
    # An override without a facet and value resolves to the empty filter set.
    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return [_filter("ngsSnp_strain_meta", _SAMPLE_FACETS)]

    intent = ParamIntent(organism_scope=None, text="x")
    rp = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=intent,
        embed=_embed_orthogonal,
        overrides={"ngsSnp_strain_meta": "All field isolates"},
    )
    value = rp.params["ngsSnp_strain_meta"]
    assert isinstance(value, FilterValue)
    assert value.filters == []
    assert not any(s.param_name == "ngsSnp_strain_meta" for s in rp.open_slots)


@pytest.mark.asyncio
async def test_distinct_vocab_defaults_both_apply() -> None:
    # The same-value guard applies to one shared vocabulary only.
    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return [
            _p(
                "go_slim",
                "single-pick-vocabulary",
                allowed=[
                    VocabOption(value="No", display="No"),
                    VocabOption(value="Yes", display="Yes"),
                ],
                default="No",
            ),
            _p(
                "regulated_dir",
                "single-pick-vocabulary",
                allowed=[
                    VocabOption(value="up", display="Up"),
                    VocabOption(value="down", display="Down"),
                ],
                default="up",
            ),
        ]

    intent = ParamIntent(organism_scope=None, text="no matching terms")
    rp = await resolve_params_with_intent(
        fetch_at=fetch_at, intent=intent, embed=_embed_orthogonal
    )
    go_slim = rp.params["go_slim"]
    regulated_dir = rp.params["regulated_dir"]
    assert isinstance(go_slim, SinglePickValue)
    assert isinstance(regulated_dir, SinglePickValue)
    assert go_slim.value == "No"
    assert regulated_dir.value == "up"
    assert rp.open_slots == []


@pytest.mark.asyncio
async def test_single_value_vocab_pair_both_bind_instead_of_opening_a_slot() -> None:
    # A one-option vocabulary leaves no second value, so both selectors bind it
    # and neither opens a slot.
    only = [VocabOption(value="average1", display="average")]

    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return [
            _p(
                "min_max_avg_ref",
                "single-pick-vocabulary",
                allowed=only,
                default="average1",
            ),
            _p(
                "min_max_avg_comp",
                "single-pick-vocabulary",
                allowed=only,
                default="average1",
            ),
        ]

    intent = ParamIntent(organism_scope=None, text="female versus male")
    rp = await resolve_params_with_intent(
        fetch_at=fetch_at, intent=intent, embed=_embed_orthogonal
    )
    ref = rp.params["min_max_avg_ref"]
    comp = rp.params["min_max_avg_comp"]
    assert isinstance(ref, SinglePickValue)
    assert isinstance(comp, SinglePickValue)
    assert ref.value == "average1"
    assert comp.value == "average1"
    assert rp.open_slots == []
    assert rp.unresolved_required == []


@pytest.mark.asyncio
async def test_user_override_outranks_the_degenerate_pair_guard() -> None:
    # An explicit override outranks the same-value guard.
    groups = [
        VocabOption(value="g1", display="Group 1"),
        VocabOption(value="g2", display="Group 2"),
    ]

    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return [
            _p(
                "samples_de_ref", "single-pick-vocabulary", allowed=groups, default="g1"
            ),
            _p(
                "samples_de_comp",
                "single-pick-vocabulary",
                allowed=groups,
                default="g1",
            ),
        ]

    intent = ParamIntent(organism_scope=None, text="no matching comparison terms")
    rp = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=intent,
        embed=_embed_orthogonal,
        overrides={"samples_de_comp": "g1"},
    )
    comp = rp.params["samples_de_comp"]
    assert isinstance(comp, SinglePickValue)
    assert comp.value == "g1"
    assert rp.open_slots == []
    assert rp.unresolved_required == []


@pytest.mark.asyncio
async def test_override_claims_its_value_before_siblings_auto_resolve() -> None:
    # An override claims its vocabulary value before a sibling auto-resolves.
    groups = [
        VocabOption(value="male", display="male"),
        VocabOption(value="female", display="female"),
    ]

    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return [
            _p("samples_fc_ref_generic", "multi-pick-vocabulary", allowed=groups),
            _p("samples_fc_comp_generic", "multi-pick-vocabulary", allowed=groups),
        ]

    intent = ParamIntent(organism_scope=None, text="upregulated in female adults")
    rp = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=intent,
        embed=_embed_prefers_female,
        overrides={"samples_fc_comp_generic": "female"},
    )
    ref = rp.params["samples_fc_ref_generic"]
    comp = rp.params["samples_fc_comp_generic"]
    assert isinstance(ref, MultiPickValue)
    assert isinstance(comp, MultiPickValue)
    assert comp.values == ["female"], "the explicit override must be honored"
    assert ref.values != comp.values, (
        f"degenerate self-comparison: ref and comp both {ref.values}"
    )
    assert rp.open_slots == []


@pytest.mark.asyncio
async def test_override_evicts_a_guess_even_when_deferred_by_a_dependency() -> None:
    # A dependent selector waits for its parent, so a sibling can bind the
    # overridden value first. The override then evicts that guess.
    groups = [
        VocabOption(value="male", display="male"),
        VocabOption(value="female", display="female"),
    ]

    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        comp_allowed = groups if "profileset" in context else [groups[1]]
        return [
            _p(
                "profileset",
                "single-pick-vocabulary",
                allowed=[VocabOption(value="ps1", display="Profile Set 1")],
            ),
            _p("samples_fc_ref_generic", "multi-pick-vocabulary", allowed=groups),
            _p(
                "samples_fc_comp_generic",
                "multi-pick-vocabulary",
                allowed=comp_allowed,
                depends_on=["profileset"],
            ),
        ]

    intent = ParamIntent(organism_scope=None, text="upregulated in female adults")
    rp = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=intent,
        embed=_embed_prefers_female,
        overrides={"samples_fc_comp_generic": "female"},
    )
    ref = rp.params["samples_fc_ref_generic"]
    comp = rp.params["samples_fc_comp_generic"]
    assert isinstance(ref, MultiPickValue)
    assert isinstance(comp, MultiPickValue)
    assert comp.values == ["female"]
    assert ref.values == ["male"], (
        f"the guess should have been evicted and re-deduced, got {ref.values}"
    )
    assert rp.open_slots == []


def _info(
    name: str,
    allowed: list[VocabOption] | None,
    *,
    default: str | None = None,
    required: bool = True,
    depends_on: list[str] | None = None,
) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type="single-pick-vocabulary",
        required=required,
        is_visible=True,
        help="",
        value_format="",
        default_value=default,
        allowed_values=allowed,
        vocab_depends_on=depends_on,
    )


def test_single_valid_value_is_auto_resolved() -> None:
    tier = classify_param(
        _info("strand", [VocabOption(value="sense", display="Sense")])
    )
    assert isinstance(tier, AutoResolved)
    assert tier.name == "strand"
    assert tier.value == "sense"


def test_multiple_valid_values_become_a_choice() -> None:
    tier = classify_param(
        _info(
            "strand",
            [
                VocabOption(value="sense", display="Sense"),
                VocabOption(value="antisense", display="Antisense"),
            ],
            default="sense",
        )
    )
    assert isinstance(tier, Choice)
    assert [o.value for o in tier.options] == ["sense", "antisense"]
    assert tier.default == "sense"


@pytest.mark.asyncio
async def test_flat_search_classifies_each_required_param() -> None:
    async def fetch_at(_ctx: dict[str, str]) -> list[ParameterInfo]:
        return [
            _info("strand", [VocabOption(value="sense", display="Sense")]),
            _info(
                "organism",
                [
                    VocabOption(value="pf", display="P. falciparum"),
                    VocabOption(value="pv", display="P. vivax"),
                ],
            ),
        ]

    res = await resolve_dag(fetch_at=fetch_at)
    assert [a.name for a in res.auto_resolved] == ["strand"]
    assert [a.value for a in res.auto_resolved] == ["sense"]
    assert [c.name for c in res.choices] == ["organism"]


@pytest.mark.asyncio
async def test_child_vocab_fetched_under_resolved_parent() -> None:
    seen: list[dict[str, str]] = []

    async def fetch_at(ctx: dict[str, str]) -> list[ParameterInfo]:
        seen.append(dict(ctx))
        profileset = _info(
            "profileset", [VocabOption(value="exp1", display="Experiment 1")]
        )
        if ctx.get("profileset") == "exp1":
            samples = _info(
                "samples",
                [
                    VocabOption(value="ref", display="Reference"),
                    VocabOption(value="comp", display="Comparison"),
                ],
                depends_on=["profileset"],
            )
        else:
            samples = _info("samples", None, depends_on=["profileset"])
        return [profileset, samples]

    res = await resolve_dag(fetch_at=fetch_at)

    assert [a.name for a in res.auto_resolved] == ["profileset"]
    samples_choice = next(c for c in res.choices if c.name == "samples")
    assert [o.value for o in samples_choice.options] == ["ref", "comp"]
    assert {"profileset": "exp1"} in seen
    # The result carries the context-refreshed parameter infos.
    samples_info = next(i for i in res.param_infos if i.name == "samples")
    assert samples_info.allowed_values is not None
    assert [v.value for v in samples_info.allowed_values] == ["ref", "comp"]


@pytest.mark.asyncio
async def test_resolve_parameter_dag_wires_client_to_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = MagicMock()
    raw.name = "strand"
    raw.dependent_params = []
    details = MagicMock()
    details.search_data.parameters = [raw]
    client = MagicMock()
    client.get_search_details = AsyncMock(return_value=details)
    monkeypatch.setattr(param_dag, "get_wdk_client", lambda _site: client)
    monkeypatch.setattr(
        param_dag,
        "format_param_info_typed",
        lambda _params: [
            _info("strand", [VocabOption(value="sense", display="Sense")])
        ],
    )

    res = await resolve_parameter_dag(
        site_id="plasmodb", record_type="transcript", search_name="GenesByRNASeq"
    )

    assert [a.name for a in res.auto_resolved] == ["strand"]
    assert [a.value for a in res.auto_resolved] == ["sense"]
    client.get_search_details.assert_awaited()
