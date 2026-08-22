---
type: Decision
title: The Lead agent belongs to the turn that runs it
description: The module-level Lead agent became a factory the graph is built with, so each turn constructs its own instance and a per-request model override cannot reach another turn; caching one instance behind the factory was rejected because the override is process-wide state.
tags: [assistant-core, ws2, agents, concurrency]
generated: { by: claude-code/opus-5, at: 2026-08-21T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-21T00:00:00Z }
status: stable
---

# What was found

`lead_agent` was built at import with a hard-coded model id and 14 tools, and
the turn node used it directly. A second assistant could not supply its own
agent, and the per-request model pick was applied with `agent.override(...)`
on that one shared object.

Constructing the agent costs about 50 ms, which is why caching one instance
behind the factory looks attractive.

# The decision

`build_lead_agent()` is a factory, the graph builder takes it as
`build_agent`, and the turn node calls it once per turn. `ai/graph/composition.py`
is the single place that names PathFinder's factory and its pre-turn hook, so
the five processes that build a graph cannot drift apart.

A cached instance was rejected. The model override is not a per-call argument;
it is state entered on the agent for the duration of the run. One shared
instance means two turns that pick different models race for it, and the
deployment is about to raise worker concurrency above one. Fifty milliseconds
against a turn that calls an LLM is not a cost worth that.

The factory also removed a branch: with a fresh agent, `agent.model` is always
the id the factory baked in, so the check for an already-installed
`FunctionModel` could never fire and is gone.

# Anchor

`apps/api/src/pathfinder/ai/lead/lead_agent.py` holds the factory,
`ai/graph/composition.py` the wiring. Done if a module-level `Agent` is
reintroduced, or if a second `build_graph` caller supplies its own hooks.
