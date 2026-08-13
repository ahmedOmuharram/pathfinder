from __future__ import annotations

from collections.abc import Sequence

import pytest

from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.integrations.embeddings.embed_fn import EmbedFn
from pathfinder.services.catalog.param_formatting import ParameterInfo
from pathfinder.services.catalog.param_intent import (
    NO_RESOLVERS,
    ParamIntent,
    ValueResolvers,
    map_intent_to_value,
)


async def _value(
    pi: ParameterInfo,
    intent: ParamIntent,
    *,
    embed: EmbedFn,
    resolvers: ValueResolvers = NO_RESOLVERS,
) -> str | list[str] | None:
    """The resolved value alone. Provenance is asserted separately."""
    match = await map_intent_to_value(pi, intent, embed=embed, resolvers=resolvers)
    return match.value if match else None


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
    out = await _value(
        pi, ParamIntent(organism_scope="Plasmodium falciparum"), embed=_embed
    )
    assert out == "Plasmodium falciparum 3D7"
    out2 = await _value(pi, ParamIntent(organism_scope="P. berghei"), embed=_embed)
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
    out = await _value(
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
    out = await _value(
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
    out = await _value(
        pi, ParamIntent(text="genes upregulated in gametocytes"), embed=_embed
    )
    assert out == "up"


@pytest.mark.asyncio
async def test_no_resolver_means_a_question_not_a_similarity_guess() -> None:
    """This used to be `test_semantic_match_picks_best_option`.

    A 0.45 cosine score between the criterion sentence and each option's display
    string decided 108 of the 237 gold params no named rule covers, and it is
    what bound `PF00069` to a phosphofructokinase domain. Without an injected
    resolver the answer is now `None`, which opens a slot -- a visible question
    instead of a silent wrong value. `test_vocab_resolver_seam.py` covers the
    resolved path.
    """
    pi = _pi(
        "profileset",
        "single-pick-vocabulary",
        allowed=[
            VocabOption(value="ds_gameto", display="Gametocyte RNA-Seq"),
            VocabOption(value="ds_other", display="Liver stage scRNA-Seq"),
        ],
    )
    out = await _value(pi, ParamIntent(text="gametocyte expression"), embed=_embed)
    assert out is None


@pytest.mark.asyncio
async def test_no_rule_no_options_returns_none() -> None:
    pi = _pi("mystery_param", "single-pick-vocabulary", allowed=[])
    assert await _value(pi, ParamIntent(text=""), embed=_embed) is None


class TestAnExplicitAccessionBlocksGuessing:
    """A named accession that is not in the vocabulary must not fall through.

    Observed: "InterPro domain PF00069" bound
    ``IPR000023 : Phosphofructokinase_dom``. PF00069 is a *Pfam* accession,
    so once FRAME set ``domain_database=INTERPRO`` the dependent vocabulary
    refreshed to 5,405 IPR entries and PF00069 was genuinely absent. The
    accession check found nothing and the semantic tier then matched on the
    substring "kinase" inside "Phosphofructokinase".

    The strategy searched the wrong domain, returned far fewer genes than intended,
    and verification reported success. FRAME's own instruction says that when
    the value is not in the vocabulary the search CANNOT realize the
    criterion -- never guess. So an unmatched explicit accession has to stop
    the chain, not hand it to the fuzzy tier.
    """

    @staticmethod
    def _interpro_vocab() -> list[VocabOption]:
        return [
            VocabOption(
                value="IPR000023 : Phosphofructokinase_dom",
                display="IPR000023 : Phosphofructokinase_dom",
            ),
            VocabOption(value="IPR000719 : Prot_kinase_dom", display="IPR000719"),
        ]

    @pytest.mark.asyncio
    async def test_an_absent_accession_does_not_bind_a_lookalike(self) -> None:
        pi = _pi("domain_typeahead", "multi-pick-vocabulary", self._interpro_vocab())

        out = await _value(
            pi,
            ParamIntent(text="InterPro domain PF00069 (protein kinase domain)"),
            embed=_embed,
        )

        assert out is None, f"expected a Tier-3 slot, guessed {out!r}"

    @pytest.mark.asyncio
    async def test_a_present_accession_still_binds(self) -> None:
        pi = _pi("domain_typeahead", "multi-pick-vocabulary", self._interpro_vocab())

        out = await _value(
            pi, ParamIntent(text="InterPro domain IPR000719"), embed=_embed
        )

        assert out == "IPR000719 : Prot_kinase_dom"

    @pytest.mark.asyncio
    async def test_text_without_an_accession_still_uses_the_other_tiers(self) -> None:
        # No explicit identifier means nothing was overridden; the semantic
        # and rule tiers remain the right answer.
        pi = _pi("organism", "multi-pick-vocabulary")

        out = await _value(
            pi,
            ParamIntent(organism_scope="Plasmodium falciparum", text="kinases"),
            embed=_embed,
        )

        assert out == "Plasmodium falciparum 3D7"
