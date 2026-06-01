from pathfinder.domain.parameters.specs import ParamSpecNormalized
from pathfinder.domain.parameters.wdk_vocab import WDKVocabTerm
from pathfinder.services.catalog.param_formatting import (
    format_normalized_param_info,
)


def test_format_normalized_param_info_emits_vocab_and_dependency_links() -> None:
    organism_vocab = [
        WDKVocabTerm(("Pf3D7", "P. falciparum 3D7", None)),
        WDKVocabTerm(("PvP01", "P. vivax P01", None)),
    ]
    taxon_vocab = [
        WDKVocabTerm(("PfTaxonA", "Pf Taxon A", None)),
        WDKVocabTerm(("PfTaxonB", "Pf Taxon B", None)),
    ]
    specs: dict[str, ParamSpecNormalized] = {
        "organism": ParamSpecNormalized(
            name="organism",
            param_type="single-pick-vocabulary",
            allow_empty_value=False,
            vocabulary=organism_vocab,
            dependent_params=("taxon",),
        ),
        "taxon": ParamSpecNormalized(
            name="taxon",
            param_type="single-pick-vocabulary",
            allow_empty_value=False,
            vocabulary=taxon_vocab,
        ),
    }

    formatted = format_normalized_param_info(specs)
    by_name = {p.name: p for p in formatted}

    assert by_name["organism"].required is True
    assert by_name["organism"].controls_vocab_of == ["taxon"]
    assert by_name["organism"].vocab_depends_on is None

    taxon = by_name["taxon"]
    assert taxon.vocab_depends_on == ["organism"]
    assert taxon.allowed_values is not None
    values = sorted(v.value for v in taxon.allowed_values)
    assert values == ["PfTaxonA", "PfTaxonB"]


def test_format_normalized_param_info_truncates_large_vocab() -> None:
    huge_vocab = [WDKVocabTerm((f"v{i}", f"v{i}", None)) for i in range(200)]
    specs = {
        "p": ParamSpecNormalized(
            name="p",
            param_type="single-pick-vocabulary",
            vocabulary=huge_vocab,
        ),
    }
    formatted = format_normalized_param_info(specs)
    assert formatted[0].allowed_values is not None
    assert len(formatted[0].allowed_values) == 50
    assert formatted[0].allowed_values_note is not None
    assert "truncated" in formatted[0].allowed_values_note.lower()
