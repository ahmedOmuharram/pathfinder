---
type: Backlog Item
title: A verification digest can report success over a build that pushed nothing
description: In four e2e journeys the build phase failed with "No OperationalSpec to build yet", the ledger recorded criteria 0 / pushed 0 / succeeded no, and the same message still rendered "Verification - completed", "Verified successfully" and a Lead reply of "Verified end-to-end." Nothing compares the digest's success flag against the build the ledger recorded, so a verification verdict is only ever as honest as whoever wrote it.
tags: [investigation, verification, ledger, trust]
generated: { by: claude-code/fable-5, at: 2026-08-20T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-20T00:00:00Z }
status: stable
---

# Investigation

**What I did.** Ran the full Playwright suite (run 10) against the containerized e2e stack.
Four journeys switch to a non-plasmo site - CryptoDB, FungiDB, TriTrypDB, ToxoDB - and send
one strategy-building prompt. Read the DOM snapshot each failure captured
(`test-results/<journey>/error-context.md`), which renders the whole assistant message plus
the Investigation Ledger panel.

**What I got.** In all four, one assistant message carried these lines together:

- `Framed 1 criterion(s) for Plasmodium falciparum genes (mock).`
- `build - failed` / "No OperationalSpec to build yet (no criteria or no structure). Call
  frame_problem first."
- `Verification - completed` / `Verified successfully`
- Lead reply: "**Verified end-to-end.** The strategy framed, built, and verified cleanly -
  root size looks right and the leaves are non-empty."

The ledger in the same DOM, at the same moment:

| section | field | value |
|---|---|---|
| Frame | present | no |
| Frame | criteria | 0 |
| Frame | ready to build | no |
| Build | pushed | 0 |
| Build | succeeded | no |
| Verification | complete | yes |
| Verification | successful | yes |

The right rail offered "Open Strategy" because there was no strategy to show.

**Why that is wrong.** The digest is the sentence a researcher acts on. Here it asserts a
verified strategy over zero built steps, on a screen that simultaneously shows the build
failed. A user who reads the reply and not the phase chips records a result that does not
exist; a user who reads both cannot tell which half to believe. The same shape hides a real
failure whenever a build partially fails and verification still returns success.

**Why it happens.** Nothing reconciles the two. The verification sub-agent returns a
`digest.success` flag, and `finalize_turn` and the Lead render it as given; the ledger's
build section is written from the build result independently. There is no assertion anywhere
that `digest.success` implies the ledger recorded a build that pushed at least one step. In
the run above the flag came from the deterministic test mock, which returned success
unconditionally - but the product accepted a contradiction it could have detected, and the
mock is not the only thing that can produce a wrong flag: a real verification sub-agent that
misreads its input produces exactly the same screen.

**Fix (to decide).** Make the contradiction impossible rather than unlikely. The narrow
version: when the build phase reports failure or pushes zero steps, a verification digest
claiming success is rejected in `finalize_turn` and the turn reports the build failure
instead. The wider version: derive the turn's disposition from the ledger rather than from a
sub-agent's self-report, so the digest can add detail but never overrule what was actually
built. Either needs a unit test that feeds a success digest alongside a zero-push build and
asserts the user-visible verdict is failure. Note that the auto-write to cross-thread memory
also keys on the verification digest reporting success, so this flag decides what is
remembered as well as what is said.

**What you would get.** A verification verdict a researcher can rely on, and one screen that
never contradicts itself. In the run above the reply would have said the build failed and
named the missing spec, which is also the sentence that would have made the four journey
failures self-explanatory.

**Consumers of the unchecked flag** (fixing the digest at source fixes all three): `run_verification`'s delta write, the `nodes.py` memory auto-write, and the eval extractor's verdict read at `services/eval_data/chunk_reader.py:109-110`.
