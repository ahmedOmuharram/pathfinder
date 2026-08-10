from __future__ import annotations

from typing import ClassVar

from pathfinder.domain.parameters.values import SinglePickValue
from pathfinder.domain.parameters.wdk_vocab import (
    WDKFilterOntologyTerm,
    WDKTreeBoxVocabNode,
    WDKVocabNodeData,
)
from pathfinder.integrations.veupathdb.wdk_parameters import (
    WDKEnumParam,
    WDKFilterParam,
)
from pathfinder.services.catalog.param_formatting import (
    ParameterInfo,
    format_typed_param,
)


def _pi(param_type: str) -> ParameterInfo:
    return ParameterInfo(
        name="p",
        display_name="P",
        type=param_type,
        required=True,
        is_visible=True,
        help="",
        value_format="",
    )


def test_param_kind_narrows_type_to_typed_paramkind() -> None:
    assert _pi("multi-pick-vocabulary").param_kind == "multi-pick-vocabulary"
    assert _pi("single-pick-vocabulary").param_kind == "single-pick-vocabulary"
    assert _pi("number").param_kind == "number"
    assert _pi("input-dataset").param_kind == "input-dataset"


def test_param_kind_falls_back_to_string_for_unknown_type() -> None:
    # The discriminator field `kind` must NOT be mistaken for the param kind.
    pi = _pi("SomeUnnormalizedWdkType")
    assert pi.kind == "parameter_info"
    assert pi.param_kind == "string"


def test_filter_param_exposes_selectable_leaf_facets() -> None:
    # Mirrors live plasmodb ngsSnp_strain_meta: category nodes carry type=None
    # (not selectable); leaf facets carry a type + their valid values.
    param = WDKFilterParam(
        name="ngsSnp_strain_meta",
        display_name="Set of Samples",
        ontology=[
            WDKFilterOntologyTerm(
                term="Sample collection", display="Sample collection"
            ),
            WDKFilterOntologyTerm(
                term="Sample type", display="Sample type", type="string"
            ),
            WDKFilterOntologyTerm(term="Country", display="Country", type="string"),
        ],
        values={
            "Sample type": ["specimen from organism", "culture", "blood"],
            "Country": ["India", "Thailand"],
        },
    )

    info = format_typed_param(param, {}, {})

    assert info.param_kind == "filter"
    fields = {f.term: f for f in info.filter_fields}
    assert set(fields) == {"Sample type", "Country"}  # category node excluded
    assert fields["Sample type"].type == "string"
    assert fields["Sample type"].is_range is False
    assert fields["Sample type"].values == [
        "specimen from organism",
        "culture",
        "blood",
    ]
    assert fields["Country"].values == ["India", "Thailand"]


class TestDependentParamNote:
    """The note must say which parent values produced the list it accompanies.

    Saying "default context only" when the read actually inherited a bound
    parent is a lie about provenance, and the model has no way to detect it: it
    sees a plausible list of 46 time points either way.
    """

    @staticmethod
    def _samples() -> WDKEnumParam:
        return WDKEnumParam(
            name="samples_percentile_generic",
            display_name="Samples",
            type="multi-pick-vocabulary",
            vocabulary=WDKTreeBoxVocabNode(
                data=WDKVocabNodeData(term="root", display="root"),
                children=[
                    WDKTreeBoxVocabNode(
                        data=WDKVocabNodeData(term="20 Hour", display="20 Hour")
                    )
                ],
            ),
        )

    _DEPENDS: ClassVar[dict[str, list[str]]] = {
        "samples_percentile_generic": ["profileset_generic"]
    }

    def test_names_the_applied_parent_value(self) -> None:
        info = format_typed_param(
            self._samples(),
            self._DEPENDS,
            {},
            applied_context={
                "profileset_generic": SinglePickValue(value="DeRisi 3D7 Smoothed")
            },
        )

        assert info.note is not None
        assert "DeRisi 3D7 Smoothed" in info.note

    def test_does_not_claim_default_context_when_one_was_applied(self) -> None:
        info = format_typed_param(
            self._samples(),
            self._DEPENDS,
            {},
            applied_context={
                "profileset_generic": SinglePickValue(value="DeRisi 3D7 Smoothed")
            },
        )

        assert info.note is not None
        assert "default context" not in info.note

    def test_warns_that_another_parent_yields_another_list(self) -> None:
        info = format_typed_param(
            self._samples(),
            self._DEPENDS,
            {},
            applied_context={
                "profileset_generic": SinglePickValue(value="DeRisi 3D7 Smoothed")
            },
        )

        assert info.note is not None
        assert "DIFFERENT" in info.note

    def test_falls_back_to_the_default_context_wording(self) -> None:
        info = format_typed_param(self._samples(), self._DEPENDS, {})

        assert info.note is not None
        assert "default context" in info.note

    def test_ignores_context_for_parents_this_param_does_not_have(self) -> None:
        info = format_typed_param(
            self._samples(),
            self._DEPENDS,
            {},
            applied_context={"organism": SinglePickValue(value="P. falciparum")},
        )

        assert info.note is not None
        assert "default context" in info.note
