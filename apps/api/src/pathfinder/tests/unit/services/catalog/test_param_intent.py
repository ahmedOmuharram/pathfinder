from __future__ import annotations

from collections.abc import Sequence

import pytest

from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.services.catalog.param_formatting import ParameterInfo
from pathfinder.services.catalog.param_intent import ParamIntent, map_intent_to_value


async def _embed(texts: Sequence[str]) -> list[list[float]]:
    # query aligns with the FIRST option, orthogonal to the rest.
    return [[1.0, 0.0], [1.0, 0.0]] + [[0.0, 1.0]] * (len(texts) - 2)


def _pi(
    name: str,
    param_type: str,
    allowed: list[VocabOption] | None = None,
) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type=param_type,
        required=True,
        is_visible=True,
        help="",
        value_format="",
        allowed_values=allowed,
    )


@pytest.mark.asyncio
async def test_organism_rule_maps_species_to_wdk_term() -> None:
    pi = _pi("organism", "multi-pick-vocabulary")  # tree-box, no flat options
    out = await map_intent_to_value(
        pi, ParamIntent(organism_scope="Plasmodium falciparum"), embed=_embed
    )
    assert out == "Plasmodium falciparum 3D7"
    out2 = await map_intent_to_value(
        pi, ParamIntent(organism_scope="P. berghei"), embed=_embed
    )
    assert out2 == "Plasmodium berghei ANKA"


_ORG_OPTS = [
    VocabOption(value="Plasmodium falciparum 3D7", display="Plasmodium falciparum 3D7"),
    VocabOption(value="Toxoplasma gondii ME49", display="Toxoplasma gondii ME49"),
    VocabOption(value="Plasmodium vivax P01", display="Plasmodium vivax P01"),
]


@pytest.mark.asyncio
async def test_organism_named_in_criterion_text_beats_scope() -> None:
    # For a cross-organism search (e.g. an orthology TARGET), the organism named
    # in the criterion text is the specific per-criterion choice and must win
    # over the strategy-wide organism_scope anchor. General — no search hardcoding.
    pi = _pi("organism", "multi-pick-vocabulary", allowed=_ORG_OPTS)
    out = await map_intent_to_value(
        pi,
        ParamIntent(
            organism_scope="Plasmodium vivax",
            text="Has ortholog(s) in Toxoplasma gondii ME49",
        ),
        embed=_embed,
    )
    assert out == "Toxoplasma gondii ME49"


@pytest.mark.asyncio
async def test_organism_falls_back_to_scope_when_text_names_no_organism() -> None:
    pi = _pi("organism", "multi-pick-vocabulary", allowed=_ORG_OPTS)
    out = await map_intent_to_value(
        pi,
        ParamIntent(organism_scope="Plasmodium falciparum", text="surface kinases"),
        embed=_embed,
    )
    assert out == "Plasmodium falciparum 3D7"


@pytest.mark.asyncio
async def test_direction_rule_from_text() -> None:
    pi = _pi(
        "regulated_dir",
        "single-pick-vocabulary",
        allowed=[
            VocabOption(value="up", display="Up-regulated"),
            VocabOption(value="down", display="Down-regulated"),
        ],
    )
    out = await map_intent_to_value(
        pi, ParamIntent(text="genes upregulated in gametocytes"), embed=_embed
    )
    assert out == "up"


@pytest.mark.asyncio
async def test_semantic_match_picks_best_option() -> None:
    pi = _pi(
        "profileset",
        "single-pick-vocabulary",
        allowed=[
            VocabOption(value="ds_gameto", display="Gametocyte RNA-Seq"),
            VocabOption(value="ds_other", display="Liver stage scRNA-Seq"),
        ],
    )
    out = await map_intent_to_value(
        pi, ParamIntent(text="gametocyte expression"), embed=_embed
    )
    assert out == "ds_gameto"


@pytest.mark.asyncio
async def test_no_rule_no_options_returns_none() -> None:
    pi = _pi("mystery_param", "single-pick-vocabulary", allowed=[])
    assert await map_intent_to_value(pi, ParamIntent(text=""), embed=_embed) is None
