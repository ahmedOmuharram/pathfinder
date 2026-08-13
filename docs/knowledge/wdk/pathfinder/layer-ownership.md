---
type: Reference
title: Who is allowed to talk to WDK
description: The six import-linter contracts that police the WDK boundary, exactly what each one forbids, the one seam that lets WDK types out of the integration layer, and the two things the contracts cannot see.
tags: [wdk-alignment, layering, import-linter, ownership, pathfinder]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
status: stable
---

Every permalink below is pinned to the sha recorded in [sources.md](../sources.md).

# This is checked, so read the check rather than the prose

The layering rule itself is in `CLAUDE.md` and is not repeated here. What is here
is the machine that enforces it, what that machine actually forbids as opposed to
what the prose says, and where it is blind.

Six `forbidden` contracts live under `[tool.importlinter]` in
`apps/api/pyproject.toml`, over `root_packages = ["pathfinder"]` with
`include_external_packages = true`. Run them with `cd apps/api && uv run lint-imports`.

| Contract name | Source | Forbidden | Named by a rule? |
|---|---|---|---|
| Domain layer is pure (no I/O, no other layers) | `pathfinder.domain` | `integrations`, `services`, `transport`, `persistence`, `ai`, and the external `httpx`, `sqlalchemy`, `asyncpg`, `fastapi` | yes - [WDK-MAP-002](../rules/pathfinder-mapping.md), [WDK-MAP-007](../rules/pathfinder-mapping.md) |
| AI tools never import integrations or persistence directly | `pathfinder.ai.tools` | `integrations`, `persistence` | yes - [WDK-MAP-004](../rules/pathfinder-mapping.md) |
| Transport never imports integrations or persistence directly | `pathfinder.transport` | `integrations`, `persistence` | **no** |
| Services never import transport or AI | `pathfinder.services` | `transport`, `ai` | **no** |
| Integrations never import services, transport, or AI | `pathfinder.integrations` | `services`, `transport`, `ai` | **no** |
| Persistence never imports services, transport, AI, or integrations | `pathfinder.persistence` | `services`, `transport`, `ai`, `integrations` | **no** |

**The last column is this table's own expiry date, and it is not decoration.** This
table restates `pyproject.toml`, so it can go stale the moment a contract is
renamed or dropped. Two of the six names are load-bearing elsewhere: they appear in
a rule's `status` field, and `scripts/check-wdk-rules.mjs` fails when a named
selector is no longer found in the file it points at. Rename either of those two
and the gate goes red.

**The four rows marked "no" are unguarded.** Nothing connects them to this
document, so if one is renamed or deleted, this table quietly becomes fiction. They
are kept because the asymmetry below is only visible with all six present, and
because a reader deciding where code belongs needs the whole picture rather than
the checked part of it. Treat them as a snapshot dated 2026-08-10, and read
`pyproject.toml` when it matters.

**The domain contract is stronger than the other five, and the difference is one
line.** The other five set `allow_indirect_imports = true`; the domain contract
does not. `import-linter`'s `ForbiddenContract` defaults that flag to `False` and
checks import *chains*, so the domain contract fails on `domain -> X -> httpx` as
well as on `domain -> httpx`. The other five fail only on a direct import
statement. That is a deliberate asymmetry - the domain layer is the one that must
be provably pure, and everything else is being kept honest about its dependencies
rather than its transitive closure - but it means five of the six contracts are
contracts about **import statements**, not about reachability.

`uv run lint-imports` reports **6 kept, 0 broken**. The AI-tools contract has been
red once, on a single edge from `catalog_discovery` into a WDK client wrapper that
belonged in the service layer; moving the wrapper cleared it. See
[WDK-MAP-004](../rules/pathfinder-mapping.md).

# The seam: `services.wdk`

The contract above is satisfied in practice by one module.
`services/wdk/__init__.py` re-exports the WDK client factories and the WDK types
that higher layers legitimately need - `StrategyAPI`, `VEuPathDBClient`,
`get_wdk_client`, `get_site`, `WDKAnswer`, `WDKParameter`, `WDKSearchConfig` and
a dozen more - so that an AI tool writes `from pathfinder.services.wdk import
WDKParameter` and never names `pathfinder.integrations`.

That is the whole mechanism, and it is worth being precise about what it does and
does not buy.

**It does not keep WDK types out of the AI layer.** `ai/tools/standalone/_catalog_models.py`
holds `WDKParameter` and `WDKBaseParameter`; `_result_models.py` holds `WDKAnswer`
and `StrategyAPI`. Those are integration-layer types in agent-facing code, and the
contract is green on them because the import names a service module. The contract
polices the **import path**, not the type.

**What it does buy is a chokepoint.** Every WDK type an upper layer can reach is
listed in one `__all__`, so widening the surface is a visible edit to one file
rather than an import added anywhere. Narrowing it later is a mechanical exercise
for the same reason.

Measured on 2026-08-10, `from pathfinder.integrations` appears in 60 modules under
`services/`, 28 under `integrations/`, 41 under `tests/`, one in `main.py`, one in
`devtools/`, and **three under `ai/`**. Two of the three import
`integrations.embeddings.prefixes`, which is the local embedding model and not WDK
at all; the third is the broken edge above. `transport/` and `jobs/` contain
**zero**.

# The two things the contracts cannot see

## A raw HTTP call to a WDK host

