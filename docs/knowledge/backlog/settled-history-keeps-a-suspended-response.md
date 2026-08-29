---
type: Backlog Item
title: settled_history keeps a no-tool-call ModelResponse in state suspended, which the next prompt trips over
description: The batch review of the thread-memory fix (2026-08-27) found the trim in assistant_core/graph/thread_history.py pops trailing messages until the last is a ModelResponse without tool calls, but a response carrying state suspended and no tool calls survives, and pydantic-ai raises UserError at _agent_graph.py:576-579 when a new prompt lands on it. Unreachable with the providers this repo runs today, so nothing fails now. Fix: one guard in settled_history treating a suspended response as unsettled, plus a pinned test with a synthetic suspended message.
tags: [assistant-core, runtime, history]
generated: { by: claude-code/fable-5, at: 2026-08-27T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-27T00:00:00Z }
status: stable
---

**What I did.** The pair review read settled_history against pydantic-ai's
refusal conditions in the installed venv.

**What I got.** The trim keys on tool calls only; _agent_graph.py:576-579
also refuses a history ending in a response whose state is suspended.

**Why that is wrong.** If a provider pause mode ever reaches a one-agent
assistant, its next turn dies with a UserError instead of answering.

**Why it happens.** The trim mirrors one of the library's two refusal
conditions.

**Fix.** Treat a suspended trailing response as unsettled in the trim; pin
with a synthetic suspended message.

**What you would get.** A trim that mirrors the whole refusal condition.
