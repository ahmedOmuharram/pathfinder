from pathfinder.domain.parameters.specs import ParamSpecNormalized
from pathfinder.platform.types import JSONArray
from pathfinder.services.catalog.param_formatting import (
    format_normalized_param_info,
)


def test_format_normalized_param_info_emits_vocab_and_dependency_links() -> None:
    organism_vocab: JSONArray = [["Pf3D7", "P. falciparum 3D7"], ["PvP01", "P. vivax P01"]]
    taxon_vocab: JSONArray = [["PfTaxonA", "Pf Taxon A"], ["PfTaxonB", "Pf Taxon B"]]
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
    huge_vocab: JSONArray = [[f"v{i}", f"v{i}"] for i in range(200)]
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
