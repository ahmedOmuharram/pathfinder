---
type: Backlog Item
title: apps/web's yarn lint cannot complete on this host, so CI's lint-web eslint step can never pass
description: yarn lint runs eslint over the whole directory and dies at the default 4 GiB heap in about 4 minutes, and again at a 10 GiB heap after 571 s (exit 134, ineffective mark-compacts near heap limit), measured 2026-08-25 during the client dist work. CI's lint-web job runs the same command on a 7 GiB runner. The documented gate npx eslint src/ passes clean, so the gap is the un-scoped invocation, likely pulling generated or build output into the lint program. Related: web-lint-job-is-red-on-formatting.md covers the same job's formatting step; this is its eslint step. Fix: scope the lint script to src (matching the documented gate) or fix the ignore set so the whole-dir run terminates, then make CI and the docs run the same command.
tags: [web, lint, ci, gates]
generated: { by: claude-code/fable-5, at: 2026-08-25T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-25T00:00:00Z }
status: stable
---

**What I did.** Ran apps/web's yarn lint on this host at the default heap
and again with a 10 GiB heap (2026-08-25).

**What I got.** OOM at ~4 minutes on the default heap; exit 134 after
571 s at 10 GiB with "Ineffective mark-compacts near heap limit". The
documented gate, npx eslint src/, exits 0.

**Why that is wrong.** CI's lint-web job runs the failing command on a
7 GiB runner, so the job cannot pass regardless of code quality, and a
gate that cannot pass gates nothing.

**Why it happens.** The script lints the whole directory rather than src,
so the lint program swallows generated or build output the documented
gate never sees.

**Fix.** Scope the script to src or repair the ignore set, then align CI
and the documented commands on one invocation.

**What you would get.** A lint-web job whose red means the code is wrong.
