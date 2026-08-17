---
type: Backlog Item
title: "Please remember my preference" is classified clarification_response and runs frame, build and verify, creating a decoy WDK strategy and a junk strategy memory before the preference lands
description: A message stating an organism default and a preferred dataset was framed (124.7K tokens), built as a 3-step strategy (organism INTERSECT Su expression, 1,456), verified, and only then auto-written as two preference memories. A strategy memory whose summary is the user's sentence was written too. The remember tool exists for this and was not used.
tags: [investigation, ui-run, lead, intent, memory, cost]
generated: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# Investigation (UI run, 2026-08-17, PlasmoDB)

**What I did.** New conversation: "Please remember for future sessions: I always work with
P. falciparum 3D7 and I prefer the Su et al. strand-specific dataset for gametocyte
expression. Then tell me what you stored."

**What I got.** Intent `clarification_response`, goal "Store a durable organism default
and a preferred gametocyte-expression dataset, then report exactly what was stored".
Frame 124.7K tokens, `criteria 2, bound 2`; build "Built 3 steps"; Graph updated 3 steps,
1,456 genes; Verification "Verified successfully"; total 182.4K tokens, $0.03; a WDK
strategy 330534643 named after the preferences. Reply: "Stored for future sessions: ...
I also materialized these preferences in strategy 330534643 for validation." No
`remember` tool call in the transcript. `GET /api/v1/memories`: `preferences` has the two
correct entries ("User prefers Plasmodium falciparum 3D7 as the default organism...",
"User prefers the Su et al. strand-specific dataset...") and `strategies` gained
`strategy:2bd0351f...` with `summary` = the user's sentence and a spec whose criteria are
"Preferred future gametocyte expression evidence: ..." and "Default organism for future
work: ...".

**Why that is wrong.** A one-line preference costs a full pipeline run, leaves a
meaningless strategy in WDK and in the strategy panel, and pollutes the strategy memory
namespace with an entry that will be retrieved as if it were a past investigation. The
outcome was right only because the auto-writer runs on verification complete.

**Why it happens.** The intent classifier has no `memory` intent; the Lead's playbook for
`clarification_response` goes to frame; the `remember` tool is available but the model
was not steered to it. Auto-write on `complete` then persisted both the intended
preferences and the decoy strategy.

**Fix (to decide).** Add an intent (or a Lead rule) for preference/knowledge statements
that calls `remember` and answers, with no frame/build/verify; suppress the strategy
auto-write when the built strategy exists only to "validate" a preference (or simply
never build for that intent). Add a mock-model journey test: a "remember" message must
produce a `remember` call and no `data-graph-snapshot`.

**What you would get.** One `remember` call per preference, a two-line confirmation, no
strategy, about 10K tokens.
