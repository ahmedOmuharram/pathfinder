from pathfinder.domain.parameters.values import ParamValue, SinglePickValue
from pathfinder.services.strategies.kind_validation import _validate_contrast_samples


def _samples(**kv: str) -> dict[str, ParamValue]:
    return {name: SinglePickValue(value=value) for name, value in kv.items()}


def test_identical_deseq_ref_comp_samples_rejected() -> None:
    # A DESeq contrast of a group against itself -> 0 DE genes. The guard must
    # catch the ``samples_de_*`` variant, not only fold-change ``samples_fc_*``.
    err = _validate_contrast_samples(
        "GenesByRNASeqDESeq",
        _samples(
            samples_de_ref_generic_deseq="Male gametocytes",
            samples_de_comp_generic_deseq="Male gametocytes",
        ),
    )
    assert err is not None
    assert "identical" in err.message.lower()


def test_distinct_deseq_ref_comp_samples_ok() -> None:
    err = _validate_contrast_samples(
        "GenesByRNASeqDESeq",
        _samples(
            samples_de_ref_generic_deseq="Female gametocytes",
            samples_de_comp_generic_deseq="Male gametocytes",
        ),
    )
    assert err is None


def test_identical_fold_change_ref_comp_still_rejected() -> None:
    err = _validate_contrast_samples(
        "GenesByFoldChange",
        _samples(
            samples_fc_ref_generic="Trophozoite",
            samples_fc_comp_generic="Trophozoite",
        ),
    )
    assert err is not None
