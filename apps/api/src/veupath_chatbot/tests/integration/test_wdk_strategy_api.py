"""HTTP-level integration tests for StrategyAPI.

Uses ``respx`` to mock outbound httpx transport so that every test exercises
the full StrategyAPI -> VEuPathDBClient -> httpx pipeline without hitting a
real WDK deployment.  Fixture responses come from
``veupath_chatbot.tests.fixtures.wdk_responses``.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.strategy_api import (
    StepTreeNode,
    StrategyAPI,
)
from veupath_chatbot.tests.fixtures.wdk_responses import (
    analysis_create_response,
    analysis_result_response,
    analysis_status_response,
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

        assert api.user_id == "current"
        await api._ensure_session()

        assert api.user_id == str(USER_ID)
        assert api._session_initialized is True


# ---------------------------------------------------------------------------
# 2. create_step normalizes params
# ---------------------------------------------------------------------------
class TestCreateStep:
    @respx.mock
    @pytest.mark.asyncio
    async def test_create_step_normalizes_params(self, api: StrategyAPI) -> None:
        """Bool/list/None values are converted to WDK string representations."""
        _mock_ensure_session(respx)

        step_route = respx.post(f"{BASE}/users/{USER_ID}/steps").respond(
            200, json=step_creation_response(100)
        )

        result = await api.create_step(
            record_type="gene",
            search_name="GenesByTaxon",
            parameters={
                "organism": ["Plasmodium falciparum 3D7"],
                "include_obsolete": True,
                "exclude_pattern": False,
                "optional_field": None,
                "plain_text": "hello",
            },
            custom_name="Test step",
        )

        assert result["id"] == 100
        assert step_route.called

        sent_body = json.loads(step_route.calls.last.request.content)
        params = sent_body["searchConfig"]["parameters"]

        # list -> JSON-encoded string
        assert params["organism"] == json.dumps(["Plasmodium falciparum 3D7"])
        # bool True -> "true"
        assert params["include_obsolete"] == "true"
        # bool False -> "false"
        assert params["exclude_pattern"] == "false"
        # None -> "" (omitted because _normalize_parameters strips empty values)
        assert "optional_field" not in params
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

        # GET /record-types/gene/searches -> includes boolean_question
        respx.get(f"{BASE}/record-types/gene/searches").respond(
            200, json=searches_response()
        )

        boolean_search_name = "boolean_question_GeneRecordClasses.GeneRecordClass"

        # GET search details for the boolean question
        respx.get(
            f"{BASE}/record-types/gene/searches/{boolean_search_name}",
        ).respond(200, json=search_details_response(boolean_search_name))

        step_route = respx.post(f"{BASE}/users/{USER_ID}/steps").respond(
            200, json=step_creation_response(110)
        )

        result = await api.create_combined_step(
            primary_step_id=100,
            secondary_step_id=101,
            boolean_operator="UNION",
            record_type="gene",
        )

        assert result["id"] == 110
        assert step_route.called

        sent_body = json.loads(step_route.calls.last.request.content)
        assert sent_body["searchName"] == boolean_search_name

        params = sent_body["searchConfig"]["parameters"]
        # The operator param should carry the requested value
        assert params["bq_operator"] == "UNION"
        # Left/right operands are empty (wired via stepTree later)
        suffix = "GeneRecordClasses.GeneRecordClass"
        assert params[f"bq_left_op__{suffix}"] == ""
        assert params[f"bq_right_op__{suffix}"] == ""


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
            f"{BASE}/record-types/gene/searches/{transform_name}",
        ).respond(200, json=search_details_response(transform_name))

        step_route = respx.post(f"{BASE}/users/{USER_ID}/steps").respond(
            200, json=step_creation_response(120)
        )

        result = await api.create_transform_step(
            input_step_id=100,
            transform_name=transform_name,
            parameters={
                "inputStepId": "stale_value_should_be_blanked",
                "organism": ["Plasmodium vivax P01"],
                "isSyntenic": "no",
            },
            record_type="gene",
        )

        assert result["id"] == 120
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

        assert result["id"] == 200
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
            analysis_type="gene-go-enrichment",
            parameters={"goAssociations": "biological_process"},
            poll_interval=0.0,  # no real waiting in tests
            max_wait=10.0,
        )

        # Verify result content
        assert result["resultSize"] == 42
        assert len(result["rows"]) == 3
        assert result["rows"][0]["ID"] == "GO:0003735"

        # Status was polled exactly twice (RUNNING, then COMPLETE)
        assert status_route.call_count == 2


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
        ds_id = await api.create_dataset(ids=gene_ids)

        assert ds_id == 500
        assert dataset_route.called

        sent_body = json.loads(dataset_route.calls.last.request.content)
        assert sent_body["sourceType"] == "idList"
        assert sent_body["sourceContent"]["ids"] == gene_ids
