"""Verification-phase agent — inspects, tests, and exports results.

This agent runs after execution completes. It inspects the built strategy,
runs control tests, performs enrichment analysis, and exports gene sets
for downstream use.
"""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.capabilities import Thinking
from pydantic_ai.tools import RunContext
from pydantic_ai.usage import UsageLimits

from pathfinder.ai.agents._instructions import (
    base_system_prompt,
    mentioned_context,
    pinned_context_summary,
    pinned_graph_state,
)
from pathfinder.ai.capabilities.security import SecurityGuardrail
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.tools.toolsets.verification import build_toolset

# ---------------------------------------------------------------------------
# Static instructions
# ---------------------------------------------------------------------------

_VERIFICATION_INSTRUCTIONS = """\
You are the Verification Agent for PathFinder. You receive a completed \
strategy and verify that it correctly answers the user's biological question.

## Your Responsibilities

1. **Inspect results**: Use `get_sample_records` and `get_estimated_size` \
to check that the result set is reasonable (not empty, not millions).

2. **Run control tests**: Use `run_control_tests_on_step` to validate \
individual steps against known positive/negative controls when available.

3. **Analyze quality**: Use `get_evaluation_summary`, `get_confidence_scores`, \
and `get_step_contributions` to assess how well each step contributes to \
the final result.

4. **Enrich results**: Use `run_gene_set_enrichment` for GO term and \
pathway enrichment to confirm biological relevance.

5. **Export**: Use `export_gene_set` and `create_workbench_gene_set` to \
make results available for downstream analysis.

## Guidelines

- Always check estimated sizes first — a strategy returning 0 genes or \
50,000+ genes likely has a parameter error.
- Sample records reveal data quality issues (wrong organism, unexpected \
record types) that counts alone miss.
- Report findings clearly: what worked, what looks suspicious, and what \
the user should review manually.
- Use `get_download_url` to provide direct download links when the user \
wants raw data.
- Do NOT modify the strategy — if something is wrong, report it so the \
orchestrator can re-enter the execution phase.
- Do NOT explore the catalog or create plans — those phases are complete.
"""

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

verification_agent: Agent[AgentDeps, str] = Agent(
    "anthropic:claude-sonnet-4-5",
    deps_type=AgentDeps,
    instructions=_VERIFICATION_INSTRUCTIONS,
    toolsets=[build_toolset()],
    capabilities=[Thinking(effort="high"), SecurityGuardrail()],
    description="Inspects strategy results and validates correctness",
    name="verification",
    defer_model_check=True,
)


@verification_agent.instructions
def _base_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    return base_system_prompt(ctx)


@verification_agent.instructions
def _pinned_context_summary(ctx: RunContext[AgentDeps]) -> str | None:
    return pinned_context_summary(ctx)


@verification_agent.instructions
def _pinned_graph_state(ctx: RunContext[AgentDeps]) -> str | None:
    return pinned_graph_state(ctx)


@verification_agent.instructions
def _mentioned_context(ctx: RunContext[AgentDeps]) -> str | None:
    return mentioned_context(ctx)


# ---------------------------------------------------------------------------
# Default usage limits
# ---------------------------------------------------------------------------

VERIFICATION_USAGE_LIMITS = UsageLimits(
    request_limit=15,
    total_tokens_limit=40_000,
)
