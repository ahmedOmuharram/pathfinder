---
type: Backlog Item
title: The persisted strategy AST is parsed into a PersistedStrategyGraph in two places, byte for byte
description: "`assistants/pathfinder_spec.py::_persisted_graph` and `jobs/runtime.py::build_worker_runtime_context` each hold the same eleven-line guard-parse-fallback over `conversation_strategies.strategy_ast`. Chat turns run through the second copy, so a change to the first is not deployed."
tags: [architecture, duplication, strategy]
generated: { by: claude-code/opus-5, at: 2026-08-27T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-27T00:00:00Z }
status: stable
---

# What I did

Read every caller of `build_strategy_session`
(`apps/api/src/pathfinder/services/strategies/session_factory.py:40`) while
wiring the pre-turn spec hydration, because the hydration reads whatever that
factory produced.

# What I got

Two production callers, holding the same logic:

`apps/api/src/pathfinder/assistants/pathfinder_spec.py:74-89`

    plan_payload: StrategyAst | None = None
    if strategy.strategy_ast and "root" in strategy.strategy_ast:
        try:
            plan_payload = StrategyAst.model_validate(strategy.strategy_ast)
        except ValueError, KeyError, TypeError:
            plan_payload = None
    return PersistedStrategyGraph(id=..., name=..., strategy_ast=plan_payload, ...)

`apps/api/src/pathfinder/jobs/runtime.py:33-49`

    plan_payload: StrategyAst | None = None
    raw_ast = strategy.strategy_ast
    if raw_ast and "root" in raw_ast:
        try:
            plan_payload = StrategyAst.model_validate(raw_ast)
        except ValueError, KeyError, TypeError:
            plan_payload = None
    strategy_session = build_strategy_session(site_id=..., strategy_graph=PersistedStrategyGraph(...))

The only differences are a local variable name and where the
`PersistedStrategyGraph` is constructed.

# Why that is wrong

Chat turns run in the WORKER, so `jobs/runtime.py` is the copy that decides
what every agent sees. A fix applied to the assistant-spec copy alone changes
nothing a user experiences, and the two can drift without any gate noticing:
no test asserts they agree. The swallowed-exception fallback makes the drift
silent by construction - a strategy that parses in one path and not the other
produces an empty session rather than an error.

# Why it happens

`build_strategy_session` takes a `PersistedStrategyGraph`, not the row, so
every caller has to do the row-to-model parse itself. The parse belongs to the
boundary, and the boundary has no single owner.

# Fix

Give `PersistedStrategyGraph` the parse. A `@model_validator(mode="before")`
on `strategy_ast`, or a classmethod on the session factory that takes the
`ConversationStrategyView` and the `Conversation`, removes both copies. Then
`assistants/pathfinder_spec.py` and `jobs/runtime.py` each call one function.

# What you would get

One place to read to know what a turn's strategy session holds, and a change
to the parse that reaches the worker by construction rather than by a second
edit somebody has to remember.
