---
type: Backlog Item
title: VERIFY's instructions tell the model to chain three tools, and none of them is in its toolset
description: The verification sub-agent's instructions direct the model to chain literature_search, lookup_gene_records and resolve_gene_ids_to_records when controls are needed, but none of the three is in the VERIFY toolset, and resolve_gene_ids_to_records is in no toolset at all. Every controls-needing verification spends at least one model turn calling a tool that does not exist before recovering. Found by the MCP design review (docs/design/2026-08-23-mcp-and-sdk-program.md, Appendix B) while inventorying tool surfaces; the same sweep found browse_search_categories, list_transforms and update_search_decision registered in no toolset while ai/context/extractors.py names the first two, so the extractor lists tools that can never produce an observation. Fix is one decision per tool - add it to the toolset or delete the instruction/extractor reference - and a test pinning that every tool an instruction or extractor names is callable by that agent.
tags: [agents, tools, verification]
generated: { by: claude-code/fable-5, at: 2026-08-23T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-23T00:00:00Z }
status: stable
---

**What I did.** The MCP design agent inventoried every toolset and every tool
reference while writing docs/design/2026-08-23-mcp-and-sdk-program.md.

**What I got.** apps/api/src/pathfinder/ai/tools/toolsets/verification.py
(instructions around lines 65-68) tells the model to chain
`literature_search` then `lookup_gene_records` then
`resolve_gene_ids_to_records`; the VERIFY toolset contains none of them, and
`resolve_gene_ids_to_records` appears in no toolset anywhere. Separately,
`browse_search_categories`, `list_transforms` and `update_search_decision`
are defined but registered in no toolset, while
`ai/context/extractors.py:197,199` names the first two.

**Why that is wrong.** A verification that needs controls spends a model turn
on a nonexistent tool call and its retry before doing anything real - wasted
tokens and latency on every such turn - and the context extractor promises
observations from tools that can never run.

**Why it happens.** Instructions, extractors and toolsets are maintained by
hand with nothing asserting agreement.

**Fix.** Per tool: register it or delete the reference. Then one test walking
every agent's instructions and the extractor registry, asserting every named
tool is callable by that agent, so the three lists cannot drift again.

**What you would get.** No wasted first turn on controls-needing
verifications, an extractor that only names real observation sources, and a
gate that keeps it true.
