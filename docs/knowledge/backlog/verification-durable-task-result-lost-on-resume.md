---
type: Backlog Item
title: Verification on a simple edit turn launches an unrequested enrichment task; when the graph resumes, its result and the verification verdict never reach the reply, the ledger, or the transcript
description: On "add a P. vivax ortholog transform", the verify sub-agent started a durable geneset_enrichment task (~2 min estimate, 22 s actual). The turn suspended, resumed after completion, and the Lead re-classified intent and answered from live state only. The transcript's Verification card stays "started", the ledger's Verification tab still shows the previous turn's verdict, and the task card says only "Task completed".
tags: [investigation, ui-run, verification, durable-tasks, resume, ledger]
generated: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# Investigation (UI run, 2026-08-17, PlasmoDB, conversation 4f69357c)

**What I did.** Sent "Now add a step at the end that transforms the result into P. vivax
P01 orthologs." on a 3-step strategy and watched the turn.

**What I got.** Transcript: Classify intent, Get live strategy state, Frame completed,
build completed (4 steps, 16 genes), "Verification - started 20.2K $0.0032", then
"Background task started / Geneset enrichment - ~2 min / Task completed", then a second
"Classify intent", "Get live strategy state", "Final result". Reply: transform details and
"returns an estimated 16 P. vivax P01 orthologs" - no verification statement, no enrichment
output. `GET /api/v1/conversations/<id>/tasks`:
`toolName geneset_enrichment, status complete, createdAt 14:24:41, completedAt 14:25:03,
latestMessage "Enrichment complete"`. Ledger Verification tab: still turn 2's text
("Verification passed for the rebuilt intersection ... 15 retained result records").
Tasks panel: "Geneset enrichment COMPLETE" with no detail on click.

**Second measurement (VectorBase, conversation af4b6648, vague hemocyte prompt).** Turn 1
built 5 steps / 18 genes; verification started `geneset_enrichment` (created 15:04:32,
completed 15:08:02, 3.5 min). Event stream after the task: a second `start` with the
*same* messageId `709c01ad`, then "Framing the strategy...", a new `data-graph-snapshot`
with all-new step ids (the tree changed from (hemocyte AND immune) AND signal to hemocyte
AND (signal AND immune)), "Verifying...", finish. Cost of the resumed frame: 136.8K tokens.
The open tab rendered none of it (turn 1's card stayed at "Running enrichment 20%" while a
later turn answered) until a reload, after which the whole resumed sequence and a good
final answer (18 named candidates) appeared. The enrichment table itself never appears.

**Why that is wrong.** The user paid for a verification and an enrichment they did not
ask for and got neither: no verdict for the 4-step strategy, no enrichment table, no link.
The transcript says verification is still running. The ledger lies about which strategy its
verdict describes.

**Why it happens.** Three things. The verify sub-agent's playbook reaches for enrichment on
an edit turn where a count check would do. And the resume path after a durable interrupt
restarts the Lead loop (a fresh "Classify intent") instead of returning the task result to
the suspended verify call, so the verify sub-agent never finishes and never writes its
section; the resumed Lead loop re-frames and rebuilds the strategy from scratch (new WDK
steps, sometimes a different tree). And the client does not subscribe to resumed-graph
chunks for the open conversation, so nothing renders until reload.

**Fix (to decide).** Resume must deliver `{result, status}` into the suspended tool call
and let verification complete and write the ledger; the transcript's phase card must
resolve; the task card must show or link the result. Separately, gate enrichment behind an
explicit ask or a verification playbook that only runs it for a new build with a control
set, not for a one-step edit.

**What you would get.** A verification verdict for the 4-step strategy in the ledger and
the reply, and an enrichment result (or none, if it was not needed).
