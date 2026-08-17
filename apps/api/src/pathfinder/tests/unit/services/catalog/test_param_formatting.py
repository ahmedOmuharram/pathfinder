from __future__ import annotations

from typing import ClassVar

from pathfinder.domain.parameters.values import SinglePickValue
from pathfinder.domain.parameters.wdk_vocab import (
    WDKFilterOntologyTerm,
    WDKTreeBoxVocabNode,
    WDKVocabNodeData,
    WDKVocabTerm,
)
from pathfinder.integrations.veupathdb.wdk_parameters import (
    WDKEnumParam,
    WDKFilterParam,
    WDKParameter,
    WDKStringParam,
)
from pathfinder.services.catalog.param_formatting import (
    ParameterInfo,
    format_param_info_typed,
    format_typed_param,
)
from pathfinder.services.catalog.vocab_rendering import _MAX_VOCAB_ENTRIES


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

    Naming the wrong context when the read inherited a bound
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
        assert "No parent value was supplied" not in info.note

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
        assert "No parent value was supplied" in info.note

    def test_ignores_context_for_parents_this_param_does_not_have(self) -> None:
        info = format_typed_param(
            self._samples(),
            self._DEPENDS,
            {},
            applied_context={"organism": SinglePickValue(value="P. falciparum")},
        )

        assert info.note is not None
        assert "No parent value was supplied" in info.note


class TestRequiredFollowsBothWdkSignals:
    """WDK marks a parameter mandatory with allowEmptyValue or minSelectedCount."""

    @staticmethod
    def _param(*, allow_empty: bool, min_selected: int) -> WDKEnumParam:
        return WDKEnumParam.model_validate(
            {
                "name": "organism",
                "type": "multi-pick-vocabulary",
                "allowEmptyValue": allow_empty,
                "minSelectedCount": min_selected,
            }
        )

    def test_a_minimum_selection_makes_a_param_required(self) -> None:
        param = self._param(allow_empty=True, min_selected=1)

        assert format_typed_param(param, {}, {}).required is True

    def test_an_empty_value_is_allowed_when_nothing_must_be_selected(self) -> None:
        param = self._param(allow_empty=True, min_selected=0)

        assert format_typed_param(param, {}, {}).required is False

    def test_forbidding_an_empty_value_is_enough_on_its_own(self) -> None:
        param = self._param(allow_empty=False, min_selected=0)

        assert format_typed_param(param, {}, {}).required is True


def _vocab_term(code: str, display: str) -> WDKVocabTerm:
    return WDKVocabTerm((code, display, None))


_PHYLETIC_TERMS = [
    _vocab_term("ALL", "Root"),
    _vocab_term("EUKA", "Eukaryota"),
    _vocab_term("MAMM", "Mammalia"),
    _vocab_term("hsap", "Homo sapiens REF"),
    _vocab_term("pfal", "Plasmodium falciparum 3D7"),
]
_PHYLETIC_INDENTS = [
    _vocab_term("EUKA", "1"),
    _vocab_term("MAMM", "2"),
    _vocab_term("hsap", "3"),
    _vocab_term("pfal", "2"),
]

_PHYLETIC_HELP_SENTENCE = (
    "Species or clade codes from the phyletic tree, comma-separated or a list; "
    "a clade selects all of its species; profile_pattern is derived from these "
    "two lists."
)


