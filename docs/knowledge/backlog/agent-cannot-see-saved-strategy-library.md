---
type: Backlog Item
title: The agent cannot find a saved strategy by name or by WDK id, and when the input is unresolved it builds the remaining criterion alone
description: "Start from my saved strategy 'X' and keep only genes with a signal peptide" produced a 187K-token frame that asked for a WDK strategy id; given the id, the next turn framed one criterion (GenesWithSignalPeptide), built a 1-step strategy (603) and reported that the saved strategy "could not be found". The saved-strategy library (Conversation rows with isSaved=true) has no agent-facing lookup, and an empty conversation has no UI entry point to insert one either.
tags: [investigation, ui-run, saved-strategies, lead, frame, tools]
generated: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# Investigation (UI run, 2026-08-17, PlasmoDB)

**What I did.** Saved the Union step of a strategy as "Pf protease union (text OR GO)"
(3 steps, WDK strategy 330534203; the row is `GET /api/v1/conversations?siteId=plasmodb`
with `isSaved: true`, `id 9bd3a584...`). Opened a new conversation and sent:
"Start from my saved strategy "Pf protease union (text OR GO)" and keep only the genes
that also have a predicted signal peptide." Then answered the follow-up with
"The WDK strategy ID is 330534203."

**What I got.** Turn 1: Frame 187.1K tokens, "1 open question"; reply: "I couldn't
resolve 'Pf protease union (text OR GO)' as an available input strategy from its name
alone. The catalog requires either the saved strategy's WDK strategy ID, or an imported
PlasmoDB Gene List Dataset". Turn 2 (`clarification_response`): ledger FRAME `criteria 1,
bound 1, ready to build yes`, structure `GenesWithSignalPeptide`; build "Built 1 step",
603; verification "Issues found"; reply: "that saved strategy could not be found. The
active strategy that was built is instead 330534273 ... Result: 603 genes/transcripts ...
Please verify that the ID is correct". Also: the empty Strategy panel has no
"insert saved strategy" action (only a step's kebab offers "Insert saved here"), and the
Saved strategies page has no "use in a new chat" action.

**Why that is wrong.** The user built a reusable component exactly as the product invites
("Other conversations can insert it without re-running the searches") and cannot use it
from chat at all. Worse, the pipeline built and pushed a strategy that is not what was
asked (the filter alone) and left it as the conversation's active strategy.

**Why it happens.** No Lead or FRAME tool lists or resolves saved strategies (by name or
WDK id); the frame's open question is answered with an id nobody can consume, so the
criterion is dropped and `ready_to_build` flips to yes with the one criterion left. The
insert-saved operation exists only as an HTTP route used by the panel's kebab
(`transport/http/routers/conversations/insert_saved.py`).

**Fix (to decide).** Give the frame a `list_saved_strategies(site)` lookup and let a
criterion bind to a saved strategy as an input step (the same operation the kebab uses);
a frame whose input criterion is unresolved must stay `needs user`, not build without it.
UI: an "Insert saved strategy" action on the empty panel and a "Use in new chat" action on
the Saved strategies page.

**What you would get.** A 2-step strategy: saved union (227) INTERSECT signal peptide,
with the union inserted as a collapsed input, and no 603-gene decoy.
