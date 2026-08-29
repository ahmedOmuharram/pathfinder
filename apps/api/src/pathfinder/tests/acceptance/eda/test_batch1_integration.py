"""Acceptance: the EDA wire models and the EDA HTTP client.

Values come from the live-verified EDA knowledge bundle. Fixtures are inline.
"""

from __future__ import annotations

import json

import httpx
import pytest
from pydantic import TypeAdapter, ValidationError

from pathfinder.platform.context import veupathdb_auth_token_ctx
from pathfinder.platform.errors import WDKLoginRequiredError

models = pytest.importorskip("pathfinder.integrations.eda.models")
errors = pytest.importorskip("pathfinder.integrations.eda.errors")
client_module = pytest.importorskip("pathfinder.integrations.eda.client")

pytestmark = [pytest.mark.eda_acceptance]

_FILTER = TypeAdapter(models.EdaFilter)
_FILTERS = TypeAdapter(list[models.EdaFilter])

_ENTITY = "GENE_PHENOTYPE_DATA_ENTITY"
_SPECIES = "VAR_035294d0"
_STUDY = "STUDY_53f554ec6a"

_SEVEN_LIVE_FILTERS: list[dict[str, object]] = [
    {
        "entityId": _ENTITY,
        "variableId": _SPECIES,
        "type": "stringSet",
        "stringSet": ["P. berghei"],
    },
    {
        "entityId": _ENTITY,
        "variableId": "EUPATH_0043064",
        "type": "numberSet",
        "numberSet": [1.0, 2.0],
    },
    {
        "entityId": _ENTITY,
        "variableId": "EUPATH_0043256",
        "type": "dateSet",
        "dateSet": ["2017-05-05T00:00:00"],
    },
    {
        "entityId": _ENTITY,
        "variableId": "EUPATH_0043064",
        "type": "numberRange",
        "min": 0.0,
        "max": 100.0,
    },
    {
        "entityId": _ENTITY,
        "variableId": "EUPATH_0043256",
        "type": "dateRange",
        "min": "2017-05-05T00:00:00",
        "max": "2017-05-11T00:00:00",
    },
    {
        "entityId": "GAZ_00000448",
        "variableId": "OBI_0001621",
        "type": "longitudeRange",
        "left": 15.0,
        "right": 16.0,
    },
    {
        "entityId": "EUPATH_0000096",
        "variableId": "EUPATH_0000321",
        "type": "multiFilter",
        "operation": "union",
        "subFilters": [{"variableId": "EUPATH_0015135", "stringSet": ["Yes"]}],
    },
]


def _permission_entry(*, omit: str = "") -> dict[str, object]:
    entry: dict[str, object] = {
        "studyId": "STUDY_66f9e70b8a",
        "sha1Hash": "66f9e70b8a4a9a7efebfe58e0303f2c7f84ec907",
        "isUserStudy": False,
        "displayName": "Transcriptomes of 7 sexual and asexual life stages",
        "shortDisplayName": "3D7 7Stages RNA-Seq",
        "description": "Illumina-based sequencing of P. falciparum 3D7 mRNA",
        "type": "end-user",
        "actionAuthorization": {
            "studyMetadata": True,
            "subsetting": True,
            "visualizations": True,
            "resultsFirstPage": True,
            "resultsAll": True,
        },
        "isManager": False,
        "accessRequestStatus": "no-request",
    }
    if omit:
        del entry[omit]
    return entry


def _de_config() -> object:
    return models.EdaDifferentialExpressionConfig(
        identifier_variable=models.EdaVariableSpec(
            entity_id="ENT_fd574cd6", variable_id="VEUPATHDB_GENE_ID"
        ),
        value_variable=models.EdaVariableSpec(
            entity_id="ENT_fd574cd6", variable_id="SEQUENCE_READ_COUNT_SENSE"
        ),
        comparator=models.EdaComparator(
            variable=models.EdaVariableSpec(
                entity_id="ENT_8151325d", variable_id="VAR_081ab087"
            ),
            group_a=[models.EdaLabeledRange(label="normal")],
            group_b=[models.EdaLabeledRange(label="febrile")],
        ),
    )


def _client(handler: object) -> object:
    instance = client_module.EdaClient(base_url="https://plasmodb.org/eda")
    instance.install_transport(httpx.MockTransport(handler))
    return instance


