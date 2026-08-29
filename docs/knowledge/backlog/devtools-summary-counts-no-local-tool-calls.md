---
type: Backlog Item
title: The devtools run summary prints toolcalls=0 for turns whose event log holds tool calls
description: Sighted three times by batch reviews (D, G, and the 2026-08-27 pair review): a site_help turn whose events.jsonl carries tool-input-available chunks prints toolcalls=0 in the devtools summary line. The artifacts are complete and legible; only the counter lies. Cosmetic but it misleads every quick read of a run. Fix: count tool calls from the event log rather than whatever source skips this assistant's local and MCP-sourced calls, with a test over a recorded run dir.
tags: [devtools, diagnosis]
generated: { by: claude-code/fable-5, at: 2026-08-27T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-27T00:00:00Z }
status: stable
---

**What I did.** Three separate reviews drove mock turns through
pathfinder.devtools.chat and compared the summary line to events.jsonl.

**What I got.** toolcalls=0 printed for turns whose logs hold
tool-input-available chunks (site_help local tools and MCP-sourced tools).

**Why that is wrong.** The summary is the first thing a reader trusts; a
zero over a log full of calls sends the debugging in the wrong direction.

**Why it happens.** The counter reads a source that only sees the Lead's
dispatch shape, not a one-agent assistant's own calls.

**Fix.** Count from the event log; pin with a recorded run dir.

**What you would get.** A summary line that agrees with its own artifacts.
