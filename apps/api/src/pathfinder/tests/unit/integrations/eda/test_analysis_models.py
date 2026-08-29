from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from pathfinder.integrations.eda.models import (
    ANALYSIS_DESCRIPTION_BYTES,
    ANALYSIS_DISPLAY_NAME_BYTES,
    EdaAnalysisDescriptor,
    EdaAnalysisRename,
    EdaComparator,
    EdaComputation,
    EdaComputationDescriptor,
    EdaDifferentialExpressionConfig,
    EdaLabeledRange,
    EdaNewAnalysis,
    EdaStringSetFilter,
    EdaSubsetDescriptor,
    EdaVariableSpec,
    EdaVisualization,
    EdaVolcanoConfiguration,
    EdaVolcanoDescriptor,
)


def _config() -> EdaDifferentialExpressionConfig:
    return EdaDifferentialExpressionConfig(
        identifier_variable=EdaVariableSpec(
            entity_id="ENT_fd574cd6", variable_id="VEUPATHDB_GENE_ID"
        ),
        value_variable=EdaVariableSpec(
            entity_id="ENT_fd574cd6", variable_id="SEQUENCE_READ_COUNT_ANTISENSE"
        ),
        comparator=EdaComparator(
            variable=EdaVariableSpec(
                entity_id="ENT_8151325d", variable_id="VAR_081ab087"
            ),
            group_a=[EdaLabeledRange(label="normal")],
            group_b=[EdaLabeledRange(label="febrile")],
        ),
    )


def test_study_id_holds_a_dataset_id_and_keeps_the_upstream_name() -> None:
    analysis = EdaNewAnalysis(study_id="DS_e973eadd57", display_name="probe")
    dumped = analysis.model_dump(by_alias=True, exclude_none=True)
    assert dumped["studyId"] == "DS_e973eadd57"
    assert "datasetId" not in dumped


def test_a_long_display_name_is_cut_to_the_upstream_bound() -> None:
    """The user service refuses a displayName over 50 UTF-8 bytes."""
    purpose = (
        "Febrile versus normal differential expression in the LRR5 and DHC "
        "heat-shock RNA-seq study"
    )
    assert len(purpose) == 90
    analysis = EdaNewAnalysis(study_id="DS_e973eadd57", display_name=purpose)
    sent = analysis.model_dump(by_alias=True)["displayName"]
    assert sent == "Febrile versus normal differential expression in t"
    assert len(sent.encode()) == ANALYSIS_DISPLAY_NAME_BYTES


def test_a_display_name_cut_never_splits_a_multibyte_character() -> None:
    """A cut in the middle of a character drops it, so the name stays UTF-8."""
    name = f"{'a' * 48}→{'b' * 9}"
    assert len(name.encode()) == 60
    sent = EdaNewAnalysis(study_id="DS_x", display_name=name).display_name
    assert sent == "a" * 48
    assert len(sent.encode()) <= ANALYSIS_DISPLAY_NAME_BYTES
    assert sent.encode().decode() == sent


def test_a_display_name_within_the_bound_is_untouched() -> None:
    name = "a" * 49
    assert len(name.encode()) == 49
    assert EdaNewAnalysis(study_id="DS_x", display_name=name).display_name == name


def test_a_long_description_is_cut_to_the_upstream_bound() -> None:
    """The same route caps description at 4000 UTF-8 bytes."""
    analysis = EdaNewAnalysis(
        study_id="DS_x", display_name="probe", description="d" * 4100
    )
    assert len(analysis.description.encode()) == ANALYSIS_DESCRIPTION_BYTES


def test_a_rename_carries_the_cut_name_on_the_wire() -> None:
    purpose = "Febrile versus normal differential expression in the LRR5 study"
    rename = EdaAnalysisRename(display_name=purpose)
    sent = rename.model_dump(by_alias=True)["displayName"]
    assert len(sent.encode()) == ANALYSIS_DISPLAY_NAME_BYTES


def test_derived_variables_hold_ids_not_specs() -> None:
    descriptor = EdaAnalysisDescriptor(derived_variables=["dv-abc-123"])
    assert descriptor.model_dump(by_alias=True)["derivedVariables"] == ["dv-abc-123"]