def test_the_filter_union_parses_all_seven_live_wire_types() -> None:
    parsed = _FILTERS.validate_python(_SEVEN_LIVE_FILTERS)
    assert [entry.type for entry in parsed] == [
        "stringSet",
        "numberSet",
        "dateSet",
        "numberRange",
        "dateRange",
        "longitudeRange",
        "multiFilter",
    ]
    assert (
        _FILTERS.dump_python(parsed, by_alias=True, exclude_none=True)
        == _SEVEN_LIVE_FILTERS
    )


def test_a_string_prefix_set_filter_is_refused_by_the_union() -> None:
    """Schema-present and wire-absent: the deployed build 422s the type."""
    with pytest.raises(ValidationError):
        _FILTER.validate_python(
            {
                "entityId": _ENTITY,
                "variableId": _SPECIES,
                "type": "stringPrefixSet",
                "prefixSet": ["P. ber"],
            }
        )


def test_a_permission_entry_parses_the_capital_h_hash_spelling() -> None:
    entry = models.EdaPermissionEntry.model_validate(_permission_entry())
    assert entry.study_id == "STUDY_66f9e70b8a"
    assert entry.sha1_hash == "66f9e70b8a4a9a7efebfe58e0303f2c7f84ec907"
    assert entry.action_authorization.results_all is True


def test_a_permission_entry_that_omits_a_declared_required_field_still_parses() -> None:
    """24 of 880 live entries omit shortDisplayName or description."""
    without_short = models.EdaPermissionEntry.model_validate(
        _permission_entry(omit="shortDisplayName")
    )
    without_description = models.EdaPermissionEntry.model_validate(
        _permission_entry(omit="description")
    )
    assert without_short.short_display_name is None
    assert without_short.description is not None
    assert without_description.description is None


def test_a_user_study_overview_parses_with_an_empty_hash_and_no_description() -> None:
    overview = models.EdaStudyOverview.model_validate(
        {
            "id": "STUDY_slI5M0RwIg0Zw",
            "datasetId": "EDAUD_slI5M0RwIg0Zw",
            "sha1hash": "",
            "sourceType": "user_submitted",
            "displayName": "My phenotype upload",
            "lastModified": "2026-05-27T20:00:00-04:00",
        }
    )
    assert overview.sha1hash == ""
    assert overview.short_display_name is None
    assert overview.description is None
    assert overview.dataset_id == "EDAUD_slI5M0RwIg0Zw"


def test_a_volcano_row_that_omits_the_p_value_parses() -> None:
    """One of 5511 live rows carries only effectSize and pointID."""
    parsed = models.VolcanoStatsResponse.model_validate(
        {
            "effectSizeLabel": "log2(Fold Change)",
            "statistics": [
                {"effectSize": "-1.49447459261845", "pointID": "PF3D7_MIT04200"}
            ],
        }
    )
    row = parsed.statistics[0]
    assert row.point_id == "PF3D7_MIT04200"
    assert row.effect_size == "-1.49447459261845"
    assert row.p_value is None
    assert row.adjusted_p_value is None


def test_every_one_of_the_six_job_statuses_parses() -> None:
    statuses = [
        "queued",
        "in-progress",
        "complete",
        "failed",
        "expired",
        "no-such-job",
    ]
    jobs = [
        models.EdaComputeJob.model_validate(
            {"jobID": "db04204e5386396e1ca2cb78469ab6fb", "status": status}
        )
        for status in statuses
    ]
    assert [job.status for job in jobs] == statuses
    assert all(len(job.job_id) == 32 for job in jobs)


def test_a_job_status_outside_the_six_is_refused() -> None:
    with pytest.raises(ValidationError):
        models.EdaComputeJob.model_validate(
            {"jobID": "db04204e5386396e1ca2cb78469ab6fb", "status": "running"}
        )


def test_the_analysis_descriptor_round_trips_derived_variable_ids() -> None:
    descriptor = models.EdaAnalysisDescriptor.model_validate(
        {"derivedVariables": ["dv-abc-123"]}
    )
    assert descriptor.derived_variables == ["dv-abc-123"]
    assert descriptor.model_dump(by_alias=True)["derivedVariables"] == ["dv-abc-123"]


def test_an_inline_derived_variable_object_is_refused() -> None:
    """The same body with a spec object in that array is a 422 upstream."""
    with pytest.raises(ValidationError):
        models.EdaAnalysisDescriptor.model_validate(
            {
                "derivedVariables": [
                    {"entityId": "GAZ_00000448", "variableId": "DV_meanMortality"}
                ]
            }
        )


