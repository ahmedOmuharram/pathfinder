---
type: Backlog Item
title: A search selection carries six fields nothing writes
description: SearchOverview keeps decided, selection_status, rationale, selection_reason, confidence and param_hints. Their only writer was update_search_decision, which was registered in no toolset and is now deleted. Two catalog tools filter their results on decided_search_names() and the pinned discovered-searches instruction renders selection_status, so both run against a value that is always the default. Fix is to remove the fields and the branches that read them, or to give them a writer in the set_criterion flow.
tags: [agents, tools, state]
generated: { by: claude-code/opus-5, at: 2026-08-24T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-24T00:00:00Z }
status: stable
---

**What I did.** Deleted `update_search_decision` and its module
(`ai/tools/standalone/catalog_selection.py`), then searched for the remaining
writers of the selection fields on `SearchOverview`
(`ai/agents/state.py:36-50`).

**What I got.** Zero writers. `decided` is set to `True` in exactly one place
before the deletion - inside `update_search_decision` - and that tool is
registered in no toolset, so no agent could ever call it. The same holds for
`selection_status`, `rationale`, `selection_reason`, `confidence` and
`param_hints`. Meanwhile three readers still run every turn:
`AgentToolState.decided_search_names()` (`state.py:149`), consumed by
`search_for_searches` (`catalog.py:83-85`) and `list_searches`
(`catalog.py:139-140`) to hide already-decided searches; and
`pinned_discovered_searches` (`strategy_instructions.py:81-90`), which renders
a `[selected]` / `[rejected]` tag.

**Why that is wrong.** The hidden-search filter is dead: `decided` is always
`False`, so the "N already-decided search(es) hidden" note can never appear and
the model re-reads searches it has already ruled out. The pinned instruction
promises the model a selection verdict per search and always shows the default.
A reader that can only ever see one value is a branch that lies about what the
turn knows.

**Why it happens.** FRAME replaced the select-then-plan flow with
`set_criterion`, which binds a search directly and never records a verdict on
the searches it passed over.

**Fix.** One decision for the group: delete the six fields, `SearchSelectionStatus`,
`decided_search_names()`, `selected_search_names()` and the branches in
`catalog.py`, `strategy_instructions.py` and `toolsets/verification.py` that read
them; or have `set_criterion` and `drop_criterion` write the verdict so the
readers see real values. `_verification_enum_overrides` reads
`selected_search_names()`, so the choice decides whether that override survives.

**What you would get.** Either a catalog that really does stop re-offering a
search the turn already ruled out, or one less always-default field per search
in the state the agents carry.
