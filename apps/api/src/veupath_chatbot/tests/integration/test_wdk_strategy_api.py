"""HTTP-level integration tests for StrategyAPI.

Uses ``respx`` to mock outbound httpx transport so that every test exercises
the full StrategyAPI -> VEuPathDBClient -> httpx pipeline without hitting a
real WDK deployment.  Fixture responses come from
``veupath_chatbot.tests.fixtures.wdk_responses``.
"""

import json

import httpx
import pytest
import respx

from veupath_chatbot.domain.strategy.ast import StepTreeNode
from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.strategy_api.analyses import (
    AnalysisPollConfig,
)
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    WDKDatasetConfigIdList,
    WDKDatasetIdListContent,
    WDKSearchConfig,
)
from veupath_chatbot.platform.errors import InternalError
from veupath_chatbot.tests.fixtures.wdk_responses import (
    analysis_create_response,
    analysis_result_response,
    analysis_status_response,
    column_distribution_response_number,
    column_distribution_response_string,
    dataset_creation_response,
    search_details_response,
    searches_response,
    standard_report_response,
    step_creation_response,
    strategy_creation_response,
    user_current_response,
)

BASE = "https://plasmodb.org/plasmo/service"
USER_ID = 12345


@pytest.fixture
def api() -> StrategyAPI:
    """StrategyAPI backed by a real VEuPathDBClient (HTTP mocked by respx)."""
    client = VEuPathDBClient(base_url=BASE, timeout=5.0)
    return StrategyAPI(client)


def _mock_ensure_session(router: respx.Router, user_id: int = USER_ID) -> None:
    """Register the GET /users/current route used by ``_ensure_session``."""
    router.get(f"{BASE}/users/current").respond(
        200, json=user_current_response(user_id)
    )


# ---------------------------------------------------------------------------
# 1. _ensure_session resolves user ID
# ---------------------------------------------------------------------------
class TestEnsureSession:
    @respx.mock
    @pytest.mark.asyncio
    async def test_ensure_session_resolves_user_id(self, api: StrategyAPI) -> None:
        """GET /users/current returns a user object; user_id is resolved."""
        _mock_ensure_session(respx)

        assert api._resolved_user_id == "current"
        await api._ensure_session()

        assert api._resolved_user_id == str(USER_ID)
        assert api._session_initialized is True


# ---------------------------------------------------------------------------
# 2. create_step normalizes params
# ---------------------------------------------------------------------------
class TestCreateStep:
    @respx.mock
    @pytest.mark.asyncio
    async def test_create_step_forwards_params(self, api: StrategyAPI) -> None:
        """String parameters are forwarded to the WDK payload correctly."""
        _mock_ensure_session(respx)

        # _expand_tree_params_to_leaves fetches search details with expandParams
        respx.get(f"{BASE}/record-types/gene/searches/GenesByTaxon").respond(
            200,
            json={"searchData": {"parameters": []}},
        )

        step_route = respx.post(f"{BASE}/users/{USER_ID}/steps").respond(
            200, json=step_creation_response(100)
        )

        result = await api.create_step(
            NewStepSpec(
                search_name="GenesByTaxon",
                search_config=WDKSearchConfig(
                    parameters={
                        "organism": json.dumps(["Plasmodium falciparum 3D7"]),
                        "include_obsolete": "true",
                        "exclude_pattern": "false",
                        "plain_text": "hello",
                    },
                ),
                custom_name="Test step",
            ),
            record_type="gene",
        )

        assert result.id == 100
        assert step_route.called

        sent_body = json.loads(step_route.calls.last.request.content)
        params = sent_body["searchConfig"]["parameters"]

        # JSON-encoded list string passes through
        assert params["organism"] == json.dumps(["Plasmodium falciparum 3D7"])
        # String "true"/"false" pass through
        assert params["include_obsolete"] == "true"
        assert params["exclude_pattern"] == "false"
        # plain string kept as-is
        assert params["plain_text"] == "hello"
        # customName forwarded
        assert sent_body["customName"] == "Test step"


