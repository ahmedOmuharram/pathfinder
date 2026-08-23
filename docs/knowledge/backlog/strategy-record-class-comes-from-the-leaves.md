---
type: Backlog Item
title: A strategy's record class is read off its first leaf, and WDK reads it off the root
description: PathFinder holds one record type per graph and threads it into every step's search URL. The two answers coincide for every strategy built from one record class and diverge the moment a class-crossing transform is used.
tags: [wdk-alignment, strategy, modelling]
generated: { by: claude-code/opus-5, at: 2026-08-22T00:00:00Z }
status: stable
---

# What is wrong

[WDK-STRAT-004](../wdk/rules/strategies-and-steps.md) says `Strategy.getRecordClass`
delegates to `getRootStep().getRecordClass()`. A transform changes record class:
`TranscriptsFromGenes` takes a `gene` input and produces transcripts, so a strategy whose
leaves are genes and whose root is that transform is a transcript strategy.

`services/catalog/searches.py:resolve_record_type_from_steps` walks
`collect_plan_leaves(root)` and returns the record type of the first leaf search that
resolves. `services/strategies/sync.py:308` stores that on `graph.record_type`.

# Why it is not simply fixed

`graph.record_type` is not only the strategy's class. It is threaded into
`services/strategies/step_wdk_push.py` and addresses **every** step's search URL, which is
`/record-types/{record_type}/searches/{search_name}` and 404s under the wrong record type
([WDK-SEARCH-001](../wdk/rules/searches-and-answers.md)). Changing the graph-level value to
the root's class would therefore break the leaf pushes it also addresses.

So the fix is a modelling change: a step carries its own record class, the push uses the
step's, and the strategy's is the root's. That is why the rule is the one
`UNENFORCED` entry in the bundle, and why its `reason` field names this item.

# Done when

A step carries its own record class, `resolve_record_type_from_steps` is replaced by a
root-first read, and WDK-STRAT-004 names a test that would go red if the strategy's class
were taken from a leaf.
