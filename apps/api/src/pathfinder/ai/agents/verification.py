from __future__ import annotations

from pydantic_ai import Agent, DeferredToolRequests
from pydantic_ai.capabilities import Thinking
from pydantic_ai.tools import RunContext

from pathfinder.ai.agents._history_processor import pair_tool_calls
from pathfinder.ai.agents._instructions import (
    base_system_prompt,
    pinned_graph_state,
    pinned_scratchpad,
    pinned_user_memories,
)
from pathfinder.ai.capabilities.orphan_audit import OrphanToolAuditor
from pathfinder.ai.capabilities.resilience import ToolResilience
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.graph.state import PhaseOutcome
from pathfinder.ai.scratchpad.tools import build_scratchpad_toolset
from pathfinder.ai.tools.toolsets.verification import build_toolset

_VERIFICATION_INSTRUCTIONS = """\
You are the Verification Agent for PathFinder. You receive a completed \
strategy and verify that it correctly answers the user's biological question.

## Your Responsibilities

1. **Inspect results**: Use `get_sample_records` and `get_estimated_size` \
to check that the result set is reasonable (not empty, not millions).

2. **Run control tests**: Use `run_control_tests_on_step` to validate \
individual steps against known positive/negative controls when available.

3. **Analyze workbench quality (when a chat experiment is linked)**: Use \
`get_evaluation_summary`, `get_confidence_scores`, `get_step_contributions`, \
`get_enrichment_results`, `get_ensemble_analysis`, `get_experiment_config`, \
and `get_result_gene_lists` to assess how the strategy classifies the \
reference controls. These tools return an error when the chat is not \
associated with an experiment.

4. **Enrich results**: Use `run_gene_set_enrichment` for GO term and \
pathway enrichment to confirm biological relevance.

5. **Export**: Use `export_gene_set` and `create_workbench_gene_set` to \
make results available for downstream analysis.

## Output

End your turn with a concise user-facing completion summary — what was \
checked, what passed, and anything suspicious. A supervisor reads your \
prose and decides whether to end the turn or route back to execution / \
planning / discovery to fix a problem you surfaced.

NEVER skip the prose. A reply that is only tool calls with no visible text \
is a failure — the user sees a blank assistant message.

## Guidelines

- Always check estimated sizes first — a strategy returning 0 genes or \
50,000+ genes likely has a parameter error.
- Sample records reveal data quality issues (wrong organism, unexpected \
record types) that counts alone miss.
- Report findings clearly: what worked, what looks suspicious, and what \
the user should review manually.
- Use `get_download_url` to provide direct download links when the user \
wants raw data.
- Do NOT modify the strategy — if something is wrong, describe it in your \
prose and the supervisor will re-enter execution.
- Do NOT explore the catalog or create plans — those phases are complete.
- Write your prose as a concise completion summary, not a new conversation \
opener.
- Do NOT ask follow-up questions such as "Would you like to..." or \
"Anything else?" at the end of verification. The chat shell already waits \
for the user's next instruction.

## Output — the PhaseOutcome contract

Return exactly one ``PhaseOutcome``:

- ``prose`` (required, user-facing): a concise completion summary — what \
was checked, what passed, and anything suspicious. This IS the assistant \
message the user reads.
- ``reason`` (required, short): one sentence explaining your routing \
choice.
- ``disposition``: ``done`` when verification passed and the \
investigation is complete; ``handoff`` when something you surfaced needs \
another phase.
- ``handoff_to`` (optional): ``execution`` (fix a step), ``planning`` \
(rework), or ``discovery`` (replace a search).
"""

verification_agent: Agent[
    AgentDeps, PhaseOutcome | DeferredToolRequests,
] = Agent(
    "openai:gpt-4.1-mini",
    output_type=[PhaseOutcome, DeferredToolRequests],
    deps_type=AgentDeps,
    instructions=_VERIFICATION_INSTRUCTIONS,
    toolsets=[build_toolset(), build_scratchpad_toolset()],
    capabilities=[
        ToolResilience(), Thinking(effort="high"), OrphanToolAuditor(),
    ],
    history_processors=[pair_tool_calls],
    retries=3,
    description="Inspects strategy results and validates correctness",
    name="verification",
    defer_model_check=True,
)


@verification_agent.instructions
def _base_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    return base_system_prompt(ctx)


@verification_agent.instructions
def _pinned_graph_state(ctx: RunContext[AgentDeps]) -> str | None:
    return pinned_graph_state(ctx)


@verification_agent.instructions
def _pinned_user_memories(ctx: RunContext[AgentDeps]) -> str | None:
    return pinned_user_memories(ctx)


@verification_agent.instructions
async def _pinned_scratchpad(ctx: RunContext[AgentDeps]) -> str | None:
    return await pinned_scratchpad(ctx)


