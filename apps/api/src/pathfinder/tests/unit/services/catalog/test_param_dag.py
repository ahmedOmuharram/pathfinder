"""DAG-resolver: Tier-1 (single valid value) auto-resolves; multi-valued params
become choices; the walk fetches a child's vocab under its resolved parent."""

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


async def _embed_prefers_group1(texts: Sequence[str]) -> list[list[float]]:
    # Align the query with "Group 1" (cosine 1.0 >= floor) and leave "Group 2"
    # orthogonal, so the slot-agnostic semantic matcher picks g1 for BOTH params.
    return [
        [1.0, 0.0]
        if t.startswith(SEARCH_QUERY_PREFIX) or "Group 1" in t
        else [0.0, 1.0]
        for t in texts
    ]


def test_apply_override_snaps_to_tree_box_leaf() -> None:
    # A tree-box param exposes its values via the flattened leaves (not the flat
    # `allowed_values`); an override must still snap to the real leaf string.
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
    """WDK's canonical default for a filter param is the empty filter set — it
    must RESOLVE (build-ready), never crash or dangle as an open slot."""

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
    # A differential search's ref/comp sample FILTER pair must NOT both default to
    # the empty 'all samples' filter — that compares all-vs-all → zero DE genes
    # (e.g. the Loffler antibody array). With no override they surface as choices.
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
    """A `<field>=<v1>,<v2>` override selects members of one facet, typed from
    the param's ontology (type/isRange), matched to real values."""

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
    # The model's natural instinct is to emit the real WDK filter value. Accept
    # it (as a JSON string) and match it to the facet's real values.
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
    # A partial clause (field + scalar value, no type/isRange) gets type/isRange
    # filled from the ontology and the scalar wrapped into a member list.
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
            _p("organism", "multi-pick-vocabulary"),  # Tier-2 rule
            _p(
                "strand",
                "single-pick-vocabulary",
                allowed=[VocabOption(value="sense", display="Sense")],
            ),  # Tier-1 auto
            _p("min_tm", "number", default="1"),  # scalar default fill
            _p(
                "profileset",
                "single-pick-vocabulary",
                allowed=[VocabOption(value="ds_x", display="DS X")],
            ),  # Tier-1, gates samples
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
            )  # required, no rule, semantic miss -> Tier-3
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
    # samples revealed only after profileset resolved, then unresolvable -> Tier-3
    assert "samples" not in rp.params
    assert any(s.param_name == "samples" for s in rp.open_slots)
    assert "samples" in rp.unresolved_required


@pytest.mark.asyncio
async def test_same_vocab_default_not_duplicated_into_degenerate_pair() -> None:
    # Two selectors drawn from the SAME vocabulary (a DESeq ref-vs-comp contrast).
    # Defaulting both to the same value compares a group to itself -> 0 results.
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
    # First selector takes its default; the second would duplicate it (same
    # vocab) -> degenerate, so it becomes a user choice instead of silently 0.
    assert isinstance(rp.params["samples_de_ref"], SinglePickValue)
    assert rp.params["samples_de_ref"].value == "g1"
    assert "samples_de_comp" not in rp.params
    assert any(s.param_name == "samples_de_comp" for s in rp.open_slots)


@pytest.mark.asyncio
async def test_same_vocab_intent_match_not_duplicated_into_degenerate_pair() -> None:
    # The degenerate-pair guard must also cover values chosen via Tier-2 INTENT,
    # not just defaults. The matcher is slot-agnostic (same text + same vocab ->
    # same value), so a DESeq ref/comp pair both match "Group 1" from the intent.
    # The second must surface as a user choice, not silently bind a self-contrast.
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
    assert isinstance(rp.params["samples_de_ref_generic_deseq"], SinglePickValue)
    assert rp.params["samples_de_ref_generic_deseq"].value == "g1"
    assert "samples_de_comp_generic_deseq" not in rp.params
    assert any(s.param_name == "samples_de_comp_generic_deseq" for s in rp.open_slots)


@pytest.mark.asyncio
async def test_user_override_fills_an_open_slot() -> None:
    # A required selector with no auto-resolution → open slot. A user override
    # (matched to the vocab, even via display text) closes it as Tier-0.
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
    # A filter param can't be built from a plain phrase like "All field isolates"
    # (no `<facet>=<value>`); rather than crash or dangle as an open slot it
    # resolves to WDK's canonical include-all empty filter set.
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
    # Two single-pick params from DIFFERENT vocabularies both default cleanly —
    # the dedup only blocks identical-vocab degenerate pairs.
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
    # the context-refreshed infos are exposed so the tool can snapshot + summarise
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