def test_a_derived_variable_spec_object_is_refused() -> None:
    """An inline object in that array is a 422 upstream."""
    with pytest.raises(ValidationError):
        EdaAnalysisDescriptor.model_validate(
            {"derivedVariables": [{"entityId": "E", "variableId": "V"}]}
        )


def test_an_empty_analysis_serializes_the_full_descriptor_skeleton() -> None:
    analysis = EdaNewAnalysis(study_id="DS_x", display_name="x")
    dumped = analysis.model_dump(by_alias=True, exclude_none=True)
    assert dumped["descriptor"] == {
        "subset": {"descriptor": [], "uiSettings": {}},
        "computations": [],
        "starredVariables": [],
        "dataTableConfig": {},
        "derivedVariables": [],
    }


def test_the_bridge_spec_round_trips_byte_for_byte() -> None:
    """The recorded spec of the measured 202-then-200 sequence."""
    analysis = EdaNewAnalysis(
        study_id="DS_e973eadd57",
        display_name="...",
        description="",
        is_public=False,
        descriptor=EdaAnalysisDescriptor(
            subset=EdaSubsetDescriptor(),
            computations=[
                EdaComputation(
                    computation_id="de2",
                    descriptor=EdaComputationDescriptor(configuration=_config()),
                    visualizations=[
                        EdaVisualization(
                            visualization_id="v2",
                            display_name="Volcano",
                            descriptor=EdaVolcanoDescriptor(
                                configuration=EdaVolcanoConfiguration(
                                    effect_size_threshold=1.0,
                                    significance_threshold=0.05,
                                ),
                            ),
                        )
                    ],
                )
            ],
        ),
    )
    dumped = json.loads(analysis.model_dump_json(by_alias=True, exclude_none=True))
    computation = dumped["descriptor"]["computations"][0]
    assert computation["descriptor"]["type"] == "differentialexpression"
    assert (
        computation["descriptor"]["configuration"]["differentialExpressionMethod"]
        == "DESeq"
    )
    assert computation["descriptor"]["configuration"]["pValueFloor"] == "1e-200"
    viz = computation["visualizations"][0]["descriptor"]
    assert viz["type"] == "volcanoplot"
    assert viz["configuration"]["effectSizeThreshold"] == 1.0
    assert viz["configuration"]["significanceThreshold"] == 0.05
    assert viz["configuration"]["effectDirection"] == "upAndDown"


def test_deseq2_is_not_a_wire_value() -> None:
    """The frontend display name is DESeq2; the wire enum is DESeq."""
    with pytest.raises(ValidationError):
        EdaDifferentialExpressionConfig.model_validate(
            {
                "identifierVariable": {"entityId": "E", "variableId": "V"},
                "valueVariable": {"entityId": "E", "variableId": "W"},
                "comparator": {
                    "variable": {"entityId": "P", "variableId": "C"},
                    "groupA": [{"label": "a"}],
                    "groupB": [{"label": "b"}],
                },
                "differentialExpressionMethod": "DESeq2",
            }
        )


def test_a_labeled_range_may_carry_a_label_alone() -> None:
    group = EdaLabeledRange.model_validate({"label": "normal"})
    assert group.min is None
    assert group.max is None
    assert group.model_dump(by_alias=True, exclude_none=True) == {"label": "normal"}


def test_a_comparator_group_may_not_be_empty() -> None:
    with pytest.raises(ValidationError):
        EdaComparator.model_validate(
            {
                "variable": {"entityId": "P", "variableId": "C"},
                "groupA": [],
                "groupB": [{"label": "b"}],
            }
        )


def test_a_subset_descriptor_holds_the_typed_filter_array() -> None:
    subset = EdaSubsetDescriptor.model_validate(
        {
            "descriptor": [
                {
                    "entityId": "GENE_PHENOTYPE_DATA_ENTITY",
                    "variableId": "VAR_035294d0",
                    "type": "stringSet",
                    "stringSet": ["P. berghei"],
                }
            ],
            "uiSettings": {},
        }
    )
    assert isinstance(subset.descriptor[0], EdaStringSetFilter)
