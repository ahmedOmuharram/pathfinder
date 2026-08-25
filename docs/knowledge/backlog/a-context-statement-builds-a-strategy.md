---
type: Backlog Item
title: Stating what you are working on builds a whole strategy, unasked, for half a dollar
description: A bare context statement with no request ("I'm investigating virulence factors in Leishmania major") drove a full frame/build/verify: 26 tool calls, 231,891 tokens, $0.47, and a persisted WDK strategy on the user's real account, where the right answer was a two-sentence reply. Measured 2026-08-23 on tritrypdb with the default provider. The turn's own diagnosis flagged budget_burn. This is the general form of the already-filed remember-request-builds-a-strategy item: the Lead treats any domain-shaped sentence as a build order.
tags: [agents, lead, cost, ux]
generated: { by: claude-code/fable-5, at: 2026-08-23T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-23T00:00:00Z }
status: stable
---

**What I did.** One turn through `pathfinder.devtools.chat`, default provider,
site tritrypdb, real WDK login, no prior conversation:

    I'm investigating virulence factors in Leishmania major

**What I got.** A built and verified strategy. The reply opens "I built and
checked a Leishmania major (Friedlin) virulence-candidate strategy", reports
52 text-evidence transcripts UNION 37 GO-evidence transcripts = 87 unique, and
links `https://tritrypdb.org/tritrypdb/app/workspace/strategies/330545263/440150943`.
Run summary: `status=ok tokens=231891 cost=$0.471 toolcalls=26 failures=1
anomalies=1`, with the run's own diagnosis raising `budget_burn: Turn consumed
231891 tokens ($0.47) with status=ok - abnormally high`.

**Why that is wrong.** The user stated context, not a request. Three harms, in
order of severity: a strategy the researcher never asked for is now persisted
in their real VEuPathDB account, next to work they did ask for; the turn cost
$0.47 and 26 tool calls to answer a sentence that deserved a sentence; and the
assistant's first act in a conversation is to decide what the user wants, which
is the behavior the FRAME phase exists to prevent. At ten such openings a day
this is a hundred dollars a month of unasked-for strategies.

**Why it happens.** Nothing between the user's message and the Lead's tool
choice distinguishes "here is my context" from "build me this". The Lead's
instructions describe how to build; they do not describe when not to. The
already-filed `remember-request-builds-a-strategy.md` is the same defect with a
different prompt, so the cause is not that prompt's wording.

**Fix.** Two candidates, to be decided:
1. Intent gating before dispatch: a cheap classification (statement, question,
   build request, edit request, meta request) that routes anything but a build
   or edit request to a conversational reply, with the Lead free to offer
   "want me to build that?".
2. Instruction-level: the Lead is told, in one rule, that a turn with no
   imperative and no question about the data is answered in prose, and that
   building is a response to a request.
Option 1 is testable and cheap per turn; option 2 costs nothing but rides on
model compliance. Both need the eval case below to hold them.

**What you would get.** The measured turn answers in prose for a few hundred
tokens and offers to build; the researcher's account gains nothing they did not
ask for; and `question-turns-do-not-build` in the eval corpus goes from red to
green as the record of the fix.
