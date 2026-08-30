"""Acceptance: the EDA services, the pure predicates, and the volcano cut.

Values come from the live-verified EDA knowledge bundle. Fixtures are inline.
"""

from __future__ import annotations

import json
import random
from collections.abc import Iterator
from dataclasses import dataclass, field

import httpx
import pytest
from pydantic import ValidationError

from pathfinder.platform.context import veupathdb_auth_token_ctx

eda_models = pytest.importorskip("pathfinder.integrations.eda.models")
eda_client = pytest.importorskip("pathfinder.integrations.eda.client")
domain = pytest.importorskip("pathfinder.domain.eda")
authoring = pytest.importorskip("pathfinder.services.eda.authoring")
catalog = pytest.importorskip("pathfinder.services.eda.catalog")
compute = pytest.importorskip("pathfinder.services.eda.compute")
eda_backed = pytest.importorskip("pathfinder.services.catalog.eda_backed")
wdk_vocab = pytest.importorskip("pathfinder.domain.parameters.wdk_vocab")

pytestmark = [pytest.mark.eda_acceptance]

_ENTITY = "GENE_PHENOTYPE_DATA_ENTITY"
_SPECIES = "VAR_035294d0"


# --------------------------------------------------------------------------
# Structural facts the domain Protocols accept. The domain layer imports no
# integration model, so an acceptance test builds the shapes it walks.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Var:
    id: str
    type: str = "string"
    display_name: str = ""
    display_type: str = "default"
    parent_id: str | None = None
    vocabulary: list[str] | None = None
    is_multi_valued: bool = False
    data_shape: str | None = None


@dataclass(frozen=True)
class Ent:
    id: str
    display_name: str = ""
    variables: list[Var] = field(default_factory=list)
    children: list["Ent"] = field(default_factory=list)


@dataclass(frozen=True)
class Study:
    id: str
    root_entity: Ent


@dataclass(frozen=True)
class Sub:
    variable_id: str
    string_set: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Filt:
    entity_id: str
    variable_id: str
    type: str
    string_set: list[str] = field(default_factory=list)
    number_set: list[float] = field(default_factory=list)
    date_set: list[str] = field(default_factory=list)
    min: float | str | None = None
    max: float | str | None = None
    left: float | None = None
    right: float | None = None
    operation: str = "union"
    sub_filters: list[Sub] = field(default_factory=list)


def _phenotype_study() -> Study:
    return Study(
        id="STUDY_53f554ec6a",
        root_entity=Ent(
            id=_ENTITY,
            display_name="Gene phenotype",
            variables=[
                Var(
                    id=_SPECIES,
                    type="string",
                    display_name="Species",
                    vocabulary=["P. berghei", "P. falciparum", "P. yoelii"],
                    is_multi_valued=True,
                ),
                Var(
                    id="EUPATH_0043064",
                    type="integer",
                    display_name="Read count",
                    data_shape="continuous",
                ),
                Var(
                    id="EUPATH_0043256",
                    type="date",
                    display_name="Collection date",
                    vocabulary=["2017-05-05", "2017-05-11"],
                ),
                Var(id="VEUPATHDB_GENE_ID", type="string", display_name="Gene"),
                Var(
                    id="CAT_1",
                    type="category",
                    display_name="Diagnosis",
                    display_type="multifilter",
                ),
                Var(
                    id="CHILD_1",
                    type="string",
                    display_name="Malaria",
                    parent_id="CAT_1",
                    vocabulary=["Yes"],
                ),
            ],
        ),
    )


# --------------------------------------------------------------------------
# serialize_spec and EdaStepRequest
# --------------------------------------------------------------------------


def _species_filter() -> object:
    return eda_models.EdaStringSetFilter(
        entity_id=_ENTITY, variable_id=_SPECIES, string_set=["P. berghei"]
    )


def _no_nulls(node: object) -> bool:
    match node:
        case dict():
            return all(v is not None and _no_nulls(v) for v in node.values())
        case list():
            return all(_no_nulls(v) for v in node)
        case _:
            return True


def test_an_analysis_with_no_filters_serializes_to_the_empty_string() -> None:
    """The plugin synthesizes an empty descriptor; the literal {} is not it."""
    analysis = authoring.new_analysis(
        dataset_id="DS_53f554ec6a", display_name="empty probe"
    )
    assert authoring.serialize_spec(analysis) == ""


