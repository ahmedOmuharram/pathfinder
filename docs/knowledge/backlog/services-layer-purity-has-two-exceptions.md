---
type: Backlog Item
title: Two experiment service modules import pydantic_ai, and one relocated catalog helper keeps an unreachable branch
description: services/experiment/ai_refinement_tools.py and ai_analysis_tools.py import pydantic_ai.RunContext inside the services layer, contradicting the doctrine the catalog purity walk now enforces (nothing reachable from a service entry point imports pydantic_ai). Separately, services/catalog/search_inspection.py:102 carries an isinstance(vocab, dict) branch that cannot fire (WDKVocabulary is list[WDKVocabTerm] | WDKTreeBoxVocabNode, and the node is a CamelModel), and the query filter silently no-ops on tree vocabularies. Found by the batch B/C review (2026-08-25). Fix: move the experiment tool halves the same way the four catalog tools were split, delete the unreachable branch, and either filter tree vocabularies or state that the filter applies to flat lists only.
tags: [services, layering, mcp, catalog]
generated: { by: claude-code/fable-5, at: 2026-08-25T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-25T00:00:00Z }
status: stable
---

**What I did.** The batch B/C reviewer grepped the services layer for
pydantic_ai imports and read the relocated search_inspection helpers
(2026-08-25).

**What I got.** Two hits outside the reviewed seams:
services/experiment/ai_refinement_tools.py and ai_analysis_tools.py import
RunContext. In services/catalog/search_inspection.py:102, the
isinstance(vocab, dict) branch is unreachable against
WDKVocabulary = list[WDKVocabTerm] | WDKTreeBoxVocabNode, and a query
against a tree vocabulary filters nothing.

**Why that is wrong.** The MCP server imports service functions; a service
that imports pydantic_ai drags the agent framework into a process that
must not run agents, and an unreachable branch reads as handled input that
is not.

**Why it happens.** The experiment tools predate the split-not-moved rule,
and the catalog helper was relocated with a fossil intact.

**Fix.** Split the experiment tool retrieval halves as the catalog four
were split; delete the dead branch; make the tree-vocabulary filter real
or documented as flat-only.

**What you would get.** A services layer the purity walk can cover whole,
and a vocabulary filter that does what it reads.
