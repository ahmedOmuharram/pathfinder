"""Live-LLM, live-WDK per-phase tests.

Run with:
    scripts/llm-tests.sh                    # all phases
    scripts/llm-tests.sh -k planning        # filter

Requires OPENAI_API_KEY in the environment. Hits plasmodb.org. Each test
is opt-in; the default pytest sweep ignores this directory.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pydantic_ai.models
import pytest

from pathfinder.ai.agents.state import AgentToolState, SearchOverview
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.graph.state import (
    ClarificationQuestion,
    ProblemFrame,
    ResearchNote,
)
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.literature_search import (
    LiteratureSearchService,
)
from pathfinder.services.research.web_search import WebSearchService

pydantic_ai.models.ALLOW_MODEL_REQUESTS = True


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    del config
    marker = pytest.mark.llm
    for item in items:
        item.add_marker(marker)


@pytest.fixture(scope="session", autouse=True)
def _skip_if_no_openai_key() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip(
            "OPENAI_API_KEY not set — llm tests require a live OpenAI key",
            allow_module_level=True,
        )


@pytest.fixture
def plasmodb_site() -> str:
    return "plasmodb"


@pytest.fixture
def strategy_session(plasmodb_site: str) -> StrategySession:
    return StrategySession(site_id=plasmodb_site)


def _make_kinase_problem_frame() -> ProblemFrame:
    return ProblemFrame(
        user_goal=(
            "Find Plasmodium kinase genes that are membrane-associated and "
            "have EST expression evidence."
        ),
        interpreted_goal=(
            "Identify genes annotated with GO term kinase activity "
            "(GO:0016301) across all Plasmodium organisms, filter to those "
            "with a predicted transmembrane domain OR signal peptide, and "
            "require EST overlap evidence with >=90% identity and >=100bp."
        ),
        organism_scope="Plasmodium (all species)",
        record_type="transcript",
        biological_entities=["kinase", "membrane protein"],
        inclusion_criteria=[
            "GO:0016301 kinase activity annotation",
            "Transmembrane domain OR signal peptide",
            "EST overlap >=90% identity AND >=100bp",
        ],
        exclusion_criteria=[],
        likely_data_sources=[
            "GenesByGoTerm",
            "GenesByTransmembraneDomains",
            "GenesWithSignalPeptide",
            "GenesByESTOverlap",
        ],
        success_criteria=["non-empty intersection; consistent counts"],
        assumptions=[
            "Curated and Computed evidence both count for GO kinase",
        ],
        blocking_questions=[],
        optional_questions=[],
        research_notes=[
            ResearchNote(
                source="prompt",
                finding="Researcher wants transmembrane OR signal peptide.",
            ),
        ],
        ready_for_wdk_discovery=True,
        confidence=0.85,
    )


@pytest.fixture
def kinase_problem_frame() -> ProblemFrame:
    return _make_kinase_problem_frame()


def _search_overview(
    name: str,
    required: list[str],
    all_params: list[str],
) -> SearchOverview:
    return SearchOverview(
        search_name=name,
        display_name=name,
        record_type="transcript",
        description=f"Live WDK search: {name}",
        parameter_names=all_params,
        required_params=required,
    )


@pytest.fixture
def kinase_discovered_searches() -> dict[str, SearchOverview]:
    """Four real-shape WDK searches pre-registered as discovered.

    Values match plasmodb.org/plasmo/service/record-types/transcript/searches
    as of 2026-04. Param names are the exact WDK identifiers so create_plan's
    _fetch_specs_by_search call can resolve them.
    """
    return {
        "GenesByGoTerm": _search_overview(
            "GenesByGoTerm",
            required=["organism", "go_term_evidence", "go_term"],
            all_params=[
                "organism",
                "go_term_evidence",
                "go_term_slim",
                "go_term",
                "go_typeahead",
            ],
        ),
        "GenesByTransmembraneDomains": _search_overview(
            "GenesByTransmembraneDomains",
            required=["organism", "min_tm", "max_tm"],
            all_params=["organism", "min_tm", "max_tm"],
        ),
        "GenesWithSignalPeptide": _search_overview(
            "GenesWithSignalPeptide",
            required=["organism"],
            all_params=["organism"],
        ),
        "GenesByESTOverlap": _search_overview(
            "GenesByESTOverlap",
            required=[
                "libraryIdGenes",
                "bp_overlap_gte",
                "min_percent_identity",
            ],
            all_params=[
                "libraryIdGenes",
                "bp_overlap_gte",
                "best_alignment_only",
                "max_number_best_alignments",
                "high_confidence_only",
                "min_percent_identity",
            ],
        ),
    }


def _build_deps(
    *,
    site_id: str,
    problem_frame: ProblemFrame | None = None,
    discovered: dict[str, SearchOverview] | None = None,
) -> AgentDeps:
    state = AgentToolState(
        discovered_searches=dict(discovered or {}),
    )
    return AgentDeps(
        site_id=site_id,
        user_id=uuid4(),
        conversation_id=uuid4(),
        strategy_session=StrategySession(site_id=site_id),
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        agent_state=state,
        problem_frame=problem_frame,
    )


@pytest.fixture
def deps_scoping(plasmodb_site: str) -> AgentDeps:
    return _build_deps(site_id=plasmodb_site)


@pytest.fixture
def deps_discovery(
    plasmodb_site: str,
    kinase_problem_frame: ProblemFrame,
) -> AgentDeps:
    return _build_deps(
        site_id=plasmodb_site,
        problem_frame=kinase_problem_frame,
    )


@pytest.fixture
def deps_planning(
    plasmodb_site: str,
    kinase_problem_frame: ProblemFrame,
    kinase_discovered_searches: dict[str, SearchOverview],
) -> AgentDeps:
    return _build_deps(
        site_id=plasmodb_site,
        problem_frame=kinase_problem_frame,
        discovered=kinase_discovered_searches,
    )


def _ambiguous_frame() -> ProblemFrame:
    return ProblemFrame(
        user_goal="find kinase genes",
        interpreted_goal="",
        organism_scope=None,
        record_type=None,
        biological_entities=["kinase"],
        ready_for_wdk_discovery=False,
        confidence=0.2,
        blocking_questions=[
            ClarificationQuestion(
                question="Which organism should we query?",
                priority="blocking",
            ),
        ],
    )


@pytest.fixture
def ambiguous_problem_frame() -> ProblemFrame:
    return _ambiguous_frame()