class TestThePhyleticListsCarryTheTree:
    """``GenesByOrthologPattern`` states its criterion on two free-text lists.

    The lists are the proposal, so the sheet must show the vocabulary they take.
    """

    @staticmethod
    def _params(*, with_term_map: bool = True) -> list[WDKParameter]:
        params: list[WDKParameter] = [
            WDKStringParam(
                name="profile_pattern",
                display_name="Phyletic Pattern",
                is_visible=False,
                initial_display_value="hsap=1T",
            ),
            WDKStringParam(
                name="included_species",
                display_name="Included Species",
                help="For documentation only.",
                allow_empty_value=True,
                initial_display_value="",
            ),
            WDKStringParam(
                name="excluded_species",
                display_name="Excluded Species",
                allow_empty_value=True,
                initial_display_value="",
            ),
            WDKEnumParam(
                name="phyletic_indent_map",
                display_name="Indent Map",
                type="multi-pick-vocabulary",
                vocabulary=_PHYLETIC_INDENTS,
            ),
            WDKEnumParam(
                name="organism",
                display_name="Organism",
                type="multi-pick-vocabulary",
                vocabulary=WDKTreeBoxVocabNode(
                    data=WDKVocabNodeData(term="root", display="root"),
                    children=[
                        WDKTreeBoxVocabNode(
                            data=WDKVocabNodeData(
                                term="P. falciparum 3D7", display="P. falciparum 3D7"
                            )
                        )
                    ],
                ),
            ),
        ]
        if with_term_map:
            params.append(
                WDKEnumParam(
                    name="phyletic_term_map",
                    display_name="Term Map",
                    type="multi-pick-vocabulary",
                    vocabulary=_PHYLETIC_TERMS,
                )
            )
        return params

    @classmethod
    def _sheet(cls, *, with_term_map: bool = True) -> dict[str, ParameterInfo]:
        infos = format_param_info_typed(cls._params(with_term_map=with_term_map))
        return {info.name: info for info in infos}

    def test_both_lists_take_the_species_and_clade_codes(self) -> None:
        sheet = self._sheet()

        for name in ("included_species", "excluded_species"):
            codes = [option.value for option in sheet[name].vocabulary()]
            assert "pfal" in codes
            assert "MAMM" in codes

    def test_the_synthetic_root_is_not_a_choice(self) -> None:
        sheet = self._sheet()

        assert all(o.value != "ALL" for o in sheet["included_species"].vocabulary())

    def test_the_codes_carry_their_species_names(self) -> None:
        options = {
            o.value: o.display for o in self._sheet()["excluded_species"].vocabulary()
        }

        assert options["hsap"] == "Homo sapiens REF"

    def test_the_help_ends_by_naming_the_derivation(self) -> None:
        sheet = self._sheet()

        assert sheet["included_species"].help.endswith(_PHYLETIC_HELP_SENTENCE)
        assert sheet["included_species"].help.startswith("For documentation only.")
        assert sheet["excluded_species"].help == _PHYLETIC_HELP_SENTENCE

    def test_the_codes_reach_the_wire_through_allowed_values(self) -> None:
        # ``vocab_leaves`` is excluded from serialization, so a tool result that
        # sends only ``allowed_values`` would show the model an empty vocabulary.
        allowed = self._sheet()["included_species"].allowed_values

        assert allowed is not None
        assert [o.value for o in allowed] == ["EUKA", "MAMM", "hsap", "pfal"]

    def test_the_lists_are_optional_the_way_wdk_declares_them(self) -> None:
        assert self._sheet()["included_species"].required is False
        assert self._sheet()["included_species"].default_value == ""

    def test_the_pattern_stays_off_the_visible_sheet(self) -> None:
        assert self._sheet()["profile_pattern"].is_visible is False

    def test_the_two_maps_are_dropped(self) -> None:
        sheet = self._sheet()

        assert "phyletic_term_map" not in sheet
        assert "phyletic_indent_map" not in sheet

    def test_another_search_leaves_the_lists_alone(self) -> None:
        sheet = self._sheet(with_term_map=False)

        assert sheet["included_species"].vocabulary() == []
        assert sheet["included_species"].help == "For documentation only."

    def test_the_other_params_keep_their_own_vocabulary(self) -> None:
        codes = [o.value for o in self._sheet()["organism"].vocabulary()]

        assert codes == ["root", "P. falciparum 3D7"]


class TestTheFullTreeSurvivesTheWireCap:
    """The live tree is hundreds of nodes. The wire view is capped; matching is not."""

    _LEAF_COUNT = _MAX_VOCAB_ENTRIES + 11

    @classmethod
    def _big_sheet(cls) -> ParameterInfo:
        terms = [_vocab_term("ALL", "Root"), _vocab_term("EUKA", "Eukaryota")]
        indents = [_vocab_term("EUKA", "1")]
        for i in range(cls._LEAF_COUNT):
            terms.append(_vocab_term(f"sp{i:02d}", f"Species {i}"))
            indents.append(_vocab_term(f"sp{i:02d}", "2"))
        params: list[WDKParameter] = [
            WDKStringParam(name="profile_pattern", is_visible=False),
            WDKStringParam(name="included_species", allow_empty_value=True),
            WDKStringParam(name="excluded_species", allow_empty_value=True),
            WDKEnumParam(
                name="phyletic_term_map",
                type="multi-pick-vocabulary",
                vocabulary=terms,
            ),
            WDKEnumParam(
                name="phyletic_indent_map",
                type="multi-pick-vocabulary",
                vocabulary=indents,
            ),
        ]
        infos = {info.name: info for info in format_param_info_typed(params)}
        return infos["included_species"]

    def test_the_wire_view_is_capped(self) -> None:
        allowed = self._big_sheet().allowed_values

        assert allowed is not None
        assert len(allowed) == _MAX_VOCAB_ENTRIES

    def test_the_note_says_the_list_was_truncated(self) -> None:
        note = self._big_sheet().allowed_values_note

        assert note is not None
        assert str(_MAX_VOCAB_ENTRIES) in note

    def test_matching_still_sees_every_node(self) -> None:
        # The clade plus every species, uncapped, so a value the cap hid still binds.
        assert len(self._big_sheet().vocabulary()) == self._LEAF_COUNT + 1
