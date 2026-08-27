---
type: Convention
title: Verification gates
description: The exact commands that decide whether a change is done, for both apps.
tags: [testing, ci, workflow]
generated: { by: claude-code/opus-5, at: 2026-08-09T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-09T00:00:00Z }
status: stable
---

Gates passing is necessary, not sufficient: see the definition of done in `CLAUDE.md`. These are the commands.

# Backend (`apps/api`)

```
uv run ruff check src/
uv run ruff format --check src/
uv run mypy --strict src/pathfinder/
uv run pyright src/pathfinder/
uv run lint-imports
uv run pytest src/pathfinder/tests/ -q
```

`pyright` is not redundant with `mypy`: it catches variance and invariance errors mypy misses. `lint-imports` enforces the six layering contracts and is the gate that keeps Domain pure. `ruff format --check` is not redundant with `ruff check` either: the two rule sets do not overlap, and formatting drift is invisible to the linter.

The unit tier refuses every connection made through Python's socket module. An autouse fixture in `src/pathfinder/tests/unit/conftest.py` patches `socket.socket.connect`, `connect_ex`, `socket.getaddrinfo` and the event loop's `create_connection`/`getaddrinfo`, so a stub that no longer covers its seam fails there instead of passing against a live server. The refusal derives from `BaseException`, because every HTTP client here retries under `except Exception` and would otherwise swallow it.

Two limits are worth knowing. The guard runs per test, so anything at collection time is outside it, including the PIGuard and fastembed model downloads the root `conftest.py` performs at import. And a C extension that opens its own socket without going through the `socket` module is not covered.

A unit test that needs a real connection carries `@pytest.mark.allow_network`. No production test does: the two database-backed ones live in `tests/integration/`, where they belong. A new marked test needs a reason, because the marker is how the guard is defeated.

## The science verifies in two lanes

The WDK rules answer to two suites, and which lane a rule lands in follows from what can falsify it.

**Per-PR, hermetic, hard gate.** Every rule that a pinned response can settle is a test in `tests/unit/`, reading a recorded fixture through `pathfinder.devtools.wdk_fixtures`. It runs in the ordinary unit tier, needs no network and no credential, and blocks a merge. A rule's `status` line names one of these tests, and `node scripts/check-wdk-rules.mjs` resolves the name and reports how many rules are still unenforced.

**Nightly, live, never blocking.** `pytest -m live_wdk` is the second lane: the same rules against running sites, plus the checks a fixture cannot answer - a search still exists, a vocabulary still carries a pinned term, a sentinel count is still in band, and the pinned fixtures still describe the wire. It skips without `WDK_TEST_EMAIL`/`WDK_TEST_PASSWORD` (or `WDK_TEST_TOKEN`), runs on a schedule in `.github/workflows/wdk-nightly.yml`, and files an issue rather than failing a build. Every resource a live check creates is deleted in teardown: the account is a researcher's own.

```
yarn wdk:live       # run the nightly lane by hand
yarn wdk:record     # re-record the pinned fixtures from live WDK
yarn check:wdk-rules
```

**A confirmed drift is answered by re-recording, not by editing a fixture.** No fixture is written by hand. `apps/api/src/pathfinder/devtools/wdk_fixtures.py` holds the manifest - what to ask, where, and which rules read it - and `record` refreshes the store. Each file carries its own provenance as data: site, method, url, status, content type, and the date it was recorded. Recording needs `VEUPATHDB_AUTH_TOKEN`, because VEuPathDB refuses anonymous service calls; every manifest entry is user-independent, so no account is addressed.

The lane writes `wdk-live-summary.json`: the run's outcomes, a per-site tally, and the drift list. It is the science layer's feed into the observability contract.

**An unenforced rule must say why.** `check-wdk-rules.mjs` fails a rule whose status is `UNENFORCED` and whose block carries no `reason`. A rule with no test and no reason is a claim nobody is checking.

## The logic verifies as a trend, and is promoted to a gate only by evidence

The assistant's evals answer "did this change make it worse at real tasks", and a bad answer is a judgement, not a crash. So the eval lane is not a gate on arrival.

**An eval starts as a tracked trend.** It runs on demand, it writes its result, and a regression in it is read, not enforced. Nothing blocks on it.

**An eval becomes a hard gate only after it catches, or would have caught, a real regression, and then holds stable.** "Would have caught" counts: a case written from a failure already in the backlog qualifies once it is shown to fail on the code that had the bug and pass on the code that fixed it. "Holds stable" means it has not flipped without the assistant changing.

**A flaking gate is demoted or deleted, never suppressed.** No skip mark, no retry loop, no tolerance widened until the red goes away. A gate that cannot decide is answering a question it cannot answer, and it goes back to being a trend, or it goes.

```
cd apps/api
uv run python -m pathfinder.devtools.evals corpus                 # the cases
uv run python -m pathfinder.devtools.evals run --out summary.json  # run them
```