@pytest.mark.asyncio
async def test_tabular_asks_for_json_with_no_wildcard_in_the_accept_header() -> None:
    """Content negotiation is one exact string comparison; anything else is TSV."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=[["gene_stable_id"], ["PF3D7_0100100"]])

    eda = _client(handler)
    token = veupathdb_auth_token_ctx.set("token-abc")
    try:
        rows = await eda.tabular(
            study_id=_STUDY,
            entity_id=_ENTITY,
            filters=[],
            output_variable_ids=["VEUPATHDB_GENE_ID"],
            num_rows=5,
        )
    finally:
        veupathdb_auth_token_ctx.reset(token)
        await eda.close()

    assert seen[0].headers["accept"] == "application/json"
    assert rows == [["gene_stable_id"], ["PF3D7_0100100"]]


@pytest.mark.asyncio
async def test_count_posts_the_filter_array_verbatim() -> None:
    """The berghei subset of the 4279-row phenotype entity is 4011."""
    seen: list[object] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"count": 4011})

    eda = _client(handler)
    token = veupathdb_auth_token_ctx.set("token-abc")
    try:
        count = await eda.count(
            study_id=_STUDY,
            entity_id=_ENTITY,
            filters=_FILTERS.validate_python([_SEVEN_LIVE_FILTERS[0]]),
        )
    finally:
        veupathdb_auth_token_ctx.reset(token)
        await eda.close()

    assert count == 4011
    assert seen[0] == {"filters": [_SEVEN_LIVE_FILTERS[0]]}


@pytest.mark.asyncio
async def test_a_request_with_no_registered_token_never_reaches_the_wire() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"count": 0})

    eda = _client(handler)
    token = veupathdb_auth_token_ctx.set(None)
    try:
        with pytest.raises(WDKLoginRequiredError):
            await eda.count(study_id=_STUDY, entity_id=_ENTITY, filters=[])
    finally:
        veupathdb_auth_token_ctx.reset(token)
        await eda.close()

    assert calls == []


@pytest.mark.asyncio
async def test_an_unauthorized_response_carries_its_own_status_through() -> None:
    """EDA refuses a guest, and the refusal is not a 403 and not a 404."""
    eda = _client(lambda _r: httpx.Response(401, json={"status": "unauthorized"}))
    token = veupathdb_auth_token_ctx.set("token-abc")
    try:
        with pytest.raises(errors.EdaError) as excinfo:
            await eda.list_studies()
    finally:
        veupathdb_auth_token_ctx.reset(token)
        await eda.close()

    assert excinfo.value.status == 401
    assert not isinstance(excinfo.value, errors.EdaForbiddenError)
    assert not isinstance(excinfo.value, errors.EdaNotFoundError)


@pytest.mark.asyncio
async def test_an_invalid_input_body_becomes_the_typed_invalid_input_error() -> None:
    body = {
        "status": "invalid-input",
        "errors": {
            "general": [],
            "byKey": {
                "config": [
                    "Cannot deserialize value of type "
                    '`DifferentialExpressionMethod` from String "DESeq2"'
                ]
            },
        },
    }
    eda = _client(lambda _r: httpx.Response(422, json=body))
    token = veupathdb_auth_token_ctx.set("token-abc")
    try:
        with pytest.raises(errors.EdaInvalidInputError) as excinfo:
            await eda.submit_compute(
                compute_name="differentialexpression",
                study_id="STUDY_e973eadd57",
                config=_de_config(),
                filters=[],
            )
    finally:
        veupathdb_auth_token_ctx.reset(token)
        await eda.close()

    assert excinfo.value.status == 422
    assert excinfo.value.errors is not None


@pytest.mark.asyncio
async def test_a_dataset_id_where_a_study_id_belongs_is_the_forbidden_error() -> None:
    eda = _client(lambda _r: httpx.Response(403, json={"status": "forbidden"}))
    token = veupathdb_auth_token_ctx.set("token-abc")
    try:
        with pytest.raises(errors.EdaForbiddenError) as excinfo:
            await eda.submit_compute(
                compute_name="differentialexpression",
                study_id="DS_e973eadd57",
                config=_de_config(),
                filters=[],
            )
    finally:
        veupathdb_auth_token_ctx.reset(token)
        await eda.close()

    assert excinfo.value.status == 403
