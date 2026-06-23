"""DAG-resolver: Tier-1 (single valid value) auto-resolves; multi-valued params
become choices; the walk fetches a child's vocab under its resolved parent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.services.catalog import param_dag
from pathfinder.services.catalog.param_dag import (
    AutoResolved,
    Choice,
    classify_param,
    resolve_dag,
    resolve_parameter_dag,
)
from pathfinder.services.catalog.param_formatting import ParameterInfo


def _info(
    name: str,
    allowed: list[VocabOption] | None,
    *,
    default: str | None = None,
    required: bool = True,
    depends_on: list[str] | None = None,
) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type="single-pick-vocabulary",
        required=required,
        is_visible=True,
        help="",
        value_format="",
        default_value=default,
        allowed_values=allowed,
        vocab_depends_on=depends_on,
    )


def test_single_valid_value_is_auto_resolved() -> None:
    tier = classify_param(
        _info("strand", [VocabOption(value="sense", display="Sense")])
    )
    assert isinstance(tier, AutoResolved)
    assert tier.name == "strand"
    assert tier.value == "sense"


def test_multiple_valid_values_become_a_choice() -> None:
    tier = classify_param(
        _info(
            "strand",
            [
                VocabOption(value="sense", display="Sense"),
                VocabOption(value="antisense", display="Antisense"),
            ],
            default="sense",
        )
    )
    assert isinstance(tier, Choice)
    assert [o.value for o in tier.options] == ["sense", "antisense"]
    assert tier.default == "sense"


@pytest.mark.asyncio
async def test_flat_search_classifies_each_required_param() -> None:
    async def fetch_at(_ctx: dict[str, str]) -> list[ParameterInfo]:
        return [
            _info("strand", [VocabOption(value="sense", display="Sense")]),
            _info(
                "organism",
                [
                    VocabOption(value="pf", display="P. falciparum"),
                    VocabOption(value="pv", display="P. vivax"),
                ],
            ),
        ]

    res = await resolve_dag(fetch_at=fetch_at)
    assert [a.name for a in res.auto_resolved] == ["strand"]
    assert [a.value for a in res.auto_resolved] == ["sense"]
    assert [c.name for c in res.choices] == ["organism"]


@pytest.mark.asyncio
async def test_child_vocab_fetched_under_resolved_parent() -> None:
    seen: list[dict[str, str]] = []

    async def fetch_at(ctx: dict[str, str]) -> list[ParameterInfo]:
        seen.append(dict(ctx))
        profileset = _info(
            "profileset", [VocabOption(value="exp1", display="Experiment 1")]
        )
        if ctx.get("profileset") == "exp1":
            samples = _info(
                "samples",
                [
                    VocabOption(value="ref", display="Reference"),
                    VocabOption(value="comp", display="Comparison"),
                ],
                depends_on=["profileset"],
            )
        else:
            samples = _info("samples", None, depends_on=["profileset"])
        return [profileset, samples]

    res = await resolve_dag(fetch_at=fetch_at)

    assert [a.name for a in res.auto_resolved] == ["profileset"]
    samples_choice = next(c for c in res.choices if c.name == "samples")
    assert [o.value for o in samples_choice.options] == ["ref", "comp"]
    assert {"profileset": "exp1"} in seen
    # the context-refreshed infos are exposed so the tool can snapshot + summarise
    samples_info = next(i for i in res.param_infos if i.name == "samples")
    assert samples_info.allowed_values is not None
    assert [v.value for v in samples_info.allowed_values] == ["ref", "comp"]


@pytest.mark.asyncio
async def test_resolve_parameter_dag_wires_client_to_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = MagicMock()
    raw.name = "strand"
    raw.dependent_params = []
    details = MagicMock()
    details.search_data.parameters = [raw]
    client = MagicMock()
    client.get_search_details = AsyncMock(return_value=details)
    monkeypatch.setattr(param_dag, "get_wdk_client", lambda _site: client)
    monkeypatch.setattr(
        param_dag,
        "format_param_info_typed",
        lambda _params: [
            _info("strand", [VocabOption(value="sense", display="Sense")])
        ],
    )

    res = await resolve_parameter_dag(
        site_id="plasmodb", record_type="transcript", search_name="GenesByRNASeq"
    )

    assert [a.name for a in res.auto_resolved] == ["strand"]
    assert [a.value for a in res.auto_resolved] == ["sense"]
    client.get_search_details.assert_awaited()
