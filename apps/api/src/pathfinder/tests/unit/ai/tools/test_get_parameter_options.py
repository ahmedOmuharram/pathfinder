"""Tests for the parameter-options tool: unknown names, repeat reads, and bound context."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.tools.standalone import catalog_discovery
from pathfinder.ai.tools.standalone.catalog_discovery import AlreadyReadNotice
from pathfinder.domain.parameters.values import SinglePickValue
from pathfinder.domain.parameters.wdk_vocab import WDKVocabTerm
from pathfinder.domain.strategy.operational_spec import Criterion
from pathfinder.integrations.veupathdb.wdk_parameters import (
    WDKEnumParam,
    WDKParameter,
    WDKStringParam,
)
from pathfinder.services.catalog.param_formatting import (
    ParameterInfo,
    ParameterNotOnSearch,
)


def _ctx() -> Any:
    ctx = MagicMock()
    ctx.deps = MagicMock()
    ctx.deps.site_id = "plasmodb"
    ctx.deps.agent_state = AgentToolState()
    return ctx


def _wdk_param(name: str) -> Any:
    """Build a WDK parameter stub that carries only the fields the tool reads."""
    p = MagicMock()
    p.name = name
    p.dependent_params = []
    return p


def _patch_resolve_and_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    record_type: str,
    param_names: list[str],
) -> None:
    async def _resolve(*_args: Any, **_kw: Any) -> str:
        return record_type

    monkeypatch.setattr(catalog_discovery, "_resolve_record_type", _resolve)

    fake_details = MagicMock()
    fake_details.search_data.parameters = [_wdk_param(n) for n in param_names]
    client = MagicMock()
    client.get_search_details = AsyncMock(return_value=fake_details)

    def _get_client(_site_id: str) -> Any:
        return client

    monkeypatch.setattr(catalog_discovery, "get_wdk_client", _get_client)


def _patch_context_client(
    monkeypatch: pytest.MonkeyPatch, param_names: list[str]
) -> Any:
    """Build a client that records the context-carrying read."""

    async def _resolve(*_args: Any, **_kw: Any) -> str:
        return "transcript"

    monkeypatch.setattr(catalog_discovery, "_resolve_record_type", _resolve)
    details = MagicMock()
    details.search_data.parameters = [_wdk_param(n) for n in param_names]
    client = MagicMock()
    client.get_search_details_with_params = AsyncMock(return_value=details)
    client.get_search_details = AsyncMock(return_value=details)
    monkeypatch.setattr(catalog_discovery, "get_wdk_client", lambda _s: client)
    return client


@pytest.mark.asyncio
async def test_known_parameter_returns_normally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid parameter ID returns the formatted parameter info."""
    _patch_resolve_and_client(
        monkeypatch,
        record_type="transcript",
        param_names=["min_pct_idents", "min_overlap_size"],
    )
    fake_info = MagicMock()
    monkeypatch.setattr(
        catalog_discovery,
        "format_typed_param",
        lambda *args, **kw: fake_info,
    )
    result = await catalog_discovery.get_parameter_options(
        _ctx(),
        search_name="GenesByESTOverlap",
        parameter_id="min_pct_idents",
    )
    assert result is fake_info


@pytest.mark.asyncio
async def test_unknown_parameter_returns_not_on_search_with_close_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unknown parameter ID returns the close match, the valid list, and the search name."""
    _patch_resolve_and_client(
        monkeypatch,
        record_type="transcript",
        param_names=[
            "min_pct_idents",
            "min_overlap_size",
            "datasets",
            "expansion_factor",
        ],
    )
    result = await catalog_discovery.get_parameter_options(
        _ctx(),
        search_name="GenesByESTOverlap",
        parameter_id="minOverlap",
    )
    assert isinstance(result, ParameterNotOnSearch)
    assert result.requested_parameter_id == "minOverlap"
    assert result.search_name == "GenesByESTOverlap"
    assert "min_overlap_size" in result.suggestions
    assert set(result.valid_parameter_ids) == {
        "min_pct_idents",
        "min_overlap_size",
        "datasets",
        "expansion_factor",
    }
    assert "minOverlap" in result.message
    assert "GenesByESTOverlap" in result.message


@pytest.mark.asyncio
async def test_no_close_match_still_lists_all_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A parameter ID with no close match still returns the full valid list."""
    _patch_resolve_and_client(
        monkeypatch,
        record_type="transcript",
        param_names=["taxon", "go_term"],
    )
    result = await catalog_discovery.get_parameter_options(
        _ctx(),
        search_name="GenesByGoTerm",
        parameter_id="completely_unrelated_xyz",
    )
    assert isinstance(result, ParameterNotOnSearch)
    assert result.requested_parameter_id == "completely_unrelated_xyz"
    assert set(result.valid_parameter_ids) == {"taxon", "go_term"}
    assert "completely_unrelated_xyz" in result.message
    assert "taxon" in result.message
    assert "go_term" in result.message


