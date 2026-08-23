"""The site-help agent: one agent, two read-only catalog tools."""

from __future__ import annotations

from assistant_core.graph.runtime import AssistantDeps
from assistant_core.platform.pydantic_base import CamelModel
from pydantic_ai import Agent, ModelRetry, Tool
from pydantic_ai.models import Model

from pathfinder.assistants.site_help.mock import build_site_help_mock
from pathfinder.platform.config import get_settings
from pathfinder.services.catalog.searches import get_raw_searches
from pathfinder.services.catalog.sites import get_record_types, list_sites

SITE_HELP_MODEL = "openai:gpt-5.6-luna"

type SiteHelpAgent = Agent[AssistantDeps, str]

SITE_HELP_INSTRUCTIONS = (
    "You help researchers find their way around the VEuPathDB family of "
    "sites. Answer in plain markdown, briefly.\n\n"
    "Use `list_veupathdb_sites` to name the sites and what each one covers, "
    "and `describe_site` to report one site's record types and how many "
    "searches each of them offers. Both tools read the live catalog: quote "
    "what they return and never invent a site, a record type or a count.\n\n"
    "You do not build strategies, run searches or change anything. When a "
    "request needs that, say so and point at the site the work belongs on."
)


class SiteSummary(CamelModel):
    """One VEuPathDB site, as the catalog registers it."""

    site_id: str
    display_name: str
    url: str


class RecordTypeSummary(CamelModel):
    """One record type a site serves, with how many searches reach it."""

    name: str
    display_name: str
    search_count: int


class SiteDetail(CamelModel):
    """What one site offers, by record type."""

    site_id: str
    display_name: str
    record_types: list[RecordTypeSummary]


async def list_veupathdb_sites() -> list[SiteSummary]:
    """List every VEuPathDB site this deployment can reach.

    Call this when the user asks which sites exist, which one covers an
    organism, or where a kind of data lives.
    """
    return [
        SiteSummary(site_id=site.id, display_name=site.display_name, url=site.base_url)
        for site in await list_sites()
    ]


async def describe_site(site_id: str) -> SiteDetail:
    """Report one site's record types and the search count of each.

    ``site_id`` is the id ``list_veupathdb_sites`` returns, such as
    ``plasmodb``. Call this when the user asks what a site holds or what
    they can search there.
    """
    sites = {site.id: site for site in await list_sites()}
    site = sites.get(site_id)
    if site is None:
        msg = f"Unknown site {site_id!r}. The sites are: {sorted(sites)}."
        raise ModelRetry(msg)
    record_types = await get_record_types(site_id)
    summaries = [
        RecordTypeSummary(
            name=record_type.name,
            display_name=record_type.display_name,
            search_count=len(await get_raw_searches(site_id, record_type.name)),
        )
        for record_type in record_types
    ]
    return SiteDetail(
        site_id=site.id,
        display_name=site.display_name,
        record_types=summaries,
    )


def _model() -> Model | str:
    """The mock provider swaps the whole model, so the turn makes no request."""
    if get_settings().pathfinder_chat_provider.strip().lower() == "mock":
        return build_site_help_mock()
    return SITE_HELP_MODEL


def build_site_help_agent() -> SiteHelpAgent:
    """A site-help agent for one turn."""
    return Agent(
        _model(),
        output_type=str,
        deps_type=AssistantDeps,
        instructions=SITE_HELP_INSTRUCTIONS,
        tools=[Tool(list_veupathdb_sites), Tool(describe_site)],
        retries=2,
        description="Points users around the VEuPathDB sites",
        name="site_help",
        defer_model_check=True,
    )


__all__ = [
    "SITE_HELP_INSTRUCTIONS",
    "SITE_HELP_MODEL",
    "RecordTypeSummary",
    "SiteDetail",
    "SiteHelpAgent",
    "SiteSummary",
    "build_site_help_agent",
    "describe_site",
    "list_veupathdb_sites",
]
