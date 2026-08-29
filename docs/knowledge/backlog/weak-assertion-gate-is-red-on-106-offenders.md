---
type: Backlog Item
title: The frontend weak-assertion gate is red on 106 offenders outside its baseline
description: apps/web/scripts/check-weak-assertions.mjs exits 1 on 106 test files whose only matchers are weak (toBeTruthy, toBeDefined, toBeTypeOf) and that are not in scripts/.weak-baseline.txt, which suppresses 209 older ones; measured 2026-08-28 during EDA batch 4, unchanged before and after that batch's edits. Every frontend batch ladder in the EDA plan lists this gate, so each implementer must scope it to its own files until the backlog is either fixed or re-baselined. Re-measured at 99 after the chat-path sweep strengthened seven of them.
tags: [tests, frontend, gates, ratchet]
generated: { by: claude-code/fable-5, at: 2026-08-28T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-28T00:00:00Z }
status: stable
---

**What I did.** Ran `node scripts/check-weak-assertions.mjs` from `apps/web`
before and after EDA batch 4's frontend edits.

**What I got.** Exit 1 both times with the same 106 offenders (for example
`src/components/ai-elements/tool.test.tsx:20`,
`src/state/useRightRailStore.test.ts:46`), and the line "Baseline at
scripts/.weak-baseline.txt suppresses 209 pre-existing offender(s)". Batch 4's
one new offender was fixed by its implementer; the count returned to 106.

**Why that is wrong.** A ratchet gate that is red on the trunk cannot ratchet:
a new weak test is invisible inside 106 existing ones, and every plan ladder
that names the gate must carve out "scoped to my files" by hand.

**Why it happens.** 106 test files gained weak-only assertions after the
baseline was frozen, and neither the pre-commit hook nor CI runs this script
on the whole tree, so nothing forced the count back to zero.

**Fix.** Either fix the 106 (a strong matcher each: `toEqual`, `toBe` with a
literal, `toHaveTextContent`, `toHaveLength`, ...) or, if the team decides the
baseline is the contract, regenerate `.weak-baseline.txt` from the current
tree and put the script in CI so it can never drift again. Record whichever
in `docs/knowledge/conventions/verification-gates.md`.

**What you would get.** A green ratchet: exit 0 on the trunk, and one red line
naming the file the next time someone adds a test that asserts nothing.
