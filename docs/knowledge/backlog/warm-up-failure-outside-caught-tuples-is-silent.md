---
type: Backlog Item
title: A warm-up exception outside the caught tuples leaves readiness stuck loading forever, logged only at task GC
description: Since the bind-before-warm-up change (2026-08-27), _warm_up_subsystems runs as a spawned task; each step catches its own expected exception tuples and marks readiness failed, but an exception type outside those tuples kills the whole task, the remaining subsystems stay "loading" in /health/ready indefinitely, and the only trace is asyncio's exception-never-retrieved log at garbage collection. Fix: a done callback on the spawned task that logs the exception and marks every still-loading subsystem failed, plus a test raising an unexpected type from a warm-up step.
tags: [infra, startup, readiness]
generated: { by: claude-code/fable-5, at: 2026-08-27T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-27T00:00:00Z }
status: stable
---

**What I did.** The pair review traced the spawned warm-up's failure paths
in main.py:84-109 and the per-site handler.

**What I got.** Expected exception types mark readiness failed; an
unexpected type kills the task silently and /health/ready reports loading
forever.

**Why that is wrong.** The UI gate polls readiness; a silent kill shows a
permanent spinner with no error anywhere a user or operator looks.

**Why it happens.** The task is spawned without a done callback and the
catch tuples are per-step.

**Fix.** A done callback that logs and fails every still-loading subsystem;
a test raising an unexpected type.

**What you would get.** A warm-up that fails loudly in the same place it
reports progress.