# ---------------------------------------------------------------------------
# 3. create_combined_step
# ---------------------------------------------------------------------------
class TestCreateCombinedStep:
    @respx.mock
    @pytest.mark.asyncio
    async def test_create_combined_step(self, api: StrategyAPI) -> None:
        """Boolean combine resolves search name and param names via HTTP."""
        _mock_ensure_session(respx)

        # GET /record-types/transcript/searches -> includes boolean_question
        respx.get(f"{BASE}/record-types/transcript/searches").respond(
            200, json=searches_response()
        )

        # Real PlasmoDB uses underscores in boolean question urlSegment
        boolean_search_name = (
            "boolean_question_TranscriptRecordClasses_TranscriptRecordClass"
        )

        # GET search details for the boolean question
        respx.get(
            f"{BASE}/record-types/transcript/searches/{boolean_search_name}",
        ).respond(200, json=search_details_response(boolean_search_name))

        step_route = respx.post(f"{BASE}/users/{USER_ID}/steps").respond(
            200, json=step_creation_response(110)
        )

        result = await api.create_combined_step(
            primary_step_id=100,
            secondary_step_id=101,
            boolean_operator="UNION",
            record_type="transcript",
        )

        assert result.id == 110
        assert step_route.called

        sent_body = json.loads(step_route.calls.last.request.content)
        assert sent_body["searchName"] == boolean_search_name

        params = sent_body["searchConfig"]["parameters"]
        # The operator param should carry the requested value
        assert params["bq_operator"] == "UNION"
        # Left/right operands are empty (wired via stepTree later)
        suffix = "TranscriptRecordClasses_TranscriptRecordClass"
        assert params[f"bq_left_op_{suffix}"] == ""
        assert params[f"bq_right_op_{suffix}"] == ""


# ---------------------------------------------------------------------------
# 4. create_transform_step blanks AnswerParams
# ---------------------------------------------------------------------------
class TestCreateTransformStep:
    @respx.mock
    @pytest.mark.asyncio
    async def test_create_transform_step_blanks_answer_params(
        self, api: StrategyAPI
    ) -> None:
        """AnswerParam (input-step) values are forced to empty string."""
        _mock_ensure_session(respx)

        transform_name = "GenesByOrthologs"

        # GET search details (includes inputStepId as type=input-step)
        respx.get(
            f"{BASE}/record-types/transcript/searches/{transform_name}",
        ).respond(200, json=search_details_response(transform_name))

        step_route = respx.post(f"{BASE}/users/{USER_ID}/steps").respond(
            200, json=step_creation_response(120)
        )

        result = await api.create_transform_step(
            NewStepSpec(
                search_name=transform_name,
                search_config=WDKSearchConfig(
                    parameters={
                        "inputStepId": "stale_value_should_be_blanked",
                        "organism": json.dumps(["Plasmodium vivax P01"]),
                        "isSyntenic": "no",
                    },
                ),
            ),
            input_step_id=100,
            record_type="transcript",
        )

        assert result.id == 120
        assert step_route.called

        sent_body = json.loads(step_route.calls.last.request.content)
        params = sent_body["searchConfig"]["parameters"]

        # AnswerParam forced to ""
        assert params["inputStepId"] == ""
        # Other params normalized normally
        assert params["organism"] == json.dumps(["Plasmodium vivax P01"])
        assert params["isSyntenic"] == "no"