The corpus lives in `apps/api/src/pathfinder/evals/corpus/`, one JSON file per case, each carrying its own provenance as data. A case arrives one of two ways: promoted from the staging queue by `pathfinder.devtools.evals promote`, or written from a cataloged failure in `backlog/`. No case names a user; see [the linkage decision](../decisions/a-staged-eval-case-carries-its-user-until-promotion.md).

**A run under the deterministic provider tests the pipeline, not the model.** The mock is a script, so a green run says the routing, the materialisation, the persistence and the reported verdict still behave; it does not say a real model would have chosen that route. The corpus is provider-agnostic, so a real-model run is the same command with a different provider.

The run writes `EvalRunSummary`: harness, provider, assistant, per-case verdict and named differences. It is the logic layer's feed into the observability contract.

# Assistant runtime (`packages/assistant-core`)

```
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy --strict src
uv run pytest
```

Run these from the package root, in the package's own environment. No
`pathfinder` is installed there, and that is the point: the suite passing is
the boundary, not a linter rule about it. `ruff` and the tests cover `tests/`
too, because the synthetic assistant lives there and is the runtime's
reference producer.

`pytest` needs a Postgres. It starts a `pgvector/pgvector:pg16` testcontainer
unless `DATABASE_URL` names one, and the conversation suite drives real
LISTEN/NOTIFY, so an in-memory substitute will not do.

`PROTOCOL.md` is gated by the suite: a chunk kind, a data part or an example
that changes without the page changing fails
`tests/integration/conversation/test_protocol_document.py`.

# Assistant client (`packages/assistant-client-ts`)

```
yarn typecheck
yarn lint
yarn format:check
yarn test
yarn build
```

Run these from the package root. The suite is the protocol's consumer side, so
a `PROTOCOL.md` change fails it until `yarn sync:protocol` regenerates the
vendored capture and a reducer answers the new kind.

`yarn build` is a gate because nothing else reads `dist/`. The app resolves the
package through its tsconfig `paths` and its vitest aliases, both of which name
`src`, so only this command and a `yarn pack` exercise the artifact a host
installs.

# MCP conformance suite (`packages/mcp-conformance`)

```
uv run ruff check src tests
uv run mypy --strict src
uv run pytest
```

Run these from the package root, in its own environment. Nothing of this
deployment is installed there, and a test walks every module to keep it that
way: the suite is run by teams whose servers we did not write.

`pytest` starts fixture MCP servers on loopback ports and drives the shipped
families at them in a child pytest, once against a compliant server and once
per planted defect. A defect must fail the check that owns it and no other. No
database, no credential and no network beyond loopback.

The families themselves are not part of this gate. They run against a server:
`pytest --pyargs mcp_conformance --mcp-endpoint <url> --mcp-bearer <token>`,
and the report they write is what an operator reads before admitting a source.

**Our own server is read the same way, in the live lane.**
`apps/api/src/pathfinder/tests/integration/mcp/` is marked `live_wdk`, so it
skips without `WDK_TEST_EMAIL`/`WDK_TEST_PASSWORD` and without
`PATHFINDER_MCP_SERVICE_TOKENS` naming the value the served container carries.
`test_conformance_ours.py` runs the suite as its own process against
`PATHFINDER_MCP_URL` (default `http://localhost:8100/mcp`) with the WDK-backed
account hook, and reads the admission record; `MCP_ADMISSION_REPORT` names where
that record is written for a lane to collect. `.github/workflows/mcp-nightly.yml`
serves the endpoint, runs the lane on a schedule, uploads the record and files
an issue on failure. Like the WDK lane, it never blocks a pull request: an
admitted source is quarantined by an issue, not by a red build.

Only warm sites appear in that run's arguments. A catalog read of a site the
container has not loaded builds a per-site index inside a 2g ceiling and the
kernel kills the process, which is a memory decision and not a conformance
result.

# Frontend (`apps/web`)

```
npx tsc --noEmit
npx eslint src/
node scripts/check-boundaries.mjs
npx vitest run
```

# Mutation testing (`apps/web`)

```
rm -f .stryker-tmp/incremental.json
./node_modules/.bin/stryker run
```

**Delete `incremental.json` first, every time.** The config sets `incremental: true`, and the cache goes stale: it reports mutants that current tests kill as survived. That cost real time once. If a survivor looks impossible, apply the mutation by hand and run the tests before believing the report.

Last full run: 100.00% across the eight `src/state/strategy` modules, zero survivors, zero uncovered.

# Docker

```
docker compose --env-file .env.dev up -d --build --force-recreate api worker
```

`--force-recreate` is not optional. Without it, `up -d --build` can build a new image and leave the old container running, so you verify code that is not deployed. Confirm by grepping for a new symbol inside the container before trusting a manual test.
