"""The service half of the four split catalog tools.

Every function here takes a site and its arguments by value. It holds no agent
state and imports nothing from ``pathfinder.ai``, so the MCP server can call
the same code the in-process tools call.
"""

from __future__ import annotations

import ast
from importlib.util import resolve_name
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

import pathfinder
from pathfinder.devtools.wdk_fixtures import load_recorded
from pathfinder.domain.parameters.values import SinglePickValue
from pathfinder.integrations.veupathdb.wdk_models import WDKSearchResponse
from pathfinder.platform.errors import WDKError
from pathfinder.services.catalog import search_inspection, searches
from pathfinder.services.catalog.search_inspection import (
    UnknownSearchError,
    inspect_search,
    read_parameter_options,
)
from pathfinder.services.catalog.searches import VagueSearchQueryError


def _response(name: str) -> WDKSearchResponse:
    return WDKSearchResponse.model_validate(load_recorded(name).json_body())


def _stub_client(monkeypatch: pytest.MonkeyPatch, fixture: str) -> MagicMock:
    response = _response(fixture)
    client = MagicMock()
    client.get_search_details = AsyncMock(return_value=response)
    client.get_search_details_with_params = AsyncMock(return_value=response)
    monkeypatch.setattr(searches, "get_wdk_client", lambda _site: client)
    monkeypatch.setattr(search_inspection, "get_wdk_client", lambda _site: client)
    return client


