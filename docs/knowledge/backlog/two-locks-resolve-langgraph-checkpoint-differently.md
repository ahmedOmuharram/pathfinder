---
type: Backlog Item
title: The api and the runtime package lock different langgraph-checkpoint versions, so the package suite proves decode behaviour the app does not run
description: Both pyprojects pin `langgraph==1.1.6` and `langgraph-checkpoint-postgres==3.0.5`, and the transitive `langgraph-checkpoint` resolves to 4.0.1 in `apps/api/uv.lock` and 4.2.0 in `packages/assistant-core/uv.lock`. The two versions decode checkpoints differently, so ladder R can be green on serialization behaviour that ladder P never executes.
tags: [assistant-core, checkpointer, langgraph, dependencies]
generated: { by: claude-code/opus-5, at: 2026-08-24T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-24T00:00:00Z }
status: stable
---

# What was measured

`grep -n '^name = "langgraph-checkpoint"' -A 2` on both locks:
`apps/api/uv.lock:1446` reports `version = "4.0.1"`, and
`packages/assistant-core/uv.lock:1123` reports `version = "4.2.0"`. Both
installs satisfy the same two pins, and both venvs are installed from their own
lock.

The two versions do not decode alike:

| behaviour | 4.0.1 (`apps/api`) | 4.2.0 (`packages/assistant-core`) |
|---|---|---|
| unregistered-type warning | one log line per decoded value | deduplicated per type for the life of the process, capped at 1000 types |
| JSON revival | `Reviver()` | `Reviver(allowed_objects="core")`, plus a safe-type bypass for pre-msgpack checkpoints |

The same undeclared type therefore produced one warning line in the package
suite and one line per occurrence in the api suite.

# Why that matters

`assistant_core` owns the checkpoint serializer, and its suite is the gate that
decides whether a state type survives a round trip. A gate that runs a
different serializer version than production can pass while the app is broken,
in either direction: a decode rule tightened in 4.2.0 is enforced only in the
package lane, and a warning the api lane would print is deduplicated away in
the package lane.

# What to do

Decide where the version is owned. Either pin `langgraph-checkpoint`
explicitly in both pyprojects so the two locks agree, or make the api resolve
it through the package it already depends on. Then assert the agreement: a test
or a lint step that compares the resolved version in the two locks fails when
they drift again.
