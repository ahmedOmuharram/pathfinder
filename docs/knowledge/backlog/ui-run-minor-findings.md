---
type: Backlog Item
title: Small UI defects seen during the 2026-08-17 UI run, each with the step that shows it
description: Status labels that lag or contradict the transcript, badges with no meaning, nameless action buttons, a chat column that collapses at 866px, workbench results that do not restore, a compose panel that promises a Venn diagram and draws none, and a polling loop on the workbench. None blocks a workflow; each misleads for a moment.
tags: [investigation, ui-run, ux, polish]
generated: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

Each line: what to do, what shows, why it is wrong. Fix any subset; delete the line when
done and this file when empty.

- **Footer status lags the transcript.** Send any prompt; when the `build` card appears
  the footer still says "Framing the strategy..." until build ends. Same for
  "Verifying...". The label is driven by `data-turn-status`, which the phases emit late.
- **Ledger Summary says "Waiting for the Lead to dispatch its first sub-agent..." while
  Frame is running.** Open the Ledger during turn 1; the Frame card is live but Summary
  says waiting. Summary should reflect the phase that is running.
- **Ledger tab dots.** During Frame the Build and Verification tabs carry a purple dot
  with nothing behind them. If the dot means "changed since viewed", an empty section
  should not raise it.
- **Transcript phase cards never resolve after Stop or after a durable interrupt.**
  `build - started` stays after Stop; `Verification - started` stays after a background
  task; a card should end in completed, cancelled, or superseded.
- **Message action buttons have no accessible names.** `read_page` lists Copy, Edit,
  Regenerate, Good, Bad, Branch as `button` with no label (tooltip-only). Add
  `aria-label`.
- **Chat column collapses at 866px.** With the conversation list open and a right panel
  open the chat column is a 30px sliver at 866px viewport width. Below some width the
  right panel or the list should overlay, not squeeze.
- **No auto-scroll on send.** Sending from a scrolled position leaves the new message
  below the fold.
- **Tasks icon badge on a fresh conversation.** Opening `/plasmodb/conversation` (new)
  shows the Tasks dot although the Tasks panel says "No background tasks yet". The badge
  is not scoped to the conversation.
- **Task card shows no result.** A completed background task's card reads "Task
  completed" and the Tasks panel row opens nothing on click; the result (or a link) is
  missing.
- **Workbench: persisted enrichment not restored.** Run enrichment on a set (5 analyses
  saved on the API), click another set, click back: the section shows only Run Enrichment.
- **Workbench: Compose panel promises a Venn.** Select two sets; the panel says "Click a
  region to create a gene set" above an empty area. Either draw the diagram or drop the
  sentence.
- **Workbench polling.** With the workbench open, `gene-sets`, `control-sets`, `me/quota`
  and `veupathdb/auth/status` are re-fetched every couple of seconds.
- **Empty Strategy panel has no way to insert a saved strategy**, and the Saved
  strategies page has no "use in a new chat" action (see the saved-strategy item).
- **Raw transport errors reach the user.** "HTTP 422 Unprocessable Content" (editor
  counts), "stream failed: 403" (workbench), and full pydantic `detail` strings (chat 422,
  scored comparison card). Each should show the field message or one line.
- **Constraints panel loses earlier entries across turns.** VectorBase: turn 1 listed
  target organism, motif, RNA-Seq, record type as provisional; after the clarification
  turn only "Motif proximity criterion" remained.
