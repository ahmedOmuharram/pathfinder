"""Tests for the parameter DAG resolver: auto-resolution, choices, and the
dependent-vocabulary walk."""

from __future__ import annotations

import pytest

from pathfinder.domain.parameters.values import (
    FilterValue,
    MultiPickValue,
    NumberValue,
    SinglePickValue,
)
from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.services.catalog.param_dag import (
    ResolvedParams,
    _apply_override,
    _single_valid_value,
    param_value_for,
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


def _tree_box_organism() -> ParameterInfo:
    # A tree-box param carries its values as flattened leaves, not as allowed
    # values.
    return ParameterInfo(
        name="organism",
        display_name="organism",
        type="multi-pick-vocabulary",
        required=True,
        is_visible=True,
        help="",
        value_format="",
        allowed_values=None,
        vocab_leaves=[
            VocabOption(value="Plasmodium vivax P01", display="P. vivax P01"),
            VocabOption(
                value="Plasmodium falciparum 3D7", display="Plasmodium falciparum 3D7"
            ),
        ],
    )


def test_apply_override_matches_a_tree_box_leaf_by_term_or_label() -> None:
    info = _tree_box_organism()

    assert _apply_override(info, "plasmodium vivax p01") == "Plasmodium vivax P01"
    assert _apply_override(info, "P. vivax P01") == "Plasmodium vivax P01"


def test_apply_override_does_not_snap_a_substring_to_a_leaf() -> None:
    # "Plasmodium vivax" is a genus, not the strain leaf. Snapping it binds a
    # strain the request never named.
    assert (
        _apply_override(_tree_box_organism(), "Plasmodium vivax") == "Plasmodium vivax"
    )


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
        intent=ParamIntent(),
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
        intent=ParamIntent(),
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
        intent=ParamIntent(),
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
        intent=ParamIntent(),
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
        intent=ParamIntent(),
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

    rp = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=ParamIntent(),
        overrides={"organism": "Plasmodium falciparum 3D7"},
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

    rp = await resolve_params_with_intent(fetch_at=fetch_at, intent=ParamIntent())
    # WDK measures the comparator against the reference, so the comparator
    # takes the default and the reference becomes the open question.
    assert isinstance(rp.params["samples_de_comp"], SinglePickValue)
    assert rp.params["samples_de_comp"].value == "g1"
    assert "samples_de_ref" not in rp.params
    assert any(s.param_name == "samples_de_ref" for s in rp.open_slots)


@pytest.mark.asyncio
async def test_same_vocab_override_not_duplicated_into_degenerate_pair() -> None:
    # The guard against a same-value pair also covers a value the caller states,
    # not defaults alone.
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

    rp = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=ParamIntent(),
        overrides={"samples_de_comp_generic_deseq": "g1"},
    )
    # The stated group binds the comparator, and the remaining group becomes the
    # reference.
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

    without = await resolve_params_with_intent(fetch_at=fetch_at, intent=ParamIntent())
    assert any(s.param_name == "samples_de_comp" for s in without.open_slots)

    filled = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=ParamIntent(),
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

    rp = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=ParamIntent(),
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

    rp = await resolve_params_with_intent(fetch_at=fetch_at, intent=ParamIntent())
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

    rp = await resolve_params_with_intent(fetch_at=fetch_at, intent=ParamIntent())
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

    rp = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=ParamIntent(),
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

    rp = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=ParamIntent(),
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
async def test_a_deferred_comparator_still_leaves_the_reference_the_other_group() -> (
    None
):
    # The comparator waits for its parent, and the reference waits for the
    # comparator, so the pair settles on distinct groups a pass later.
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

    rp = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=ParamIntent(),
        overrides={"samples_fc_comp_generic": "female"},
    )
    ref = rp.params["samples_fc_ref_generic"]
    comp = rp.params["samples_fc_comp_generic"]
    assert isinstance(ref, MultiPickValue)
    assert isinstance(comp, MultiPickValue)
    assert comp.values == ["female"]
    assert ref.values == ["male"], (
        f"the reference must take the group the comparator did not, got {ref.values}"
    )
    assert rp.open_slots == []


def _info(
    name: str,
    allowed: list[VocabOption] | None,
    *,
    default: str | None = None,
) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type="single-pick-vocabulary",
        required=True,
        is_visible=True,
        help="",
        value_format="",
        default_value=default,
        allowed_values=allowed,
    )


def test_a_one_option_vocabulary_has_a_single_valid_value() -> None:
    info = _info("strand", [VocabOption(value="sense", display="Sense")])

    assert _single_valid_value(info) == "sense"


def test_several_options_leave_the_value_to_the_caller() -> None:
    info = _info(
        "strand",
        [
            VocabOption(value="sense", display="Sense"),
            VocabOption(value="antisense", display="Antisense"),
        ],
        default="sense",
    )

    assert _single_valid_value(info) is None


def test_no_vocabulary_has_no_single_valid_value() -> None:
    assert _single_valid_value(_info("text_expression", None)) is None
