---
type: Backlog Item
title: A dependent vocabulary read before its parent is bound returns the default set
description: Parent inheritance works once a criterion is bound. The exploratory read that happens first has no parent to inherit, returns the default profileset's terms, and the selection made from it survives into the strategy.
tags: [agents, parameters, wdk-alignment]
generated: { by: claude-code/opus-5, at: 2026-08-12T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-12T00:00:00Z }
status: stable
---

# Symptom

A request for expression across a stated hour range binds a subset of that
range, omitting two hours, and the reply explains only the omissions it chose
deliberately. The two unexplained hours are exactly the pair absent from the
search's DEFAULT profileset and present in the bound one.

# Cause

`get_parameter_options` inherits the parent values the draft spec has already
bound, which fixes the read that happens after binding. Two reads occur:

| read | context | vocabulary |
|---|---|---|
| exploratory, before binding | none to inherit | the search default |
| after binding | the bound parent | correct |

The first read shapes the selection. Nothing is wrong with the second read, and
nothing in the first read is flagged beyond a prose note that the values shown
are the default context's.

# Why the note is not enough

The note is prose next to a list. The list is data, plausible, and the right
length. A reader comparing the two has no reason to distrust the list, and the
model did not.

# Options

1. Refuse the read. A dependent param whose parents are unbound has no single
   answer, so the tool returns the parent list and asks for a context instead of
   a vocabulary. Loud, and it costs one extra call.
2. Answer under every parent. Return the terms common to all parent values, plus
   the ones that vary, so a selection made early cannot silently exclude.
3. Bind the parent first. Order the walk so a parent is resolved before its
   child is offered for inspection.

Option 1 is the smallest and the only one that cannot be ignored.

# Anchor

`get_parameter_options` and `AgentToolState.resolved_params_for` in
`ai/tools/standalone/catalog_discovery.py`. Done when a vocabulary read for a
dependent param either carries its parents or does not return a term list.