def test_a_one_filter_analysis_serializes_the_dataset_id_and_the_filter() -> None:
    analysis = authoring.new_analysis(
        dataset_id="DS_53f554ec6a",
        display_name="berghei subset",
        filters=[_species_filter()],
    )
    parsed = json.loads(authoring.serialize_spec(analysis))
    assert parsed["studyId"] == "DS_53f554ec6a"
    assert parsed["descriptor"]["subset"]["descriptor"][0] == {
        "entityId": _ENTITY,
        "variableId": _SPECIES,
        "type": "stringSet",
        "stringSet": ["P. berghei"],
    }
    assert _no_nulls(parsed)


def test_a_step_request_refuses_a_spec_naming_another_dataset() -> None:
    spec = authoring.serialize_spec(
        authoring.new_analysis(
            dataset_id="DS_53f554ec6a",
            display_name="x",
            filters=[_species_filter()],
        )
    )
    with pytest.raises(ValidationError) as excinfo:
        eda_backed.EdaStepRequest(
            eda_dataset_id="DS_eeca6a5476", eda_analysis_spec=spec
        )
    message = str(excinfo.value)
    assert "DS_eeca6a5476" in message
    assert "DS_53f554ec6a" in message


def test_a_step_request_accepts_the_empty_spec() -> None:
    request = eda_backed.EdaStepRequest(
        eda_dataset_id="DS_53f554ec6a", eda_analysis_spec=""
    )
    assert request.eda_analysis_spec == ""
    assert request.wdk_parameters() == {
        "eda_dataset_id": "DS_53f554ec6a",
        "eda_analysis_spec": "",
    }


# --------------------------------------------------------------------------
# domain/eda.py predicates
# --------------------------------------------------------------------------


def test_an_out_of_vocabulary_value_is_named_in_the_rejection() -> None:
    """Upstream answers 200 with count 0, so this predicate is the only guard."""
    errors = domain.validate_filters(
        _phenotype_study(),
        [
            Filt(
                entity_id=_ENTITY,
                variable_id=_SPECIES,
                type="stringSet",
                string_set=["P. vivax"],
            )
        ],
    )
    assert len(errors) == 1
    assert "P. vivax" in errors[0]
    assert "P. berghei" in errors[0]


def test_a_date_bound_without_a_time_is_named_in_the_rejection() -> None:
    errors = domain.validate_filters(
        _phenotype_study(),
        [
            Filt(
                entity_id=_ENTITY,
                variable_id="EUPATH_0043256",
                type="dateRange",
                min="2017-05-05",
                max="2017-05-11T00:00:00",
            )
        ],
    )
    assert len(errors) == 1
    assert "T00:00:00" in errors[0]


def test_a_number_range_on_a_string_variable_is_refused() -> None:
    errors = domain.validate_filters(
        _phenotype_study(),
        [
            Filt(
                entity_id=_ENTITY,
                variable_id=_SPECIES,
                type="numberRange",
                min=0.0,
                max=1.0,
            )
        ],
    )
    assert len(errors) == 1
    assert _SPECIES in errors[0]


def test_a_well_formed_multi_filter_passes() -> None:
    assert (
        domain.validate_filters(
            _phenotype_study(),
            [
                Filt(
                    entity_id=_ENTITY,
                    variable_id="CAT_1",
                    type="multiFilter",
                    operation="union",
                    sub_filters=[Sub(variable_id="CHILD_1", string_set=["Yes"])],
                )
            ],
        )
        == []
    )


def test_one_gene_id_variable_resolves_the_gene_entity() -> None:
    result = domain.find_gene_entity(_phenotype_study())
    assert result.entity_id == _ENTITY
    assert result.error is None


def test_no_gene_id_variable_is_an_error_naming_the_reserved_id() -> None:
    study = Study(
        id="STUDY_53f554ec6a",
        root_entity=Ent(id=_ENTITY, variables=[Var(id=_SPECIES)]),
    )
    result = domain.find_gene_entity(study)
    assert result.entity_id is None
    assert result.error is not None
    assert "VEUPATHDB_GENE_ID" in result.error