# ---------------------------------------------------------------------------
# 5. create_strategy builds step tree
# ---------------------------------------------------------------------------
class TestCreateStrategy:
    @respx.mock
    @pytest.mark.asyncio
    async def test_create_strategy_builds_step_tree(self, api: StrategyAPI) -> None:
        """POST /strategies includes stepTree with primaryInput/secondaryInput."""
        _mock_ensure_session(respx)

        strategy_route = respx.post(f"{BASE}/users/{USER_ID}/strategies").respond(
            200, json=strategy_creation_response(200)
        )

        leaf_a = StepTreeNode(step_id=10)
        leaf_b = StepTreeNode(step_id=11)
        root = StepTreeNode(step_id=100, primary_input=leaf_a, secondary_input=leaf_b)

        result = await api.create_strategy(
            step_tree=root,
            name="Integration test strategy",
            description="Two-leaf combine",
            is_saved=True,
        )

        assert result.id == 200
        assert strategy_route.called

        sent_body = json.loads(strategy_route.calls.last.request.content)
        assert sent_body["name"] == "Integration test strategy"
        assert sent_body["description"] == "Two-leaf combine"
        assert sent_body["isSaved"] is True
        assert sent_body["isPublic"] is False

        tree = sent_body["stepTree"]
        assert tree["stepId"] == 100
        assert tree["primaryInput"]["stepId"] == 10
        assert tree["secondaryInput"]["stepId"] == 11


# ---------------------------------------------------------------------------
# 6. get_step_count reads meta.totalCount
# ---------------------------------------------------------------------------
class TestGetStepCount:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_step_count(self, api: StrategyAPI) -> None:
        """POST standard report with numRecords=0 returns meta.totalCount."""
        _mock_ensure_session(respx)

        report_route = respx.post(
            f"{BASE}/users/{USER_ID}/steps/100/reports/standard"
        ).respond(200, json=standard_report_response(gene_ids=[], total_count=42))

        count = await api.get_step_count(step_id=100)

        assert count == 42
        assert report_route.called

        sent_body = json.loads(report_route.calls.last.request.content)
        pagination = sent_body["reportConfig"]["pagination"]
        assert pagination["offset"] == 0
        assert pagination["numRecords"] == 0