@pytest.mark.asyncio
async def test_second_identical_read_returns_already_read_notice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A repeat read of the same parameter returns an already-read notice."""
    _patch_resolve_and_client(
        monkeypatch,
        record_type="transcript",
        param_names=["go_term", "taxon"],
    )
    fake_info = MagicMock()
    monkeypatch.setattr(
        catalog_discovery,
        "format_typed_param",
        lambda *args, **kw: fake_info,
    )
    ctx = _ctx()
    first = await catalog_discovery.get_parameter_options(
        ctx,
        search_name="GenesByGoTerm",
        parameter_id="go_term",
    )
    assert first is fake_info

    second = await catalog_discovery.get_parameter_options(
        ctx,
        search_name="GenesByGoTerm",
        parameter_id="go_term",
    )
    assert isinstance(second, AlreadyReadNotice)
    assert second.search_name == "GenesByGoTerm"
    assert second.parameter_id == "go_term"


@pytest.mark.asyncio
async def test_failed_read_is_not_marked_so_retry_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed read stays unmarked, so a corrected name still reads the options."""
    _patch_resolve_and_client(
        monkeypatch,
        record_type="transcript",
        param_names=["go_term", "taxon"],
    )
    fake_info = MagicMock()
    monkeypatch.setattr(
        catalog_discovery,
        "format_typed_param",
        lambda *args, **kw: fake_info,
    )
    ctx = _ctx()
    wrong = await catalog_discovery.get_parameter_options(
        ctx,
        search_name="GenesByGoTerm",
        parameter_id="goTerm",
    )
    assert isinstance(wrong, ParameterNotOnSearch)

    fixed = await catalog_discovery.get_parameter_options(
        ctx,
        search_name="GenesByGoTerm",
        parameter_id="go_term",
    )
    assert fixed is fake_info