def test_two_gene_id_variables_are_an_error_naming_both_entities() -> None:
    study = Study(
        id="STUDY_fd06cb37d3",
        root_entity=Ent(
            id="ENT_8151325d",
            variables=[Var(id="VEUPATHDB_GENE_ID")],
            children=[Ent(id="ENT_d282b742", variables=[Var(id="VEUPATHDB_GENE_ID")])],
        ),
    )
    result = domain.find_gene_entity(study)
    assert result.entity_id is None
    assert result.error is not None
    assert "ENT_8151325d" in result.error
    assert "ENT_d282b742" in result.error


# --------------------------------------------------------------------------
# The volcano cut
# --------------------------------------------------------------------------

_RETAINED_UP = ["PF3D7_0100200", "PF3D7_0100300", "PF3D7_1133400"]
_RETAINED_DOWN = ["PF3D7_0100400", "PF3D7_1037100"]

_VOLCANO_ROWS: list[dict[str, str]] = [
    # Three rows recorded live on STUDY_e973eadd57, normal against febrile.
    {
        "effectSize": "-0.218035922112735",
        "pValue": "0.350285751849808",
        "adjustedPValue": "0.46960449943855",
        "pointID": "PF3D7_0100100",
    },
    {
        "effectSize": "3.94437533216012",
        "pValue": "1.95781599815607e-05",
        "adjustedPValue": "0.000137772236907279",
        "pointID": "PF3D7_0100200",
    },
    {"effectSize": "-1.49447459261845", "pointID": "PF3D7_MIT04200"},
    # Boundary probes at the pinned thresholds, on real gene ids.
    {"effectSize": "1.0", "pValue": "0.01", "pointID": "PF3D7_0100300"},
    {"effectSize": "-1.0", "pValue": "0.05", "pointID": "PF3D7_0100400"},
    {"effectSize": "5.0", "pValue": "0.06", "pointID": "PF3D7_0100500"},
    {"effectSize": "-0.99", "pValue": "0.001", "pointID": "PF3D7_0507500"},
    {"effectSize": "-2.5", "pValue": "0.004", "pointID": "PF3D7_1037100"},
    {"effectSize": "NA", "pValue": "NA", "pointID": "PF3D7_1116700"},
    {"effectSize": "2.2", "pValue": "0.049", "pointID": "PF3D7_1133400"},
]


def _stats() -> object:
    return eda_models.VolcanoStatsResponse.model_validate(
        {
            "effectSizeLabel": "log2(Fold Change)",
            "pValueFloor": "1e-200",
            "statistics": _VOLCANO_ROWS,
        }
    )


def _ids(
    direction: str, *, effect: float = 1.0, significance: float = 0.05
) -> list[str]:
    return compute.retained_point_ids(
        _stats(),
        effect_size_threshold=effect,
        significance_threshold=significance,
        effect_direction=direction,
    )


def test_the_retained_set_at_one_and_five_hundredths_is_exact() -> None:
    """Both comparisons are inclusive, and the effect test is on the absolute."""
    assert _ids("upAndDown") == [
        "PF3D7_0100200",
        "PF3D7_0100300",
        "PF3D7_0100400",
        "PF3D7_1037100",
        "PF3D7_1133400",
    ]
    assert _ids("upOnly") == _RETAINED_UP
    assert _ids("downOnly") == _RETAINED_DOWN


def test_a_row_with_no_p_value_is_dropped_and_counted() -> None:
    summary = compute.retained_summary(
        _stats(), effect_size_threshold=1.0, significance_threshold=0.05
    )
    assert summary.total_rows == 10
    assert summary.unparseable_rows == 2
    assert summary.retained == 5
    assert summary.retained_up == 3
    assert summary.retained_down == 2
    assert "PF3D7_MIT04200" not in _ids("upAndDown")


def test_raising_the_effect_size_threshold_never_grows_the_retained_set() -> None:
    stats = _stats()
    rng = random.Random(20260828)
    pairs = [(rng.uniform(0.1, 4.0), rng.uniform(0.001, 0.2)) for _ in range(50)]
    for effect, significance in pairs:
        both = set(
            compute.retained_point_ids(
                stats,
                effect_size_threshold=effect,
                significance_threshold=significance,
            )
        )
        stricter = set(
            compute.retained_point_ids(
                stats,
                effect_size_threshold=effect + 0.5,
                significance_threshold=significance,
            )
        )
        up = set(
            compute.retained_point_ids(
                stats,
                effect_size_threshold=effect,
                significance_threshold=significance,
                effect_direction="upOnly",
            )
        )
        down = set(
            compute.retained_point_ids(
                stats,
                effect_size_threshold=effect,
                significance_threshold=significance,
                effect_direction="downOnly",
            )
        )
        assert stricter <= both
        assert up | down == both
        assert up & down == set()


