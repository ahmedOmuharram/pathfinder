"""veupathdb-wdk-mcp read by veupathdb-mcp-conformance, over the served endpoint.

The suite is a separate distribution that imports nothing of this deployment, so
it runs as its own pytest process: this module supplies the endpoint, both
credentials, the arguments a call may use, and the WDK-backed account hook, then
reads the admission record the run wrote.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from assistant_core.platform.pydantic_base import CamelModel
from pydantic import Field

from pathfinder import __version__ as pathfinder_version
from pathfinder.integrations.veupathdb.factory import get_strategy_api
from pathfinder.mcp.server import SERVER_NAME, TOOLS
from pathfinder.platform.context import veupathdb_auth_token_ctx
from pathfinder.services.gene_sets.wdk_helpers import fetch_gene_ids_from_step
from pathfinder.tests._support.wdk_credentials import NO_CREDENTIALS_REASON
from pathfinder.tests.integration.mcp._served import (
    RECORD_TYPE,
    SITE,
    TARGET_PARAMETERS,
    TARGET_SEARCH,
    OwnedStep,
    owned_step_for,
    served_url,
    wire,
)

pytestmark = pytest.mark.live_wdk

BEARER_VARIABLE = "MCP_CONFORMANCE_BEARER"
SECOND_BEARER_VARIABLE = "MCP_CONFORMANCE_BEARER_SECOND"

# Where a lane collects the record it publishes. Unset, the run keeps it beside
# the arguments it wrote, and the record is still read by the checks below.
REPORT_VARIABLE = "MCP_ADMISSION_REPORT"

ACCOUNT_HOOK = "pathfinder.tests.integration.mcp.conformance_account_hook"

# A Toxoplasma gene, which a Plasmodium falciparum search cannot return.
NEGATIVE_CONTROL = "TGME49_205250"
CONTROL_GENE_COUNT = 3

RUN_SECONDS = 900.0

# Three gaps, each for its own measured reason: one account cannot own the
# resource a second identity must read, no served write is idempotent, and no
# served call can be driven past a budget without the abandoned work outliving
# the caller. The suite reports each as a skip, and the verdict is incomplete.
UNSETTLED_CHECKS = frozenset(
    {
        "test_auth.py::test_one_identity_cannot_read_another_identity_resource",
        "test_auth.py::test_the_isolation_case_names_a_resource_that_exists",
        "test_annotations.py::test_an_idempotent_tool_answers_the_same_twice",
        "test_timeouts.py::test_a_call_past_its_budget_times_out_on_the_client",
        "test_timeouts.py::test_the_timeout_fires_at_the_budget_and_not_later",
        "test_timeouts.py::test_the_session_survives_a_call_that_timed_out",
    }
)

EXPECTED_FAMILIES = ("shape", "auth", "annotations", "errors", "timeouts", "stability")


class RecordedCheck(CamelModel):
    id: str
    outcome: str
    message: str | None = None


class RecordedFamily(CamelModel):
    id: str
    number: int
    passed: int
    failed: int
    skipped: int
    checks: list[RecordedCheck]


class RecordedServerInfo(CamelModel):
    name: str = ""
    version: str = ""


class RecordedServer(CamelModel):
    protocol_version: str = ""
    instructions: str | None = None
    server_info: RecordedServerInfo = RecordedServerInfo()


class RecordedTool(CamelModel):
    name: str
    description: str = ""
    output_schema: dict[str, Any] | None = None


class AdmissionRecord(CamelModel):
    """The report an operator reads before admitting a source."""

    verdict: str
    server: RecordedServer = RecordedServer()
    tools: list[RecordedTool] = Field(default_factory=list)
    families: list[RecordedFamily] = Field(default_factory=list)

    @property
    def unsettled(self) -> set[str]:
        return {
            check.id
            for family in self.families
            for check in family.checks
            if check.outcome == "skipped"
        }

    @property
    def broken(self) -> set[str]:
        return {
            check.id
            for family in self.families
            for check in family.checks
            if check.outcome in ("failed", "error")
        }


def sample_arguments(step: OwnedStep, controls: list[str]) -> dict[str, Any]:
    """The arguments a conformance call may use, on the one site kept warm.

    Fifteen of the sixteen tools appear. `enrich_gene_ids` does not: the suite
    calls one non-destructive write, and the cheaper of the two answers it.
    """
    return {
        "list_record_types": {"site_id": SITE},
        "search_for_searches": {"site_id": SITE, "query": "genes by molecular weight"},
        "browse_search_categories": {"site_id": SITE},
        "list_searches": {"site_id": SITE},
        "list_transforms": {"site_id": SITE},
        "lookup_phyletic_codes": {"site_id": SITE, "query": "falciparum"},
        "search_example_plans": {"site_id": SITE, "query": "gametocyte genes"},
        "get_search_overview": {"site_id": SITE, "search_name": TARGET_SEARCH},
        "get_parameter_options": {
            "site_id": SITE,
            "search_name": TARGET_SEARCH,
            "parameter_id": "organism",
        },
        "lookup_gene_records": {"site_id": SITE, "query": "PfAP2-G", "limit": 5},
        "resolve_gene_ids_to_records": {"site_id": SITE, "gene_ids": controls},
        "get_step_estimated_size": {
            "site_id": SITE,
            "wdk_step_id": step.step_id,
            "wdk_strategy_id": step.strategy_id,
        },
        "get_step_sample_records": {
            "site_id": SITE,
            "wdk_step_id": step.step_id,
            "record_type": RECORD_TYPE,
            "limit": CONTROL_GENE_COUNT,
        },
        "get_step_download_url": {"site_id": SITE, "wdk_step_id": step.step_id},
        "run_control_tests_on_search": {
            "site_id": SITE,
            "target_search_name": TARGET_SEARCH,
            "target_parameters": wire(TARGET_PARAMETERS),
            "positive_controls": controls,
            "negative_controls": [NEGATIVE_CONTROL],
            "record_type": RECORD_TYPE,
        },
    }


def conformance_command(samples: Path, report: Path) -> list[str]:
    """The run a foreign operator makes, with this deployment's answers filled in.

    No `--mcp-slow-tool` is named. The one read slow enough to overrun a budget is
    also the one that allocates the most, and abandoning it outlives the caller.
    """
    return [
        sys.executable,
        "-m",
        "pytest",
        "--pyargs",
        "mcp_conformance",
        "-p",
        ACCOUNT_HOOK,
        "-p",
        "no:cacheprovider",
        "-q",
        "-rs",
        "--mcp-endpoint",
        served_url(),
        "--mcp-sample-args",
        str(samples),
        "--mcp-report",
        str(report),
    ]


async def control_genes(step: OwnedStep, bearer: str) -> list[str]:
    """Genes the step really returns, so the write the suite makes is a real one."""
    reset = veupathdb_auth_token_ctx.set(bearer)
    try:
        genes = await fetch_gene_ids_from_step(
            get_strategy_api(SITE), step_id=step.step_id
        )
    finally:
        veupathdb_auth_token_ctx.reset(reset)
    return genes[:CONTROL_GENE_COUNT]


def run_the_suite(
    directory: Path,
    bearer: str,
    second_bearer: str,
    samples: dict[str, Any],
) -> AdmissionRecord:
    """One conformance run, credentialed through the environment the suite reads."""
    sample_file = directory / "sample-arguments.json"
    sample_file.write_text(json.dumps(samples))
    named = os.environ.get(REPORT_VARIABLE, "").strip()
    report = Path(named).resolve() if named else directory / "admission-report.json"
    finished = subprocess.run(  # noqa: S603
        conformance_command(sample_file, report),
        cwd=directory,
        env={
            **os.environ,
            BEARER_VARIABLE: bearer,
            SECOND_BEARER_VARIABLE: second_bearer,
        },
        capture_output=True,
        text=True,
        timeout=RUN_SECONDS,
        check=False,
    )
    assert report.is_file(), (finished.stdout + finished.stderr)[-4000:]
    return AdmissionRecord.model_validate_json(report.read_text())


@pytest.fixture(scope="module")
async def admission_record(
    served_endpoint: str,
    service_bearer: str,
    wdk_registered_token: str | None,
    tmp_path_factory: pytest.TempPathFactory,
) -> AdmissionRecord:
    """The record one run wrote. The step it needs lives only for that run."""
    del served_endpoint
    if wdk_registered_token is None:
        pytest.skip(NO_CREDENTIALS_REASON)
    async with owned_step_for(wdk_registered_token) as step:
        controls = await control_genes(step, wdk_registered_token)
        assert controls
        return run_the_suite(
            tmp_path_factory.mktemp("mcp-conformance"),
            wdk_registered_token,
            service_bearer,
            sample_arguments(step, controls),
        )


def test_no_conformance_check_fails_against_the_served_endpoint(
    admission_record: AdmissionRecord,
) -> None:
    """The admission claim: every family ran and nothing it settled came back wrong."""
    assert admission_record.broken == set()


def test_every_family_ran_against_the_served_endpoint(
    admission_record: AdmissionRecord,
) -> None:
    named = [family.id for family in admission_record.families]
    empty = [family.id for family in admission_record.families if not family.checks]

    assert (tuple(named), empty) == (EXPECTED_FAMILIES, [])


def test_only_the_named_gaps_are_unsettled(
    admission_record: AdmissionRecord,
) -> None:
    """A new skip is a check that stopped running, and it is not an admission."""
    assert admission_record.unsettled == set(UNSETTLED_CHECKS)


def test_the_verdict_reads_incomplete_while_a_gap_remains(
    admission_record: AdmissionRecord,
) -> None:
    """A skipped check is not a passed one, so the record must not read as a pass."""
    assert admission_record.verdict == "incomplete"


def test_the_record_names_this_deployment_and_its_inventory(
    admission_record: AdmissionRecord,
) -> None:
    server = admission_record.server
    declared = {row.fn.__name__ for row in TOOLS}

    assert (server.server_info.name, server.server_info.version) == (
        SERVER_NAME,
        pathfinder_version,
    )
    assert server.protocol_version != ""
    assert {tool.name for tool in admission_record.tools} == declared


def test_the_record_carries_what_each_served_tool_returns(
    admission_record: AdmissionRecord,
) -> None:
    """An operator signs for the payload, so no tool row may omit its schema."""
    unsigned = [
        tool.name for tool in admission_record.tools if tool.output_schema is None
    ]

    assert unsigned == []
