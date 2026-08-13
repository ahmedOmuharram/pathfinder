"""Two guards against strategies that run fine and answer nothing.

Both live in ``kind_validation.py``, which nothing has imported since the
FRAME/BUILD migration. They protect against the worst failure mode in this
product: a strategy that pushes cleanly, returns a number, and is biologically
meaningless.

- A differential search whose reference and comparison samples are the same
  group is a contrast of a set against itself.
- INTERSECT across organisms compares gene IDs from different species, which
  never match, so the answer is always zero.

They belong on the validator every push already runs, not in a module with no
callers.
"""

from pathfinder.domain.parameters.values import MultiPickValue, StringValue
from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.validate import validate_strategy


def _differential(step_id: str, ref: str, comp: str) -> StrategyStepNode:
    return StrategyStepNode(
        id=step_id,
        search_name="GenesByDeseqExpression",
        parameters={
            "samples_de_ref_generic_deseq": StringValue(value=ref),
            "samples_de_comp_generic_deseq": StringValue(value=comp),
        },
    )


def _taxon(step_id: str, organism: str) -> StrategyStepNode:
    return StrategyStepNode(
        id=step_id,
        search_name="GenesByTaxon",
        parameters={"organism": MultiPickValue(values=[organism])},
    )


def _intersect(
    step_id: str, primary: StrategyStepNode, secondary: StrategyStepNode
) -> StrategyStepNode:
    return StrategyStepNode(
        id=step_id,
        search_name="__combine__",
        primary_input=primary,
        secondary_input=secondary,
        operator=CombineOp.INTERSECT,
    )


class TestIdenticalContrastSamples:
    def test_a_group_contrasted_against_itself_is_rejected(self) -> None:
        result = validate_strategy(
            _differential("s", "gametocyte", "gametocyte"), "transcript"
        )

        assert not result.valid

    def test_the_message_names_the_problem_in_biological_terms(self) -> None:
        result = validate_strategy(
            _differential("s", "gametocyte", "gametocyte"), "transcript"
        )

        joined = " ".join(issue.message for issue in result.errors)
        assert "reference" in joined.lower()
        assert "comparison" in joined.lower()

    def test_a_genuine_contrast_passes(self) -> None:
        result = validate_strategy(
            _differential("s", "gametocyte", "ring"), "transcript"
        )

        assert result.valid

    def test_fold_change_naming_is_covered_too(self) -> None:
        """The pair is matched by ``_ref_``/``_comp_``, not one search's names."""
        step = StrategyStepNode(
            id="s",
            search_name="GenesByFoldChange",
            parameters={
                "samples_fc_ref_generic": StringValue(value="ring"),
                "samples_fc_comp_generic": StringValue(value="ring"),
            },
        )

        assert not validate_strategy(step, "transcript").valid

    def test_an_unpaired_reference_is_not_flagged(self) -> None:
        step = StrategyStepNode(
            id="s",
            search_name="GenesByDeseqExpression",
            parameters={"samples_de_ref_generic_deseq": StringValue(value="ring")},
        )

        assert validate_strategy(step, "transcript").valid


class TestCrossOrganismIntersect:
    def test_intersecting_two_species_is_rejected(self) -> None:
        step = _intersect(
            "c",
            _taxon("a", "Plasmodium falciparum 3D7"),
            _taxon("b", "Toxoplasma gondii ME49"),
        )

        assert not validate_strategy(step, "transcript").valid

    def test_the_message_explains_why_it_returns_zero(self) -> None:
        step = _intersect(
            "c",
            _taxon("a", "Plasmodium falciparum 3D7"),
            _taxon("b", "Toxoplasma gondii ME49"),
        )

        joined = " ".join(
            issue.message for issue in validate_strategy(step, "transcript").errors
        )
        assert "organism" in joined.lower()

    def test_the_same_organism_on_both_sides_passes(self) -> None:
        step = _intersect(
            "c",
            _taxon("a", "Plasmodium falciparum 3D7"),
            _taxon("b", "Plasmodium falciparum 3D7"),
        )

        assert validate_strategy(step, "transcript").valid

    def test_an_unknown_organism_scope_is_not_guessed_at(self) -> None:
        """The guard only fires when both sides are known and disjoint;
        otherwise it would block legitimate strategies."""
        step = _intersect(
            "c",
            _taxon("a", "Plasmodium falciparum 3D7"),
            StrategyStepNode(id="b", search_name="GenesByText"),
        )

        assert validate_strategy(step, "transcript").valid

    def test_a_union_across_organisms_is_allowed(self) -> None:
        """UNION across species is meaningful; only INTERSECT is always zero."""
        step = StrategyStepNode(
            id="c",
            search_name="__combine__",
            primary_input=_taxon("a", "Plasmodium falciparum 3D7"),
            secondary_input=_taxon("b", "Toxoplasma gondii ME49"),
            operator=CombineOp.UNION,
        )

        assert validate_strategy(step, "transcript").valid
