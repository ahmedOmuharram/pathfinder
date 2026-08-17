---
type: Backlog Item
title: A unit test whose stub misses its seam reaches the live WDK and still passes
description: Nothing in the unit tier blocks sockets, so a monkeypatch on the wrong module attribute is inert and the test performs a real HTTPS request. One such test was found and fixed; the class is open.
tags: [testing, tooling]
generated: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# Symptom

`tests/unit/ai/tools/test_get_search_overview_ranks_on_the_goal.py` patched
`catalog_discovery.get_wdk_client` after the client seam had moved to
`_catalog_models.read_search_definition`. The stub was never consulted, the
test issued a real GET to plasmodb.org, and it passed because the network was
up. With `HTTPS_PROXY=http://127.0.0.1:9` it failed with `httpx.ConnectError`.
The seam has been repointed; the hazard that let it pass has not.

# Why it matters

A unit tier that can reach the network is a unit tier that can go green on
someone else's server and red on a plane. It also hides exactly the class of
regression a refactor introduces: a stub that no longer stubs.

# Fix

An autouse fixture in the unit tier's `conftest.py` that refuses socket
connections (a `socket.socket.connect` guard, or `pytest-socket` if a dependency
is acceptable), with an explicit opt-in marker for the few unit tests that
legitimately need loopback. Run the unit suite once under it and repoint every
stub it exposes.

# Anchor

`apps/api/src/pathfinder/tests/unit/conftest.py`. Done when the unit suite
passes with sockets refused.
