---
type: Backlog Item
title: The eval extractor opens a turn per user-message envelope, so a legacy duplicate yields a phantom turn
description: services/eval_data/chunk_reader.py:88 read_turns starts a new turn at every user-message envelope. Four conversations on the dev database predate the once-per-id log guard (2026-08-25) and hold one duplicated envelope each, so extraction over them produces a phantom turn with a doubled request and a split reply. The write path and the snapshot reducer are fixed (keep-first); the extractor was not reconciled. Fix: skip an envelope whose id was already seen in the thread, mirroring the reducer's rule, with a test over the incident-shaped sequence.
tags: [evals, extraction, chat]
generated: { by: claude-code/fable-5, at: 2026-08-25T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-25T00:00:00Z }
status: stable
---

**What I did.** The duplicate-id fix review read read_turns against the four
legacy conversations that hold a duplicated user-message envelope.

**What I got.** A turn boundary at each envelope, so the duplicated id opens
a phantom turn: the request text twice, the reply split across two turns.

**Why that is wrong.** An extracted case with a doubled prompt and a broken
reply poisons the eval corpus for as long as the case lives.

**Why it happens.** read_turns keys turn starts on the envelope kind alone;
the keep-first rule lives only in the client reducer.

**Fix.** Skip an envelope whose id was already seen in the thread, mirroring
the reducer, with a test over the incident-shaped sequence.

**What you would get.** Extraction that agrees with what a reader of the
thread actually sees.