class TestInspectSearch:
    async def test_it_returns_the_overview_and_the_definition_it_came_from(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_client(monkeypatch, "search_genes_by_molecular_weight")

        result = await inspect_search(
            "plasmodb",
            "GenesByMolecularWeight",
            record_type="transcript",
            query="molecular weight of kinases",
        )

        assert result.record_type == "transcript"
        assert result.definition.url_segment == "GenesByMolecularWeight"
        assert [p.name for p in result.definition.parameters or []] == [
            "organism",
            "min_molecular_weight",
            "max_molecular_weight",
        ]
        assert result.overview.search_name == "GenesByMolecularWeight"
        assert result.overview.display_name == "Molecular Weight"
        assert [entry.name for entry in result.overview.required] == [
            "organism",
            "min_molecular_weight",
            "max_molecular_weight",
        ]
        assert result.overview.optional == []

    async def test_it_ranks_without_a_query(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_client(monkeypatch, "search_genes_by_molecular_weight")

        result = await inspect_search(
            "plasmodb", "GenesByMolecularWeight", record_type="transcript"
        )

        assert [entry.name for entry in result.overview.required] == [
            "organism",
            "min_molecular_weight",
            "max_molecular_weight",
        ]

    async def test_it_resolves_the_record_type_when_none_is_given(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_client(monkeypatch, "search_genes_by_molecular_weight")

        async def _resolve(_site: str, _search: str, _rt: str | None) -> str:
            return "transcript"

        monkeypatch.setattr(search_inspection, "resolve_search_record_type", _resolve)

        result = await inspect_search("plasmodb", "GenesByMolecularWeight")

        assert result.record_type == "transcript"

    async def test_an_unknown_search_names_the_valid_ones(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = MagicMock()
        client.get_search_details = AsyncMock(
            side_effect=WDKError("Resource 'search: Nope' does not exist.", status=404)
        )
        monkeypatch.setattr(searches, "get_wdk_client", lambda _site: client)

        async def _valid(_site: str, _rt: str) -> list[Any]:
            return [_raw("GenesByMolecularWeight"), _raw("GenesByLocation")]

        monkeypatch.setattr(search_inspection, "get_raw_searches", _valid)

        with pytest.raises(UnknownSearchError) as excinfo:
            await inspect_search(
                "plasmodb", "GenesByMolecularWeigh", record_type="transcript"
            )

        guidance = excinfo.value.guidance
        assert "GenesByMolecularWeigh" in guidance
        assert "GenesByMolecularWeight" in guidance
        assert "Valid search values" in guidance

    async def test_a_non_404_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        client.get_search_details = AsyncMock(
            side_effect=WDKError("upstream 502", status=502)
        )
        monkeypatch.setattr(searches, "get_wdk_client", lambda _site: client)

        with pytest.raises(WDKError):
            await inspect_search("plasmodb", "Whatever", record_type="transcript")


def _raw(name: str) -> Any:
    raw = MagicMock()
    raw.url_segment = name
    return raw


class TestReadParameterOptions:
    async def test_it_formats_one_parameter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_client(monkeypatch, "search_genes_by_location")

        result = await read_parameter_options(
            "plasmodb",
            "GenesByLocation",
            "organismSinglePick",
            record_type="transcript",
        )

        assert result.kind == "parameter_info"
        assert result.name == "organismSinglePick"
        assert result.controls_vocab_of == ["chromosomeOptional"]
        assert result.allowed_values

    async def test_a_query_narrows_the_vocabulary(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_client(monkeypatch, "search_genes_by_location")

        whole = await read_parameter_options(
            "plasmodb",
            "GenesByLocation",
            "organismSinglePick",
            record_type="transcript",
        )
        narrowed = await read_parameter_options(
            "plasmodb",
            "GenesByLocation",
            "organismSinglePick",
            record_type="transcript",
            query="falciparum",
        )

        assert whole.kind == "parameter_info"
        assert narrowed.kind == "parameter_info"
        assert narrowed.allowed_values is not None
        assert whole.allowed_values is not None
        assert 0 < len(narrowed.allowed_values) < len(whole.allowed_values)
        assert all(
            "falciparum" in option.value.lower()
            or "falciparum" in option.display.lower()
            for option in narrowed.allowed_values
        )

    async def test_a_dependent_parameter_asks_for_its_parent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_client(monkeypatch, "search_genes_by_location")

        result = await read_parameter_options(
            "plasmodb",
            "GenesByLocation",
            "chromosomeOptional",
            record_type="transcript",
        )

        assert result.kind == "parent_context_required"
        assert result.parent_parameter_ids == ["organismSinglePick"]

    async def test_context_travels_by_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = _stub_client(monkeypatch, "search_genes_by_location")

        result = await read_parameter_options(
            "plasmodb",
            "GenesByLocation",
            "chromosomeOptional",
            record_type="transcript",
            context_values={"organismSinglePick": "Plasmodium falciparum 3D7"},
        )

        assert result.kind == "parameter_info"
        assert client.get_search_details_with_params.await_count == 1
        context = client.get_search_details_with_params.await_args.kwargs["context"]
        assert context["organismSinglePick"] == "Plasmodium falciparum 3D7"

    async def test_it_accepts_already_typed_context(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = _stub_client(monkeypatch, "search_genes_by_location")

        result = await read_parameter_options(
            "plasmodb",
            "GenesByLocation",
            "chromosomeOptional",
            record_type="transcript",
            context_values={
                "organismSinglePick": SinglePickValue(value="Plasmodium falciparum 3D7")
            },
        )

        assert result.kind == "parameter_info"
        context = client.get_search_details_with_params.await_args.kwargs["context"]
        assert context["organismSinglePick"] == "Plasmodium falciparum 3D7"

    async def test_an_unknown_parameter_names_the_valid_ones(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_client(monkeypatch, "search_genes_by_location")

        result = await read_parameter_options(
            "plasmodb",
            "GenesByLocation",
            "organism_single_pick",
            record_type="transcript",
        )

        assert result.kind == "parameter_not_on_search"
        assert result.suggestions == ["organismSinglePick"]
        assert result.valid_parameter_ids == [
            "chromosomeOptional",
            "end_point",
            "organismSinglePick",
            "sequenceId",
            "start_point",
        ]


class TestSearchQueryGuard:
    async def test_an_empty_query_is_refused(self) -> None:
        with pytest.raises(VagueSearchQueryError) as excinfo:
            await searches.search_for_searches("plasmodb", "transcript", "")

        assert excinfo.value.rejection.error == "query_required"

    async def test_a_one_word_query_is_refused(self) -> None:
        with pytest.raises(VagueSearchQueryError) as excinfo:
            await searches.search_for_searches("plasmodb", "transcript", "gene")

        rejection = excinfo.value.rejection
        assert rejection.error == "query_too_vague"
        assert rejection.query == "gene"
        assert rejection.examples

    async def test_keywords_carry_a_short_query(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorded: dict[str, Any] = {}

        async def _resolve(*_a: Any, **_k: Any) -> list[str]:
            recorded["called"] = True
            return ["transcript"]

        monkeypatch.setattr(searches, "resolve_record_types", _resolve)
        monkeypatch.setattr(searches, "get_discovery_service", MagicMock())

        async def _collect(*_a: Any, **_k: Any) -> list[Any]:
            return []

        async def _no_bonus(*_a: Any, **_k: Any) -> None:
            return None

        monkeypatch.setattr(searches, "collect_search_candidates", _collect)
        monkeypatch.setattr(searches, "apply_site_search_bonus", _no_bonus)
        monkeypatch.setattr(searches, "apply_semantic_bonus", _no_bonus)

        result = await searches.search_for_searches(
            "plasmodb", "transcript", "gene", keywords=["Su_strand_specific"]
        )

        assert result == []
        assert recorded["called"] is True


_SOURCE_ROOT = Path(pathfinder.__file__).parent.parent
_SERVICE_ENTRY_POINTS = (
    "pathfinder.services.catalog.search_inspection",
    "pathfinder.services.catalog.searches",
)


def _source_of(module: str) -> Path | None:
    """The file a first-party module lives in. ``None`` for a third-party name."""
    base = _SOURCE_ROOT.joinpath(*module.split("."))
    single = base.with_suffix(".py")
    if single.is_file():
        return single
    package = base / "__init__.py"
    return package if package.is_file() else None


def _imports_of(module: str, path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            package = module.rsplit(".", 1)[0] if path.name != "__init__.py" else module
            names.add(
                resolve_name("." * node.level + (node.module or ""), package)
                if node.level
                else (node.module or "")
            )
    return names


def _modules_reachable_from(entry_points: tuple[str, ...]) -> set[str]:
    """Every module name the entry points pull in, first-party walk, leaves included."""
    seen: set[str] = set()
    pending = list(entry_points)
    while pending:
        module = pending.pop()
        if module in seen:
            continue
        seen.add(module)
        source = _source_of(module)
        if source is not None:
            pending.extend(_imports_of(module, source))
    return seen


class TestTheServiceHalfCarriesNoAgentSurface:
    def test_nothing_it_reaches_imports_pydantic_ai(self) -> None:
        """The MCP server holds no agent framework, so the read must load without one."""
        reached = _modules_reachable_from(_SERVICE_ENTRY_POINTS)

        assert [
            name for name in sorted(reached) if name.startswith("pydantic_ai")
        ] == []

    def test_the_control_module_is_caught(self) -> None:
        """The walk finds a real dependency, so a green result is not a blind spot."""
        reached = _modules_reachable_from(
            ("pathfinder.ai.tools.standalone.catalog_discovery",)
        )

        assert "pydantic_ai" in reached

    def test_the_split_halves_take_a_site_and_no_state(self) -> None:
        signatures = {
            "inspect_search": inspect_search,
            "read_parameter_options": read_parameter_options,
            "search_for_searches": searches.search_for_searches,
            "list_searches": searches.list_searches,
        }

        for name, function in signatures.items():
            params = list(
                function.__code__.co_varnames[: function.__code__.co_argcount]
            )
            assert params[0] == "site_id", name
            assert "ctx" not in params, name
            assert "agent_state" not in params, name
            assert "deps" not in params, name
