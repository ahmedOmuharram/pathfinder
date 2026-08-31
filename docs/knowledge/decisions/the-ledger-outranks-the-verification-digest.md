---
type: Decision
title: The ledger outranks the verification digest, and the contradiction is corrected where the digest is recorded
description: run_verification refuses a success digest the ledger's build section does not support and rewrites it into a failure digest naming the contradiction. A ModelRetry on the verification sub-agent was rejected, because retries are finite and the flag also decides the memory auto-write and the eval verdict.
tags: [verification, ledger, trust, agents]
generated: { by: claude-code/opus-5, at: 2026-08-30T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-30T00:00:00Z }
status: stable
---

# What was decided

`ai/lead/ledger.py::build_contradiction` states, in one place, why a success
verdict cannot stand over a build: the build ran and did not come out clean
(a step failed, was skipped, or returned nothing), or no build ran this turn
and no step of the strategy is in VEuPathDB. `digest_held_to_the_build`
rewrites the digest when it does: `success` becomes False, `reason` and
`prose` name the contradiction, and the original prose is kept below it so
nothing the checker found is lost.

`ai/lead/sub_agent_dispatch.py::run_verification` applies both before it
writes `state.domain.verification_digest`. That is the single write point, so
the three readers of the flag - the delta the Lead quotes, the memory
auto-write in `ai/graph/nodes.py`, and the eval extractor's verdict in
`services/eval_data/chunk_reader.py` - all read the corrected digest.

The rule reads the ledger and the live session only. The digest may add
detail to what the build recorded; it may never overrule it.

# What was rejected

**A `ModelRetry` from the verification tool.** Handing the contradiction back
to the sub-agent and asking it to try again is the more conversational fix,
and it lets the model explain itself. It was rejected because it does not
make the contradiction impossible: retries are finite, and a model that
misread its input once will usually misread it again, after which the wrong
flag lands anyway. It also spends a second sub-agent run to reach a verdict
the ledger already holds.

**Correcting each reader.** The reply, the auto-write and the eval extractor
could each check the build themselves. That puts one rule in three places and
guarantees that the next reader of the flag forgets it.

**Deriving the whole verdict from the ledger and dropping `success`.** The
digest carries findings a ledger cannot: sample records, control tests,
constraint reports. Removing the flag would lose them. The flag is kept and
bounded instead.

# The consequence, stated

One screen can no longer say "build - failed" and "Verified end-to-end." at
the same time. A verification that claims more than the build supports is
reported as the build failure it is, and nothing is remembered from it.