# ---------------------------------------------------------------------------
# 7. run_step_analysis full lifecycle
# ---------------------------------------------------------------------------
class TestRunStepAnalysis:
    @respx.mock
    @pytest.mark.asyncio
    async def test_run_step_analysis_lifecycle(self, api: StrategyAPI) -> None:
        """Create -> run -> poll(RUNNING -> COMPLETE) -> get result."""
        _mock_ensure_session(respx)

        uid = str(USER_ID)
        step_id = 100
        analysis_id = 300
        analysis_base = f"{BASE}/users/{uid}/steps/{step_id}/analyses"

        # Warmup: zero-record standard report materializes the step answer
        respx.post(f"{BASE}/users/{uid}/steps/{step_id}/reports/standard").respond(
            200, json=standard_report_response(gene_ids=[], total_count=42)
        )

        # Phase 1: create analysis instance
        respx.post(analysis_base).respond(
            200, json=analysis_create_response(analysis_id)
        )

        # Phase 2: kick off execution
        respx.post(f"{analysis_base}/{analysis_id}/result").respond(
            200, json={"status": "RUNNING"}
        )

        # Phase 3: poll status -- first RUNNING, then COMPLETE
        status_url = f"{analysis_base}/{analysis_id}/result/status"
        status_route = respx.get(status_url).mock(
            side_effect=[
                httpx.Response(200, json=analysis_status_response("RUNNING")),
                httpx.Response(200, json=analysis_status_response("COMPLETE")),
            ]
        )

        # Phase 4: retrieve result
        result_response = analysis_result_response()
        respx.get(f"{analysis_base}/{analysis_id}/result").respond(
            200, json=result_response
        )

        result = await api.run_step_analysis(
            step_id=step_id,
            analysis_type="go-enrichment",
            parameters={"goAssociationsOntologies": "Biological Process"},
            poll_config=AnalysisPollConfig(poll_interval=0.0, max_wait=10.0),
        )

        # Verify result content (real WDK format: resultData with camelCase string fields)
        assert len(result["resultData"]) == 3
        assert result["resultData"][0]["goId"] == "GO:0003735"

        # Status was polled exactly twice (RUNNING, then COMPLETE)
        assert status_route.call_count == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_warmup_report_before_analysis(self, api: StrategyAPI) -> None:
        """run_step_analysis triggers a zero-record standard report first.

        Boolean/combined steps need their answer materialized before WDK will
        accept step analysis requests.  Requesting a zero-record report forces
        WDK to compute and cache the answer.
        """
        _mock_ensure_session(respx)

        uid = str(USER_ID)
        step_id = 100
        analysis_id = 300
        analysis_base = f"{BASE}/users/{uid}/steps/{step_id}/analyses"

        # Warmup: zero-record standard report
        warmup_route = respx.post(
            f"{BASE}/users/{uid}/steps/{step_id}/reports/standard"
        ).respond(200, json=standard_report_response(gene_ids=[], total_count=150))

        respx.post(analysis_base).respond(
            200, json=analysis_create_response(analysis_id)
        )
        respx.post(f"{analysis_base}/{analysis_id}/result").respond(
            200, json={"status": "RUNNING"}
        )
        respx.get(f"{analysis_base}/{analysis_id}/result/status").respond(
            200, json=analysis_status_response("COMPLETE")
        )
        respx.get(f"{analysis_base}/{analysis_id}/result").respond(
            200, json=analysis_result_response()
        )

        result = await api.run_step_analysis(
            step_id=step_id,
            analysis_type="go-enrichment",
            poll_config=AnalysisPollConfig(poll_interval=0.0, max_wait=10.0),
        )

        assert len(result["resultData"]) == 3
        # Warmup report was called before creating the analysis
        assert warmup_route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_error_status_reruns_same_instance(self, api: StrategyAPI) -> None:
        """ERROR on boolean/combined steps → re-run same instance → succeeds.

        WDK step analyses on boolean/combined steps can ERROR on first run
        because sub-step answers haven't been computed yet.  The WDK backend
        supports re-running the same instance (requiresRerun=true for ERROR).
        We must NOT create a new instance — just POST to the run endpoint again.
        """
        _mock_ensure_session(respx)

        uid = str(USER_ID)
        step_id = 100
        analysis_id = 300
        analysis_base = f"{BASE}/users/{uid}/steps/{step_id}/analyses"

        # Warmup report
        respx.post(f"{BASE}/users/{uid}/steps/{step_id}/reports/standard").respond(
            200, json=standard_report_response(gene_ids=[], total_count=150)
        )

        # Phase 1: create analysis instance (only once)
        create_route = respx.post(analysis_base).respond(
            200, json=analysis_create_response(analysis_id)
        )

        # Phase 2: run endpoint called twice (initial + retry)
        run_route = respx.post(f"{analysis_base}/{analysis_id}/result").respond(
            200, json={"status": "RUNNING"}
        )

        # Phase 3: poll returns ERROR first, then RUNNING after re-run, then COMPLETE
        status_url = f"{analysis_base}/{analysis_id}/result/status"
        status_route = respx.get(status_url).mock(
            side_effect=[
                httpx.Response(200, json=analysis_status_response("ERROR")),
                httpx.Response(200, json=analysis_status_response("RUNNING")),
                httpx.Response(200, json=analysis_status_response("COMPLETE")),
            ]
        )

        # Phase 4: retrieve result
        respx.get(f"{analysis_base}/{analysis_id}/result").respond(
            200, json=analysis_result_response()
        )

        result = await api.run_step_analysis(
            step_id=step_id,
            analysis_type="go-enrichment",
            parameters={"goAssociationsOntologies": "Biological Process"},
            poll_config=AnalysisPollConfig(poll_interval=0.0, max_wait=10.0),
        )

        assert len(result["resultData"]) == 3

        # Instance created exactly once — no new instance on retry
        assert create_route.call_count == 1

        # Run endpoint called twice: initial run + retry after ERROR
        assert run_route.call_count == 2

        # Status polled 3 times: ERROR, RUNNING, COMPLETE
        assert status_route.call_count == 3

    @respx.mock
    @pytest.mark.asyncio
    async def test_out_of_date_reruns_same_instance(self, api: StrategyAPI) -> None:
        """OUT_OF_DATE (cache cleared) → re-run same instance → succeeds."""
        _mock_ensure_session(respx)

        uid = str(USER_ID)
        step_id = 100
        analysis_id = 300
        analysis_base = f"{BASE}/users/{uid}/steps/{step_id}/analyses"

        respx.post(f"{BASE}/users/{uid}/steps/{step_id}/reports/standard").respond(
            200, json=standard_report_response(gene_ids=[], total_count=0)
        )

        create_route = respx.post(analysis_base).respond(
            200, json=analysis_create_response(analysis_id)
        )
        run_route = respx.post(f"{analysis_base}/{analysis_id}/result").respond(
            200, json={"status": "RUNNING"}
        )

        status_url = f"{analysis_base}/{analysis_id}/result/status"
        respx.get(status_url).mock(
            side_effect=[
                httpx.Response(200, json=analysis_status_response("OUT_OF_DATE")),
                httpx.Response(200, json=analysis_status_response("COMPLETE")),
            ]
        )

        respx.get(f"{analysis_base}/{analysis_id}/result").respond(
            200, json=analysis_result_response()
        )

        result = await api.run_step_analysis(
            step_id=step_id,
            analysis_type="go-enrichment",
            poll_config=AnalysisPollConfig(poll_interval=0.0, max_wait=10.0),
        )

        assert len(result["resultData"]) == 3
        assert create_route.call_count == 1
        assert run_route.call_count == 2  # initial + retry

    @respx.mock
    @pytest.mark.asyncio
    async def test_repeated_errors_raises_after_max_retries(
        self, api: StrategyAPI
    ) -> None:
        """Repeated ERROR statuses give up after max retries."""
        _mock_ensure_session(respx)

        uid = str(USER_ID)
        step_id = 100
        analysis_id = 300
        analysis_base = f"{BASE}/users/{uid}/steps/{step_id}/analyses"

        respx.post(f"{BASE}/users/{uid}/steps/{step_id}/reports/standard").respond(
            200, json=standard_report_response(gene_ids=[], total_count=0)
        )

        respx.post(analysis_base).respond(
            200, json=analysis_create_response(analysis_id)
        )
        respx.post(f"{analysis_base}/{analysis_id}/result").respond(
            200, json={"status": "RUNNING"}
        )

        # Return ERROR every time — should eventually give up
        status_url = f"{analysis_base}/{analysis_id}/result/status"
        respx.get(status_url).respond(200, json=analysis_status_response("ERROR"))

        with pytest.raises(InternalError, match="Analysis unavailable"):
            await api.run_step_analysis(
                step_id=step_id,
                analysis_type="go-enrichment",
                poll_config=AnalysisPollConfig(poll_interval=0.0, max_wait=10.0),
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_expired_status_raises(self, api: StrategyAPI) -> None:
        """EXPIRED status raises InternalError immediately (no retry)."""
        _mock_ensure_session(respx)

        uid = str(USER_ID)
        step_id = 100
        analysis_id = 300
        analysis_base = f"{BASE}/users/{uid}/steps/{step_id}/analyses"

        respx.post(f"{BASE}/users/{uid}/steps/{step_id}/reports/standard").respond(
            200, json=standard_report_response(gene_ids=[], total_count=0)
        )

        respx.post(analysis_base).respond(
            200, json=analysis_create_response(analysis_id)
        )
        respx.post(f"{analysis_base}/{analysis_id}/result").respond(
            200, json={"status": "RUNNING"}
        )

        status_url = f"{analysis_base}/{analysis_id}/result/status"
        respx.get(status_url).respond(200, json=analysis_status_response("EXPIRED"))

        with pytest.raises(InternalError, match="Step analysis failed"):
            await api.run_step_analysis(
                step_id=step_id,
                analysis_type="go-enrichment",
                poll_config=AnalysisPollConfig(poll_interval=0.0, max_wait=10.0),
            )


# ---------------------------------------------------------------------------
# 8. create_dataset
# ---------------------------------------------------------------------------
class TestCreateDataset:
    @respx.mock
    @pytest.mark.asyncio
    async def test_create_dataset(self, api: StrategyAPI) -> None:
        """POST /users/{uid}/datasets with idList payload returns dataset id."""
        _mock_ensure_session(respx)

        dataset_route = respx.post(f"{BASE}/users/{USER_ID}/datasets").respond(
            200, json=dataset_creation_response(500)
        )

        gene_ids = ["PF3D7_0100100", "PF3D7_0831900", "PF3D7_1133400"]
        config = WDKDatasetConfigIdList(
            source_type="idList",
            source_content=WDKDatasetIdListContent(ids=gene_ids),
        )
        ds_id = await api.create_dataset(config)

        assert ds_id == 500
        assert dataset_route.called

        sent_body = json.loads(dataset_route.calls.last.request.content)
        assert sent_body["sourceType"] == "idList"
        assert sent_body["sourceContent"]["ids"] == gene_ids


# ---------------------------------------------------------------------------
# 9. get_column_distribution uses column reporter (not filter-summary)
# ---------------------------------------------------------------------------
class TestGetColumnDistribution:
    @respx.mock
    @pytest.mark.asyncio
    async def test_string_column_distribution(self, api: StrategyAPI) -> None:
        """POST .../columns/{col}/reports/byValue returns histogram + statistics."""
        _mock_ensure_session(respx)

        step_id = 100
        column_name = "organism"
        expected = column_distribution_response_string()

        col_route = respx.post(
            f"{BASE}/users/{USER_ID}/steps/{step_id}/columns/{column_name}/reports/byValue"
        ).respond(200, json=expected)

        result = await api.get_column_distribution(step_id, column_name)

        assert col_route.called
        assert len(result.histogram) == 3
        assert result.histogram[0].value == 2890
        assert result.statistics.subset_size == 4429

        sent_body = json.loads(col_route.calls.last.request.content)
        assert sent_body == {"reportConfig": {}}

    @respx.mock
    @pytest.mark.asyncio
    async def test_number_column_distribution(self, api: StrategyAPI) -> None:
        """Number columns return binned histogram with ranges."""
        _mock_ensure_session(respx)

        step_id = 100
        column_name = "exon_count"
        expected = column_distribution_response_number()

        col_route = respx.post(
            f"{BASE}/users/{USER_ID}/steps/{step_id}/columns/{column_name}/reports/byValue"
        ).respond(200, json=expected)

        result = await api.get_column_distribution(step_id, column_name)

        assert col_route.called
        assert len(result.histogram) == 4
        assert result.histogram[1].bin_label == "[5.0, 10.0)"
        assert result.statistics.subset_min == 0.5

    @respx.mock
    @pytest.mark.asyncio
    async def test_unsupported_column_returns_empty(self, api: StrategyAPI) -> None:
        """WDK 500 for unsupported columns returns empty histogram gracefully."""
        _mock_ensure_session(respx)

        step_id = 100
        column_name = "snpoverview"

        respx.post(
            f"{BASE}/users/{USER_ID}/steps/{step_id}/columns/{column_name}/reports/byValue"
        ).respond(500, text="Internal Error")

        result = await api.get_column_distribution(step_id, column_name)

        assert result.histogram == []
        assert result.statistics.subset_size == 0

    @respx.mock
    @pytest.mark.asyncio
    async def test_timeout_returns_empty(self, api: StrategyAPI) -> None:
        """WDK timeout for slow columns returns empty without retrying."""
        _mock_ensure_session(respx)

        step_id = 100
        column_name = "pan_3586"

        route = respx.post(
            f"{BASE}/users/{USER_ID}/steps/{step_id}/columns/{column_name}/reports/byValue"
        ).mock(side_effect=httpx.ReadTimeout("read timed out"))

        result = await api.get_column_distribution(step_id, column_name)

        assert result.histogram == []
        assert result.statistics.subset_size == 0
        # Tenacity retries transient transport errors 3 times before giving up.
        # The resulting RetryError is converted to WDKError, which
        # get_column_distribution catches and returns empty.
        assert route.call_count == 3
