---
type: Backlog Item
title: The tool-repetition guard is registered on no agent, so it never blocks a loop
description: repetition_guard_hook is defined and documented but never passed to any agent, and nothing else calls ToolRepetitionGuard.check, so the anti-thrash circuit breaker is inert in every phase.
tags: [agents, capabilities, dead-code, assistant-core]
generated: { by: claude-code/opus-5, at: 2026-08-21T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-21T00:00:00Z }
status: stable
---

# What was found

`assistant_core/capabilities/repetition_guard.py` defines `ToolRepetitionGuard.check`, which
blocks the third consecutive identical read-only tool call, and
`repetition_guard_hook`, which is meant to run it. The hook's own docstring says
it is "registered via `Hooks(tool_execute=repetition_guard_hook)` on agents whose
toolsets contain read-only inspectors".

No agent registers it. `Hooks(` appears nowhere in `src/pathfinder`, the hook is
referenced only by its own definition, and no other caller invokes
`ToolRepetitionGuard.check`. The guard instance on `AgentDeps.tool_repetition_guard`
is constructed every turn and read by nothing, so `total_blocked` is always 0 and a
read-only loop burns its tokens until `request_limit` catches it.

Batch C made the guard's tool-name sets constructor arguments
(`ai/agents/tool_vocabulary.py` supplies PathFinder's). That inversion is correct
and tested, but it currently parameterizes a mechanism that does not run.

# What to decide

Either re-wire it or delete it. Both are one change:

- **Re-wire**: pass `Hooks(tool_execute=repetition_guard_hook)` to the FRAME,
  execution and verification agents, then prove it with a test that runs one agent
  through three identical `get_strategy` calls and asserts the third returns the
  warning string rather than the tool result. The read-only set in
  `tool_vocabulary.py` must first be checked against the tools those agents
  actually carry today; several names in it (`get_plan`, `search_catalog`) predate
  the FRAME/BUILD/VERIFY split.
- **Delete**: remove the hook, the class, `AssistantDeps.tool_repetition_guard`,
  `build_tool_repetition_guard`, the two tool-name sets and their tests. The
  circuit breaker in `ToolResilience.prepare_tools` and the per-phase
  `UsageLimits` remain as the loop defences.

Deleting is smaller; re-wiring is what the docstring and the phase budgets assume.
The choice belongs to whoever owns the phase budgets, which is why Batch C left it.

# Anchor

`apps/api/src/pathfinder/assistant_core/capabilities/repetition_guard.py` defines it;
`apps/api/src/pathfinder/ai/agents/{frame,execution,verification}.py` are where a
registration would go. Done when either a test proves the guard blocks a real
agent's third call, or the module is gone.