# --------------------------------------------------------------------------
# Dataset resolution
# --------------------------------------------------------------------------

_PERMISSIONS = {
    "perDataset": {
        "DS_53f554ec6a": {
            "studyId": "STUDY_53f554ec6a",
            "sha1Hash": "53f554ec6a4a9a7efebfe58e0303f2c7f84ec907",
            "isUserStudy": False,
            "displayName": "Rodent malaria phenotypes",
            "shortDisplayName": "Rodent phenotypes",
            "description": "Phenotype scores per gene",
            "type": "end-user",
            "actionAuthorization": {
                "studyMetadata": True,
                "subsetting": True,
                "visualizations": True,
                "resultsFirstPage": True,
                "resultsAll": True,
            },
        },
        "DS_eeca6a5476": {
            "studyId": "STUDY_fd06cb37d3",
            "sha1Hash": "fd06cb37d34a9a7efebfe58e0303f2c7f84ec907",
            "isUserStudy": False,
            "displayName": "Dual transcriptomes of malaria-infected Gambian children",
            "shortDisplayName": "Gambian children RNA-Seq",
            "description": "The dataset whose id suffix is not its study's",
            "type": "end-user",
            "actionAuthorization": {
                "studyMetadata": True,
                "subsetting": True,
                "visualizations": True,
                "resultsFirstPage": True,
                "resultsAll": True,
            },
        },
    }
}


@pytest.fixture
def permissions_wired(monkeypatch: pytest.MonkeyPatch) -> Iterator[object]:
    catalog.clear_study_caches()
    instance = eda_client.EdaClient(base_url="https://plasmodb.org/eda")
    instance.install_transport(
        httpx.MockTransport(lambda _r: httpx.Response(200, json=_PERMISSIONS))
    )
    monkeypatch.setattr(catalog, "get_eda_client", lambda _site: instance)
    token = veupathdb_auth_token_ctx.set("token-abc")
    yield instance
    veupathdb_auth_token_ctx.reset(token)
    catalog.clear_study_caches()


@pytest.mark.asyncio
async def test_a_dataset_resolves_to_the_study_id_the_permissions_map_names(
    permissions_wired: object,
) -> None:
    """The suffixes agree for most curated studies and not for all of them."""
    entry = await catalog.resolve_dataset("plasmodb", "DS_eeca6a5476")
    assert entry.study_id == "STUDY_fd06cb37d3"
    await permissions_wired.close()


@pytest.mark.asyncio
async def test_a_dataset_with_no_permission_entry_is_refused_by_name(
    permissions_wired: object,
) -> None:
    with pytest.raises(catalog.UnknownEdaDatasetError) as excinfo:
        await catalog.resolve_dataset("plasmodb", "EDAUD_slI5M0RwIg0Zw")
    assert "EDAUD_slI5M0RwIg0Zw" in str(excinfo.value)
    await permissions_wired.close()


# --------------------------------------------------------------------------
# The upload sentinel
# --------------------------------------------------------------------------


_UPLOAD_DISPLAY = "Upload a Phenotype User Dataset in My Workspace"


def test_a_one_term_upload_vocabulary_is_an_empty_state_not_a_choice() -> None:
    """Running the search with that term is a 400 upstream."""
    vocabulary = [
        wdk_vocab.WDKVocabTerm(("EDAUD_slI5M0RwIg0Zw", _UPLOAD_DISPLAY, None))
    ]
    assert eda_backed.is_upload_sentinel_vocabulary(vocabulary) is True


def test_a_real_one_dataset_vocabulary_is_not_an_empty_state() -> None:
    vocabulary = [
        wdk_vocab.WDKVocabTerm(("EDAUD_slI5M0RwIg0Zw", "My phenotype upload", None))
    ]
    assert eda_backed.is_upload_sentinel_vocabulary(vocabulary) is False


def test_two_terms_are_never_an_empty_state() -> None:
    vocabulary = [
        wdk_vocab.WDKVocabTerm(("EDAUD_a", _UPLOAD_DISPLAY, None)),
        wdk_vocab.WDKVocabTerm(("EDAUD_b", "My phenotype upload", None)),
    ]
    assert eda_backed.is_upload_sentinel_vocabulary(vocabulary) is False
