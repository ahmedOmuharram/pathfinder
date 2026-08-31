"""The ledger must show which way a differential contrast points.

An inverted contrast (reference and comparator swapped) returns a plausible,
non-empty gene set that is confidently the wrong biology. Unlike a zero-result
bug there is nothing to notice, so the direction has to be visible rather than
buried in a parameter dict the UI never renders.
"""

from __future__ import annotations

from pathfinder.ai.lead.ledger_sections import FrameSection
from pathfinder.domain.parameters.values import MultiPickValue, SinglePickValue
from pathfinder.domain.strategy.operational_spec import Criterion, OperationalSpec


def _fold_change_criterion(
    *, comparator: str, reference: str, direction: str
) -> Criterion:
    return Criterion(
        id="female_enrichment",
        text="genes enriched in female adults",
        search_name="GenesByMicroarray_GSE22339_male_vs_female_RSRC",
        resolved_params={
            "samples_fc_comp_generic": MultiPickValue(values=[comparator]),
            "samples_fc_ref_generic": MultiPickValue(values=[reference]),
            "regulated_dir": SinglePickValue(value=direction),
            "protein_coding_only": SinglePickValue(value="yes"),
        },
    )


def _section(*criteria: Criterion) -> FrameSection:
    return FrameSection(spec=OperationalSpec(criteria=list(criteria)))


def test_contrast_reports_comparator_reference_and_direction() -> None:
    section = _section(
        _fold_change_criterion(
            comparator="female", reference="male", direction="up-regulated"
        )
    )
    contrasts = section.contrasts
    assert len(contrasts) == 1
    contrast = contrasts[0]
    assert contrast.criterion_id == "female_enrichment"
    assert contrast.comparator == "female"
    assert contrast.reference == "male"
    assert contrast.direction == "up-regulated"


def test_contrast_summary_reads_the_way_a_biologist_states_it() -> None:
    section = _section(
        _fold_change_criterion(
            comparator="female", reference="male", direction="up-regulated"
        )
    )
    assert section.contrasts[0].summary == "up-regulated in female vs male"


def test_an_inverted_contrast_reads_differently_so_it_can_be_spotted() -> None:
    inverted = _section(
        _fold_change_criterion(
            comparator="male", reference="female", direction="up-regulated"
        )
    )
    assert inverted.contrasts[0].summary == "up-regulated in male vs female"


def test_criteria_without_a_contrast_pair_are_not_reported() -> None:
    plain = Criterion(
        id="obp",
        text="odorant binding proteins",
        search_name="GenesByText",
        resolved_params={"text_expression": SinglePickValue(value="odorant binding")},
    )
    assert _section(plain).contrasts == []


def test_a_half_bound_contrast_still_surfaces_what_is_known() -> None:
    """A reference still awaiting an answer must not hide the comparator -- that
    is exactly when a user needs to see which way the contrast is pointing."""
    half = Criterion(
        id="c",
        text="t",
        search_name="S",
        resolved_params={
            "samples_fc_comp_generic": MultiPickValue(values=["female"]),
            "regulated_dir": SinglePickValue(value="up-regulated"),
        },
    )
    contrast = _section(half).contrasts[0]
    assert contrast.comparator == "female"
    assert contrast.reference is None
    assert contrast.summary == "up-regulated in female vs (unset)"


def test_no_spec_means_no_contrasts() -> None:
    assert FrameSection().contrasts == []
