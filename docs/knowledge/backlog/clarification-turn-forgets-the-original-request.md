---
type: Backlog Item
title: A clarification_response turn frames from the answer alone, forgets the original request's organism, motif and evidence, and asks the user for what they already gave
description: Turn 1 (VectorBase) asked for A. gambiae midgut proteases (text and GO), midgut RNA-Seq, ortholog transform, and colocation with [TG].{5,6}YGCACACAN[TCA]H; it ran out of frame budget and asked two definitional questions. Turn 2 answered them. The turn-2 frame (296.9K tokens) bound Aedes aegypti orthology and A. aegypti protease annotation, dropped RNA-Seq and GO, and replied "the 'within 1 kb upstream of the motif' criterion still lacks the motif itself ... Please provide the exact motif sequence".
tags: [investigation, ui-run, lead, frame, clarification, context, cost]
generated: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# Investigation (UI run, 2026-08-17, VectorBase, conversation 762c33a2)

**What I did.** Turn 1: "Find A. gambiae midgut protease genes conserved across mosquito
species that are near a known regulatory DNA motif. Use text and GO evidence for protease
identification, filter by midgut RNA-Seq expression, transform to A. gambiae orthologs,
then check for proximity to the motif [TG].{5,6}YGCACACAN[TCA]H on the genome." Reply
(after the frame budget ran out): asked how to define "conserved" and "near". Turn 2:
"Conserved = has an ortholog in at least two other mosquito species. Near = within 1 kb
upstream of the motif. Go ahead."

**What I got.** Intent `clarification_response`, goal "Confirm the conservation and
motif-proximity definitions, then proceed with the previously requested mosquito protease
strategy." Ledger CONSTRAINTS: only "Motif proximity criterion - grounded - requested
within 1 kb upstream of the motif" (turn 1 had listed target organism A. gambiae, the
motif string, RNA-Seq, record type genome, all provisional). Frame: 296.9K tokens,
`criteria 2, bound 2, ready to build yes`. Reply: "operationalized as Aedes aegypti genes
with orthologs in at least two other mosquito species ... using Aedes albopictus and
Anopheles gambiae, and intersected it with the A. aegypti protease/peptidase annotation
search. I cannot yet build the complete strategy because the 'within 1 kb upstream of the
motif' criterion still lacks the motif itself ... Please provide either the exact motif
sequence ... or a recognized motif identifier."

**Why that is wrong.** The user is asked to repeat information they gave one message ago,
the organism has silently changed to a different genus, and two of the five requested
lines of evidence are gone. At $0.09 for that frame alone.

**Why it happens.** The frame for a clarification turn is seeded from the new message and
the one-line intent goal; the prior turn's constraints and the original prompt's literal
values (organism, motif regex, dataset kind) are not carried into the frame's context, and
the intent classifier's constraint list is rebuilt per turn rather than accumulated. Same
root as [edit turns dropping criteria](edit-strategy-drops-criteria-and-claims-preserved.md):
the frame does not start from the conversation's standing requirements.

**Fix (to decide).** Keep a per-conversation requirement ledger (organism, named
datasets, literal motifs/ids, evidence kinds) that every frame receives verbatim and must
account for (kept / changed / dropped with reason); a clarification turn adds to it and
never replaces it. Refuse to ask the user for a value already present in it.

**What you would get.** Turn 2 frames A. gambiae PEST proteases (text OR GO), midgut
RNA-Seq filter, ortholog conservation as defined, colocation within 1 kb upstream of
`[TG].{5,6}YGCACACAN[TCA]H`, and builds.
