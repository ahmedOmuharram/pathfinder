"""Deterministic resolution of a WDK search's parameter dependency DAG."""

from __future__ import annotations

import graphlib
from collections.abc import Awaitable, Callable
from typing import Annotated, Literal

from pydantic import Field

from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.catalog.param_formatting import (
    ParameterInfo,
    format_param_info_typed,
)
from pathfinder.services.wdk import get_wdk_client


class AutoResolved(CamelModel):
    """A param with a single valid value — set in code, no choice to make."""

    kind: Literal["auto_resolved"] = "auto_resolved"
    name: str
    value: str


class Choice(CamelModel):
    """A multi-valued param — the model maps intent to a value, or it becomes
    an editable plan slot for the user."""

    kind: Literal["choice"] = "choice"
    name: str
    options: list[VocabOption] = Field(default_factory=list)
    default: str | None = None
    help: str = ""


ParamTier = Annotated[AutoResolved | Choice, Field(discriminator="kind")]


def classify_param(info: ParameterInfo) -> ParamTier:
    values = info.allowed_values or []
    if len(values) == 1:
        return AutoResolved(name=info.name, value=values[0].value)
    return Choice(
        name=info.name,
        options=values,
        default=info.default_value,
        help=info.help,
    )


ParamFetcher = Callable[[dict[str, str]], Awaitable[list[ParameterInfo]]]


class DagResolution(CamelModel):
    auto_resolved: list[AutoResolved] = Field(default_factory=list)
    choices: list[Choice] = Field(default_factory=list)
    param_infos: list[ParameterInfo] = Field(default_factory=list)


async def resolve_dag(
    *,
    fetch_at: ParamFetcher,
    chosen_values: dict[str, str] | None = None,
) -> DagResolution:
    context = dict(chosen_values or {})
    infos = await fetch_at(context)
    last_context = dict(context)
    required = {i.name: i for i in infos if i.required}
    graph = {
        name: set(info.vocab_depends_on or []) & required.keys()
        for name, info in required.items()
    }
    fill_order = list(graphlib.TopologicalSorter(graph).static_order())

    auto_resolved: list[AutoResolved] = []
    choices: list[Choice] = []
    param_infos: list[ParameterInfo] = []
    for name in fill_order:
        if context != last_context:
            infos = await fetch_at(context)
            last_context = dict(context)
        info = next((i for i in infos if i.name == name), None)
        if info is None:
            continue
        param_infos.append(info)
        tier = classify_param(info)
        if isinstance(tier, AutoResolved):
            context[name] = tier.value
            auto_resolved.append(tier)
        else:
            choices.append(tier)
    return DagResolution(
        auto_resolved=auto_resolved, choices=choices, param_infos=param_infos
    )


async def resolve_parameter_dag(
    *,
    site_id: str,
    record_type: str,
    search_name: str,
    chosen_values: dict[str, str] | None = None,
) -> DagResolution:
    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        client = get_wdk_client(site_id)
        if context:
            resp = await client.get_search_details_with_params(
                record_type, search_name, context=context
            )
        else:
            resp = await client.get_search_details(record_type, search_name)
        params = resp.search_data.parameters or []
        return format_param_info_typed(params)

    return await resolve_dag(fetch_at=fetch_at, chosen_values=chosen_values)