`import-linter` forbids importing `pathfinder.integrations`. It says nothing about
importing `httpx` and calling a VEuPathDB URL, because `httpx` is only in the
forbidden list of the domain contract.

Every non-test module under `src/pathfinder/` that imports `httpx` was read on
2026-08-10. Most catch its exception types without making a call; the literature
clients under `services/research/` call arXiv, Crossref, PubMed and the rest.
Exactly one builds a client against a VEuPathDB base URL.
`transport/http/routers/veupathdb_auth.py` constructs its own
`httpx.AsyncClient(base_url=auth_site.service_url)` and calls `GET /logout` on it.
Every contract is green on that file, and it is a transport module talking to WDK.

The consequence is worth stating because it is not obvious.
[`SessionService.processLogout`](https://github.com/VEuPathDB/WDK/blob/e534d2e6a5119165e1742c7a9e07a371217ddda5/Service/src/main/java/org/gusdb/wdk/service/service/SessionService.java#L277-L311)
acts on `getRequestingUser()` - the identity carried by *that* request's cookies -
and returns immediately when that user is a guest. The client PathFinder builds
there carries no cookie jar and no `Authorization` header, and a credential-less
request is served as a fresh guest ([WDK-AUTH-001](../rules/auth-and-transport.md)).
Read literally, that call cannot log the browser's WDK user out of anything. **This
reading is from pinned source and was not confirmed against a live site**, which is
the only reason it is written as a reading. It is filed as
[logout-call-cannot-invalidate-the-token](../../backlog/logout-call-cannot-invalidate-the-token.md),
which sets out the four-step live check that would either confirm it or retire it.

What is not in doubt is the layering fact, which is measured: a transport module
opens a socket to a WDK host, and no contract objects. That is why
[WDK-MAP-005](../rules/pathfinder-mapping.md) is `UNENFORCED` rather than partially
covered by the transport contract - that contract forbids an import, which is a
different proposition, and this call is the proof that the two come apart.

## Which types cross a boundary

A contract is about modules, not about the types that flow between them. So the
question "where may a WDK type appear" is answered by a different measurement.

`openapi.json` holds 283 schemas on 2026-08-10. Eight of them are named `WDK*`:
`WDKVocabTerm`, `WDKVocabNodeData`, `WDKTreeBoxVocabNode`, `WDKFilterOntologyTerm`,
`WDKDatasetParser`, `WDKRecordIdPart`, `WDKHistogramBin`, `WDKHistogramStatistics`.
**All eight are defined in `domain/` - five in `domain/parameters/wdk_vocab.py`,
three in `domain/wdk_values.py` - and none in `integrations/`.** Not one of the
`WDK*` response models in `integrations/veupathdb/wdk_models.py` reaches the wire.

So the answer is: a WDK-*shaped* type may reach the browser if it is a pure value
object owned by `domain/`; a WDK-*response* type may not leave the integration
layer except through `services.wdk`, and never onto the wire. That is
[WDK-MAP-007](../rules/pathfinder-mapping.md), and it is enforced for the domain
half by the strongest of the six contracts: putting one of those value models in
`integrations/` and importing it from `domain/` breaks
`Domain layer is pure (no I/O, no other layers)` immediately.

# Why an AI tool calls a service and not an integration

The layering answer is in `CLAUDE.md`. The WDK-specific answer is not, and it is
the one that matters here: **a WDK conversation is stateful, and the state lives on
the client object.**

WDK identity travels as an `Authorization` cookie, and a request that arrives
without one is not rejected - a new guest is minted for it, **a different one each
time** ([WDK-AUTH-001](../rules/auth-and-transport.md)). A client built without that
cookie is therefore a different user on every call, and nothing says so. A client
reused across identities has the mirror-image problem: it can carry the previous
identity's `JSESSIONID` into the next call, which can only ever bind the request to
the wrong container session, so PathFinder drops it whenever the effective token
changes ([WDK-AUTH-003](../rules/auth-and-transport.md)).

What that costs is continuity of identity, and nothing weaker. An agent tool that
built its own client would not fail loudly: it would act as a guest that owns
nothing, so a strategy it created on one call is invisible on the next, the list
comes back `[]` rather than an error, and the model reports that emptiness to a
researcher as a finding. That is the failure mode the whole `SILENT` class in
[the rules](../rules/) exists to name, and it is why the tool layer gets
`get_strategy_api()` from `services.wdk` rather than a URL.

Do **not** reach for the other explanation. The belief that a process query returns
zero without a `JSESSIONID` did not reproduce - a cookie-less
`GenesByOrthologPattern` returned `totalCount` a large result - and it is recorded as an open
question in [transport-quirks](../rest/transport-quirks.md) rather than as a rule.
The identity argument above is the one that is measured.

# The frontend does not speak to WDK at all

Measured on 2026-08-10 across `apps/web/src`: three files contain a VEuPathDB URL
and all three are `.test.tsx` fixtures for `wdkUrl`, a string the backend supplies
and the UI renders as an `href`. No non-test file contains a `*db.org` URL or a
`/service/` path, and no component fetches one.

The browser's entire view of WDK is whatever `openapi.json` describes, which is the
eight domain-owned value types above plus PathFinder's own projections. Adding a
direct call from the browser to plasmodb.org would break nothing mechanical today -
`check-boundaries.mjs` polices feature isolation, not hostnames - so this section
is a measurement rather than a guarantee.
