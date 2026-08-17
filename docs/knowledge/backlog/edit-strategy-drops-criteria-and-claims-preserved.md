---
type: Backlog Item
title: An edit_strategy turn re-frames from the message alone, drops a criterion the user asked to keep, and the reply says "the rest preserved"
description: A "change X, keep the rest" turn is classified edit_strategy with a goal that says "preserving all other strategy criteria", but the FRAME sub-agent produced two criteria where the prior strategy had three, silently dropping the GO:0006508 branch. The final reply then asserted the rest was preserved.
tags: [investigation, ui-run, lead, frame, edit-strategy, honesty]
generated: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# Investigation (UI run, 2026-08-17, PlasmoDB, conversation 4f69357c)

**What I did.** Turn 1 (moderate prompt) framed three criteria: GenesByText `*protease*`,
GenesByGoTerm `GO:0006508` (Curated+Computed), and a gametocyte percentile filter; the plan
was (Text UNION GO) INTERSECT Expression, 5 steps. Turn 2:
"Wait, for the gametocyte expression use the Su et al. strand-specific 4 life cycle stages
dataset instead, top 20% in Gametocyte II or V. Keep the rest."

**What I got.** Intent: `edit_strategy`, goal "Revise the gametocyte-expression criterion
... while preserving all other strategy criteria." Ledger FRAME: `criteria 2, bound 2`,
structure `(GenesByText INTERSECT GenesByRNASeqpfal3D7_Su_...)`. Build: 3 steps, 15
transcripts (2,122 INTERSECT 1,456). Final reply: "Updated and rebuilt the strategy with the
rest preserved. ... Preserved criterion: Plasmodium genes with protease/proteolysis
annotations." The GO:0006508 criterion and the UNION are gone.

**Second measurement, same conversation.** Later turn: "Instead of a transform, put the
protease criterion back to text OR GO:0006508 like the very first version, and keep the Su
et al. filter." The frame restored the UNION but also narrowed both protease branches from
`Plasmodium` to `P. falciparum 3D7` (text 2,122 -> 45) and changed the Su filter's
`any_or_all` from any to all (1,456 -> 700); reply: "Su et al. filter retained ... 700
genes". Nothing the user said asked for either change.

**Why that is wrong.** The user asked for one substitution and got a different strategy
(a narrower one) with a reply that says nothing changed elsewhere. A researcher who trusts
the reply now has a result set built on one line of evidence where they asked for two, and
the count they will cite (15) is not the count of the strategy they described.

**Why it happens.** The FRAME sub-agent for an edit turn re-derives criteria from the new
message plus the intent goal; the prior frame's criteria are not carried in as the starting
point that must be preserved, so "keep the rest" is honoured only as far as the model
remembers to restate the old criteria. The verification phase compares the build against
the new frame, not against the prior strategy, so the dropped branch is invisible to it, and
the reply is generated from the new frame's summary.

**Fix (to decide).** For `edit_strategy`, seed the frame with the previous turn's bound
criteria and structure, and require the frame to state each prior criterion as kept,
changed, or dropped (with a reason) before build; make verification diff the new plan
against the previous plan and surface any dropped criterion in the ledger and the reply.
A reply that says "preserved" must be generated from that diff, not from prose.

**What you would get.** Turn 2 would produce (Text UNION GO) INTERSECT Su-expression, 5
steps, and the reply would list the one criterion changed and the two kept.
