---
type: Decision
title: Prompts are checked against the architecture
description: The base prompt kept describing scoping/discovery/planning and three output schemas that no longer exist, so the model was being told to return types it could not return.
tags: [agents, prompts, drift]
generated: { by: claude-code/opus-5, at: 2026-08-09T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-09T00:00:00Z }
status: stable
---

# What was wrong

FRAME/BUILD/VERIFY replaced the five-phase pipeline in code. `system.md` did not follow. It told every agent:

- that the Lead dispatches "(scoping, discovery, planning, execution-recovery, verification)" - three of which no longer exist;
- that output schemas include `FrameDelta`, `DiscoveryDelta` and `PlanDelta` - **none of which exist**; the real ones are `FrameResult`, `ExecuteDelta`, `RecoveryDelta`, `VerificationDelta`;
- that `submit_plan_for_approval` suspends the run - a tool that was deleted.

This is not a documentation problem. A prompt is the model's only description of its own architecture, so this instructed the model to return a type it cannot return and to expect dispatches that cannot happen. The devtool README had the same rot, documenting `create_plan` and `submit_plan`.

# The guard

`tests/unit/ai/prompts/test_prompts_match_the_architecture.py` fails when prose and code drift:

- every `*Delta` / `*Result` named in any prompt must exist in `ai/lead/deltas.py`;
- no prompt may name a retired sub-agent **as a role**.

The second test was deliberately narrowed. Matching the bare words flagged "**Search Discovery**: Find available searches" in `workbench.md`, which is a correct capability label. A test that forces correct prose to change is a bad test, so it now matches role references ("the discovery agent", "the planning phase", a name inside a sub-agent list) and leaves ordinary English alone. Verified by injecting a retired role and watching it fail.

# Anchor

`ai/prompts/*.md` against `ai/lead/deltas.py` and `SubAgentName` in `ai/lead/ledger.py`.
