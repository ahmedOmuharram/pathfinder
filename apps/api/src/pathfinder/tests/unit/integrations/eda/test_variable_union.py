from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from pathfinder.integrations.eda.models import (
    EdaCategoryVariable,
    EdaCollection,
    EdaEntity,
    EdaLongitudeVariable,
    EdaNumberVariable,
    EdaStringVariable,
    EdaStudyDetailResponse,
    EdaVariable,
)

FIXTURES = Path(__file__).parent / "fixtures"
VARIABLE = TypeAdapter(EdaVariable)


def test_type_discriminates_a_string_variable() -> None:
    parsed = VARIABLE.validate_python(
        {
            "id": "VAR_035294d0",
            "parentId": "GENE_PHENOTYPE_DATA_ENTITY",
            "providerLabel": "No Provider Label available",
            "displayName": "Species",
            "displayType": "default",
            "type": "string",
            "hideFrom": [],
            "dataShape": "categorical",
            "vocabulary": ["P. berghei", "P. falciparum", "P. yoelii"],
            "distinctValuesCount": 3,
            "isMultiValued": True,
        }
    )
    assert isinstance(parsed, EdaStringVariable)
    assert parsed.is_multi_valued is True
    assert parsed.vocabulary == ["P. berghei", "P. falciparum", "P. yoelii"]


def test_a_category_variable_carries_no_value_fields() -> None:
    parsed = VARIABLE.validate_python(
        {
            "id": "EUPATH_0000321",
            "parentId": "EUPATH_0000308",
            "providerLabel": "No Provider Label available",
            "displayName": "Diagnosis at discharge",
            "displayType": "multifilter",
            "displayOrder": 4,
            "type": "category",
            "hideFrom": [],
        }
    )
    assert isinstance(parsed, EdaCategoryVariable)
    assert not hasattr(parsed, "vocabulary")
    assert not hasattr(parsed, "data_shape")


def test_is_category_is_not_modelled() -> None:
    """Declared required in the RAML, absent on all 66664 variables scanned."""
    parsed = VARIABLE.validate_python(
        {
            "id": "V",
            "displayName": "v",
            "providerLabel": "p",
            "displayType": "default",
            "type": "category",
            "hideFrom": [],
            "isCategory": "true",
        }
    )
    assert not hasattr(parsed, "is_category")


def test_distribution_defaults_carry_only_three_of_six_keys() -> None:
    parsed = VARIABLE.validate_python(
        {
            "id": "SEQUENCE_READ_COUNT",
            "displayName": "read count",
            "providerLabel": "p",
            "displayType": "default",
            "type": "number",
            "hideFrom": [],
            "dataShape": "continuous",
            "distributionDefaults": {
                "rangeMin": 0,
                "rangeMax": 1684173,
                "binWidth": 54329,
            },
        }
    )
    assert isinstance(parsed, EdaNumberVariable)
    assert parsed.distribution_defaults.display_range_min is None
    assert parsed.distribution_defaults.range_max == 1684173


def test_scale_is_not_modelled() -> None:
    parsed = VARIABLE.validate_python(
        {
            "id": "V",
            "displayName": "v",
            "providerLabel": "p",
            "displayType": "default",
            "type": "number",
            "hideFrom": [],
            "scale": "log2",
        }
    )
    assert not hasattr(parsed, "scale")


def test_longitude_is_its_own_type() -> None:
    parsed = VARIABLE.validate_python(
        {
            "id": "OBI_0001621",
            "displayName": "longitude",
            "providerLabel": "p",
            "displayType": "longitude",
            "type": "longitude",
            "hideFrom": [],
            "precision": 1.0,
        }
    )
    assert isinstance(parsed, EdaLongitudeVariable)


def test_an_unknown_variable_type_is_refused() -> None:
    with pytest.raises(ValidationError):
        VARIABLE.validate_python(
            {
                "id": "V",
                "displayName": "v",
                "providerLabel": "p",
                "displayType": "default",
                "type": "geoaggregator",
                "hideFrom": [],
            }
        )


def test_the_entity_tree_is_recursive_and_children_are_optional() -> None:
    raw = json.loads((FIXTURES / "study_detail_de.json").read_text())
    detail = EdaStudyDetailResponse.model_validate(raw).study
    root = detail.root_entity
    assert root.id_column_name.endswith("_stable_id")
    assert root.children, "the DE study has a child counts entity"
    leaf = root.children[0]
    assert leaf.children == []
    assert isinstance(leaf, EdaEntity)


def test_normalization_method_null_is_a_string_value_not_absence() -> None:
    collection = EdaCollection.model_validate(
        {
            "id": "EUPATH_0005051",
            "displayName": "Eigengene",
            "type": "number",
            "dataShape": "continuous",
            "memberVariableIds": ["VAR_a", "VAR_b"],
            "imputeZero": False,
            "normalizationMethod": "NULL",
            "isCompositional": False,
            "isProportion": False,
            "member": "eigengene",
            "memberPlural": "eigengenes",
        }
    )
    assert collection.normalization_method == "NULL"