class TestInheritsBoundParentContext:
    """A read with no explicit context must still send the parent values the spec binds.

    Without them, WDK answers from the search defaults.
    """

    @staticmethod
    def _ctx_with_bound_profileset() -> Any:
        ctx = _ctx()
        ctx.deps.agent_state.frame_set_criterion(
            Criterion(
                id="timecourse",
                text="trophozoite expression",
                search_name="GenesByMicroarrayDerisi",
                resolved_params={
                    "profileset_generic": SinglePickValue(value="DeRisi 3D7 Smoothed")
                },
            )
        )
        return ctx

    @pytest.mark.asyncio
    async def test_sends_the_bound_parent_to_wdk(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = _patch_context_client(monkeypatch, ["samples_percentile_generic"])
        monkeypatch.setattr(
            catalog_discovery, "format_typed_param", lambda *a, **k: MagicMock()
        )

        await catalog_discovery.get_parameter_options(
            self._ctx_with_bound_profileset(),
            search_name="GenesByMicroarrayDerisi",
            parameter_id="samples_percentile_generic",
        )

        client.get_search_details_with_params.assert_awaited_once()
        context = client.get_search_details_with_params.await_args.kwargs["context"]
        assert context["profileset_generic"] == "DeRisi 3D7 Smoothed"

    @pytest.mark.asyncio
    async def test_explicit_context_overrides_the_bound_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = _patch_context_client(monkeypatch, ["samples_percentile_generic"])
        monkeypatch.setattr(
            catalog_discovery, "format_typed_param", lambda *a, **k: MagicMock()
        )

        await catalog_discovery.get_parameter_options(
            self._ctx_with_bound_profileset(),
            search_name="GenesByMicroarrayDerisi",
            parameter_id="samples_percentile_generic",
            context_values={"profileset_generic": "DeRisi Dd2 Smoothed"},
        )

        context = client.get_search_details_with_params.await_args.kwargs["context"]
        assert context["profileset_generic"] == "DeRisi Dd2 Smoothed"

    @pytest.mark.asyncio
    async def test_unbound_search_still_reads_without_context(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_resolve_and_client(
            monkeypatch, record_type="transcript", param_names=["go_term"]
        )
        monkeypatch.setattr(
            catalog_discovery, "format_typed_param", lambda *a, **k: MagicMock()
        )

        result = await catalog_discovery.get_parameter_options(
            _ctx(), search_name="GenesByGoTerm", parameter_id="go_term"
        )

        assert not isinstance(result, ParameterNotOnSearch)

    @pytest.mark.asyncio
    async def test_inherited_context_reaches_the_formatter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_context_client(monkeypatch, ["samples_percentile_generic"])
        seen: dict[str, Any] = {}

        def _format(*_a: Any, **kw: Any) -> Any:
            seen.update(kw)
            return MagicMock()

        monkeypatch.setattr(catalog_discovery, "format_typed_param", _format)

        await catalog_discovery.get_parameter_options(
            self._ctx_with_bound_profileset(),
            search_name="GenesByMicroarrayDerisi",
            parameter_id="samples_percentile_generic",
        )

        assert seen["applied_context"] == {
            "profileset_generic": SinglePickValue(value="DeRisi 3D7 Smoothed")
        }


def _dependent_param(name: str, parents: list[str]) -> Any:
    """A parameter whose vocabulary changes with its parents' values."""
    p = MagicMock()
    p.name = name
    p.dependent_params = []
    p.depends_on = parents
    return p


def _patch_with_dependency(
    monkeypatch: pytest.MonkeyPatch, child: str, parent: str
) -> Any:
    async def _resolve(*_args: Any, **_kw: Any) -> str:
        return "transcript"

    monkeypatch.setattr(catalog_discovery, "_resolve_record_type", _resolve)
    parent_param = _wdk_param(parent)
    parent_param.dependent_params = [child]
    details = MagicMock()
    details.search_data.parameters = [parent_param, _wdk_param(child)]
    client = MagicMock()
    client.get_search_details = AsyncMock(return_value=details)
    client.get_search_details_with_params = AsyncMock(return_value=details)
    monkeypatch.setattr(catalog_discovery, "get_wdk_client", lambda _s: client)
    return client


class TestADependentReadNeedsItsParent:
    """The vocabulary differs per parent, so an unqualified read is a guess.

    Measured live: the DeRisi 3D7 profileset offers hours 23 and 29 and the HB3
    profileset does not, so a selection made under the default silently omits
    them.
    """

    @pytest.mark.asyncio
    async def test_an_unbound_parent_does_not_return_a_term_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_with_dependency(
            monkeypatch, "samples_percentile_generic", "profileset_generic"
        )

        result = await catalog_discovery.get_parameter_options(
            _ctx(),
            search_name="GenesByProfile",
            parameter_id="samples_percentile_generic",
        )

        assert isinstance(result, catalog_discovery.ParentContextRequired)

    @pytest.mark.asyncio
    async def test_it_names_the_parent_to_bind(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_with_dependency(
            monkeypatch, "samples_percentile_generic", "profileset_generic"
        )

        result = await catalog_discovery.get_parameter_options(
            _ctx(),
            search_name="GenesByProfile",
            parameter_id="samples_percentile_generic",
        )

        assert isinstance(result, catalog_discovery.ParentContextRequired)
        assert result.parent_parameter_ids == ["profileset_generic"]

    @pytest.mark.asyncio
    async def test_an_explicit_context_is_answered(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_with_dependency(
            monkeypatch, "samples_percentile_generic", "profileset_generic"
        )
        fake_info = MagicMock()
        monkeypatch.setattr(
            catalog_discovery, "format_typed_param", lambda *a, **kw: fake_info
        )

        result = await catalog_discovery.get_parameter_options(
            _ctx(),
            search_name="GenesByProfile",
            parameter_id="samples_percentile_generic",
            context_values={"profileset_generic": "DeRisi 3D7 Smoothed"},
        )

        assert result is fake_info

    @pytest.mark.asyncio
    async def test_a_parameter_with_no_parents_is_unaffected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_resolve_and_client(
            monkeypatch, record_type="transcript", param_names=["organism"]
        )
        fake_info = MagicMock()
        monkeypatch.setattr(
            catalog_discovery, "format_typed_param", lambda *a, **kw: fake_info
        )

        result = await catalog_discovery.get_parameter_options(
            _ctx(), search_name="GenesByTaxon", parameter_id="organism"
        )

        assert result is fake_info


def _term(code: str, display: str) -> WDKVocabTerm:
    return WDKVocabTerm((code, display, None))


_PHYLETIC_PARAMS: list[WDKParameter] = [
    WDKStringParam(name="profile_pattern", is_visible=False),
    WDKStringParam(
        name="included_species", allow_empty_value=True, initial_display_value=""
    ),
    WDKStringParam(
        name="excluded_species", allow_empty_value=True, initial_display_value=""
    ),
    WDKEnumParam(
        name="phyletic_term_map",
        type="multi-pick-vocabulary",
        vocabulary=[
            _term("ALL", "Root"),
            _term("EUKA", "Eukaryota"),
            _term("MAMM", "Mammalia"),
            _term("hsap", "Homo sapiens REF"),
            _term("pfal", "Plasmodium falciparum 3D7"),
        ],
    ),
    WDKEnumParam(
        name="phyletic_indent_map",
        type="multi-pick-vocabulary",
        vocabulary=[
            _term("EUKA", "1"),
            _term("MAMM", "2"),
            _term("hsap", "3"),
            _term("pfal", "2"),
        ],
    ),
]


def _patch_phyletic_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve the real ``GenesByOrthologPattern`` parameter shapes."""

    async def _resolve(*_args: Any, **_kw: Any) -> str:
        return "transcript"

    monkeypatch.setattr(catalog_discovery, "_resolve_record_type", _resolve)
    details = MagicMock()
    details.search_data.parameters = _PHYLETIC_PARAMS
    client = MagicMock()
    client.get_search_details = AsyncMock(return_value=details)
    client.get_search_details_with_params = AsyncMock(return_value=details)
    monkeypatch.setattr(catalog_discovery, "get_wdk_client", lambda _s: client)


class TestReadingOnePhyleticList:
    """A single-parameter read must show the same vocabulary the sheet shows.

    The two lists carry no WDK vocabulary of their own, so without the clade
    tree the model reads an empty option list and writes species names.
    """

    @staticmethod
    async def _read(
        monkeypatch: pytest.MonkeyPatch,
        *,
        parameter_id: str = "included_species",
        query: str | None = None,
    ) -> Any:
        _patch_phyletic_client(monkeypatch)
        return await catalog_discovery.get_parameter_options(
            _ctx(),
            search_name="GenesByOrthologPattern",
            parameter_id=parameter_id,
            query=query,
        )

    @pytest.mark.asyncio
    async def test_a_query_returns_the_matching_species(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        info = await self._read(monkeypatch, query="homo")

        assert isinstance(info, ParameterInfo)
        assert info.allowed_values is not None
        assert [(o.value, o.display) for o in info.allowed_values] == [
            ("hsap", "Homo sapiens REF")
        ]

    @pytest.mark.asyncio
    async def test_a_common_name_matches_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The filter is a substring over codes and scientific names, so 'human'
        # does not reach 'Homo sapiens REF'.
        info = await self._read(monkeypatch, query="human")

        assert isinstance(info, ParameterInfo)
        assert info.allowed_values is None

    @pytest.mark.asyncio
    async def test_the_read_carries_the_derivation_sentence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        info = await self._read(monkeypatch, query="homo")

        assert isinstance(info, ParameterInfo)
        assert "profile_pattern is derived from these two lists" in info.help

    @pytest.mark.asyncio
    async def test_a_code_query_matches_too(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        info = await self._read(monkeypatch, query="PFAL")

        assert isinstance(info, ParameterInfo)
        assert info.allowed_values is not None
        assert [o.value for o in info.allowed_values] == ["pfal"]

    @pytest.mark.asyncio
    async def test_no_query_returns_the_whole_tree(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        info = await self._read(monkeypatch, parameter_id="excluded_species")

        assert isinstance(info, ParameterInfo)
        assert info.allowed_values is not None
        assert [o.value for o in info.allowed_values] == [
            "EUKA",
            "MAMM",
            "hsap",
            "pfal",
        ]

    @pytest.mark.asyncio
    async def test_the_hidden_pattern_gains_no_tree(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        info = await self._read(monkeypatch, parameter_id="profile_pattern")

        assert isinstance(info, ParameterInfo)
        assert info.allowed_values is None
