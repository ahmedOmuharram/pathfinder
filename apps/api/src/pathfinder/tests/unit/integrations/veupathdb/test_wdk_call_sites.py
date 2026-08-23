"""Who may open a connection to a WDK host, and what a user path may say.

Neither property is an import, so no import-linter contract can see either.
Both are call sites, so both are read off the syntax tree.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from pathfinder.devtools.wdk_fixtures import load_recorded
from pathfinder.integrations.veupathdb._failures import validation_bundle, wdk_failure
from pathfinder.integrations.veupathdb.client import VEuPathDBClient
from pathfinder.integrations.veupathdb.strategy_api import StrategyAPI
from pathfinder.integrations.veupathdb.wdk_models import WDKSearchConfig

_SOURCE_ROOT = Path(__file__).resolve().parents[4]
_INTEGRATION = "integrations/veupathdb"
_SITE_SOURCES = ("get_site", "SiteInfo", "service_url")
_CURRENT_ALIAS = "/users/current"
# The two calls whose whole job is resolving the concrete id.
_RESOLVERS = (
    "integrations/veupathdb/strategy_api/helpers.py",
    "services/wdk_identity.py",
)


@dataclass(frozen=True)
class _CallSite:
    module: str
    line: int
    detail: str


def _modules() -> list[tuple[str, str]]:
    return [
        (path.relative_to(_SOURCE_ROOT).as_posix(), path.read_text())
        for path in _SOURCE_ROOT.rglob("*.py")
        if "tests/" not in path.relative_to(_SOURCE_ROOT).as_posix()
    ]


def _is_httpx_client(node: ast.Call) -> bool:
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr in {"AsyncClient", "Client"}
        and isinstance(func.value, ast.Name)
        and func.value.id == "httpx"
    )


def _site_backed_clients(module: str, source: str) -> list[_CallSite]:
    """Every httpx client whose base url is resolved from the site router."""
    found: list[_CallSite] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or not _is_httpx_client(node):
            continue
        for keyword in node.keywords:
            if keyword.arg != "base_url":
                continue
            expression = ast.unparse(keyword.value)
            if any(source_name in expression for source_name in _SITE_SOURCES):
                found.append(_CallSite(module, node.lineno, expression))
    return found


def _docstrings(tree: ast.AST) -> set[int]:
    """The id of every string node that is a docstring rather than a value."""
    holders = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, holders) or not node.body:
            continue
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            found.add(id(first.value))
    return found


def _current_alias_literals(module: str, source: str) -> list[_CallSite]:
    """Every string value naming the ``current`` alias, docstrings excluded."""
    tree = ast.parse(source)
    prose = _docstrings(tree)
    return [
        _CallSite(module, node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and _CURRENT_ALIAS in node.value
        and id(node) not in prose
    ]


class TestWdkMap005OnlyTheIntegrationOpensAWdkConnection:
    def test_wdk_map_005_no_module_outside_the_integration_builds_a_site_client(
        self,
    ) -> None:
        offenders = [
            site
            for module, source in _modules()
            if not module.startswith(_INTEGRATION)
            for site in _site_backed_clients(module, source)
        ]

        assert offenders == []

    def test_wdk_map_005_the_check_sees_a_site_backed_client(self) -> None:
        # The property is the base url's origin, not a hostname literal.
        source = (
            "import httpx\n"
            "from pathfinder.integrations.veupathdb.factory import get_site\n"
            "client = httpx.AsyncClient(base_url=get_site(site_id).service_url)\n"
        )

        assert len(_site_backed_clients("transport/http/routers/x.py", source)) == 1

    def test_wdk_map_005_an_unrelated_client_is_not_reported(self) -> None:
        source = "import httpx\nclient = httpx.AsyncClient(base_url=settings.api_url)\n"

        assert _site_backed_clients("services/research/x.py", source) == []


class TestWdkHttp001EveryCallAddressesAConcreteId:
    def test_wdk_http_001_only_the_resolvers_name_the_current_alias(self) -> None:
        offenders = [
            site
            for module, source in _modules()
            if module not in _RESOLVERS
            for site in _current_alias_literals(module, source)
        ]

        assert offenders == []

    async def test_wdk_http_001_a_later_call_carries_the_resolved_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = VEuPathDBClient("https://example.invalid/service")
        api = StrategyAPI(client)
        paths: list[str] = []

        async def get(path: str, **_: object) -> Any:
            paths.append(path)
            return {"id": 4315616, "isGuest": False}

        async def post(path: str, **_: object) -> Any:
            paths.append(path)
            return {"stepTree": {"stepId": 12}}

        monkeypatch.setattr(client, "get", get)
        monkeypatch.setattr(client, "post", post)

        await api.get_duplicated_step_tree(9)

        assert paths == [
            "/users/current",
            "/users/4315616/strategies/9/duplicated-step-tree",
        ]

    async def test_wdk_http_001_the_id_is_resolved_once_per_client(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = VEuPathDBClient("https://example.invalid/service")
        api = StrategyAPI(client)
        paths: list[str] = []

        async def get(path: str, **_: object) -> Any:
            paths.append(path)
            return {"id": 4315616, "isGuest": False}

        async def post(path: str, **_: object) -> Any:
            paths.append(path)
            return {"stepTree": {"stepId": 12}}

        monkeypatch.setattr(client, "get", get)
        monkeypatch.setattr(client, "post", post)

        await api.get_duplicated_step_tree(9)
        await api.get_duplicated_step_tree(10)

        assert paths.count("/users/current") == 1


class TestWdkStrat007AStepBelongsToOneStrategy:
    async def test_wdk_strat_007_reusing_a_branch_asks_for_new_ids(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Two strategies cannot share a subtree, so reuse means copying.
        client = VEuPathDBClient("https://example.invalid/service")
        api = StrategyAPI(client)

        async def get(path: str, **_: object) -> Any:
            del path
            return {"id": 4315616, "isGuest": False}

        async def post(path: str, **_: object) -> Any:
            del path
            return {"stepTree": {"stepId": 77, "primaryInput": {"stepId": 78}}}

        monkeypatch.setattr(client, "get", get)
        monkeypatch.setattr(client, "post", post)

        tree = await api.get_duplicated_step_tree(9)

        assert tree.step_id == 77
        assert tree.primary_input is not None
        assert tree.primary_input.step_id == 78

    def test_wdk_strat_007_a_refusal_names_the_owning_strategy(self) -> None:
        body = "Step 440085983 belongs to strategy 330423363 so cannot be assigned to"

        error = wdk_failure("PUT", "/users/1/strategies/2/step-tree", 422, body)

        assert error.status == 422
        assert "belongs to strategy" in str(error)


class TestWdkStep005ACountNeedsAStrategy:
    async def test_wdk_step_005_a_step_count_addresses_a_step_in_a_strategy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = VEuPathDBClient("https://example.invalid/service")
        api = StrategyAPI(client)
        paths: list[str] = []

        async def get(path: str, **_: object) -> Any:
            del path
            return {"id": 4315616, "isGuest": False}

        async def post(path: str, **_: object) -> Any:
            paths.append(path)
            return {"meta": {"totalCount": 132, "responseCount": 0}, "records": []}

        monkeypatch.setattr(client, "get", get)
        monkeypatch.setattr(client, "post", post)

        assert await api.get_step_count(440085983) == 132
        assert paths == ["/users/4315616/steps/440085983/reports/standard"]

    async def test_wdk_step_005_an_unpersisted_count_uses_the_search_report(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The equivalent with no step and no strategy at all.
        client = VEuPathDBClient("https://example.invalid/service")
        paths: list[str] = []

        async def post(path: str, **_: object) -> Any:
            paths.append(path)
            return {"meta": {"totalCount": 105, "responseCount": 0}, "records": []}

        monkeypatch.setattr(client, "post", post)

        answer = await client.run_search_report(
            "transcript", "GenesByMolecularWeight", WDKSearchConfig()
        )

        assert answer.meta.records_returned() == 105
        assert paths == [
            "/record-types/transcript/searches/GenesByMolecularWeight/reports/standard"
        ]

    def test_wdk_step_005_the_refusal_is_prose_at_level_unspecified(self) -> None:
        body = (
            '{"level":"UNSPECIFIED","isValid":false,"errors":{"general":'
            '["Step 440085953 is not part of a strategy, so cannot run."],"byKey":{}}}'
        )

        bundle = validation_bundle(body)

        assert bundle is not None
        assert bundle.level == "UNSPECIFIED"
        assert bundle.errors is not None
        assert bundle.errors.by_key == {}


def test_the_fixture_store_records_where_every_body_came_from() -> None:
    recorded = load_recorded("search_boolean_transcript")

    assert recorded.provenance.site == "plasmodb"
    assert recorded.provenance.url.startswith("https://plasmodb.org/")
    assert recorded.provenance.recorded_at
