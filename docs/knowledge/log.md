# Log

## 2026-08-29

* **Embeddings became an API call and two Postgres tables.** The local
  `nomic-embed-text-v1.5` is deleted: 547 MB on disk, 967 MB resident per
  process before it encoded a text, one sequence at a time on CPU in the api,
  the worker and `wdk-mcp`. Measured before the change on 2026-08-29: a cold
  rebuild of every cache was about 110 minutes, the portal alone about 50;
  thirteen of the fourteen committed `.npz` files carried the retired shape, so
  7,184 of 7,699 shipped rows were dead; the quadlets persisted no cache volume;
  and `search_example_plans` re-embedded the whole public strategy list on every
  call, 46 s for a patient client. Every vector now comes from OpenAI
  `text-embedding-3-large` at 1024 dimensions through
  `assistant_core/embeddings/openai_embedder.py`, cut at 2000 characters,
  grouped into requests of at most 256 inputs and 200,000 characters, and run
  eight at a time in input order.
  `assistant_core/embeddings/record_manager.py` owns `embedding_vectors` and
  `embedding_index_entries`: a vector is addressed by
  `sha256(model + "\n" + text)`, two indexes sharing one text share one row,
  `sync_index` embeds only what changed and answers with a `SyncReport`, and
  `search_index` ranks in SQL with `1 - (embedding <=> :query)`. The three index
  ids are `catalog:{site_id}`, `eda-studies` and `public-strategies:{site_id}`.
  Two of the three old indexes multiplied unnormalized vectors, so their scores
  ran to about 340 and the catalog multiplied that by `_SEMANTIC_BOOST = 15.0`:
  the ranking was embedding order and the lexical score did not participate.
  Measured on the plasmodb snapshot over its 515 searches, the top lexical
  score of five research queries was 45.3, 106.9, 44.7, 49.2 and 60.4, so the
  boost is 70.0 against a cosine and a cosine of 0.7 buys 49.0, the median top.
  `EMBEDDING_INDEX_SYNC_ENABLED` replaces `EDA_STUDY_INDEX_BUILD_ENABLED` and is
  true only on the api; the worker and `wdk-mcp` search what the api wrote, in
  compose and in both quadlets, which one test now reads for every guarded unit. An
  `EmbeddingUnavailableError` never 500s: the catalog ranks lexically, the study
  search matches names and says so, the public strategies fall back to token
  overlap, and memory retrieval returns nothing. The nomic query and document
  prefixes are gone with the model, and with them the LangGraph
  `aembed_documents` trap. Recorded as [embeddings are an API call and a
  Postgres record manager](decisions/embeddings-are-an-api-and-a-record-manager.md).

* **A study description is bounded, and a dead worker no longer holds a turn
  open.** One prompt on plasmodb called `search_eda_studies`, the worker built
  the EDA study index cold, and docker reported `oom` and `die 137` on
  `pathfinder-worker-1` 49 seconds later. Measured in the api container with a
  real login: 759 studies, `study_enriched_text` up to 24,820 characters, a
  cold encode of 458.7 s peaking at 4.70 GiB. `study_index.DESCRIPTION_LIMIT`
  now cuts the description at 2,000 characters, which touches 34 of the 759
  and brings the same encode to 368.4 s peaking at 1.19 GiB. Batching the
  model was measured and rejected: a length-sorted batch under a 16,384
  padded-character budget was OOM-killed inside the worker after 47 seconds,
  so `_embed` keeps `batch_size=1` and one document is the only thing in the
  arena. The EDA service answers with the portal's catalog, byte-identical on
  plasmodb, toxodb, hostdb, vectorbase and orthomcl, so the rows live in one
  content-addressed store, `eda-studies.npz`, and `preload_study_indexes` in
  the api warm-up fills it under the service account token, leaving the worker
  nothing to encode. The worker is also forbidden to encode it:
  `EDA_STUDY_INDEX_BUILD_ENABLED=false` sits beside `CATALOG_REFRESH_ENABLED`
  on that container, and a store that does not cover every study raises
  `EdaStudyIndexNotReadyError`, which `search_eda_studies` returns as guidance
  rather than starting a second encode beside the api's; concurrent encodes
  measured 1.170 s per text against 0.485 s alone. On the release side,
  `release_stalled_jobs` now also asks
  procrastinate for the jobs of a worker whose `last_heartbeat` is older than
  the new `worker_dead_heartbeat_seconds` (300 s, ge 60), so a killed worker
  loses its lock five to six minutes after it dies instead of at the hour-wide
  started-age timeout, and Stop calls the same release directly. The window is
  300 s and not 60 s because a live worker was measured 153 s behind its own
  heartbeat during a long frame, so
  [the starvation item](backlog/worker-heartbeat-starves-during-turn-and-ui-gate-goes-fatal.md)
  is the prerequisite for lowering it; the 30 s window in
  `platform/health.py` is a different question and keeps its number. A released
  turn, and a turn whose own driver raises, now write one `tool-output-error`
  per tool call they left open before the terminator; `PROTOCOL.md` 1.3.1
  states the rule and the client's conformance capture carries it.

* **EDA reached both surfaces, and the seven-batch plan is closed.** A
  researcher can open an EDA study from the thread and from a workbench-style
  tab, and the two edit one analysis: `services/eda/authoring.py` is the only
  writer, every mutation answers with the same `EdaAnalysisState`, and
  `data-eda.analysis-state`, `data-eda.subset-preview` and `data-eda.viz`
  carry it to chat while `GET|PATCH /api/v1/conversations/{id}/eda` carries
  it to the tab. Batch 7 grew the three chat renderers into real cards (the
  volcano and scatter on a canvas beside their readouts, chips from the
  backend's `filterSummaries`, every count against its unfiltered total, an
  "Open in EDA tab" affordance), added the right-rail EDA panel that marks
  unseen EDA activity, and proved the loop with three Playwright journeys
  (chat-only render, tab edit returning on the next state part, export to a
  step the strategy rail lists) plus a conformance spec that parses every
  e2e fixture through the generated schemas, the last of which caught a
  fixture point that omitted its nullable p-values on both the feature spec
  and the frozen journey. The verifier failed the first pass on a chip keyed
  by its text, an untested rail marker and an untested scatter guard; all
  three were pinned and re-probed. The frozen acceptance layer closed
  56 backend, 41 frontend and 3 journey tests without a single line changed
  by an implementer; the lead's edits to it were four constructor
  completions and the journey fixtures' wire shapes. Three repo-wide gates
  stay red on files outside the plan and are backlogged: weak assertions
  (99), Playwright index locators (16), and the dev server's Turbopack flag.
  The concept and architecture-fit documents now read as built, every batch
  document is accepted, and `execute-eda-integration-plan.md` left the
  backlog.

## 2026-08-27

* **A strategy with no spec now describes itself, and a "preserved" claim is
  computed.** Batches E1 to E3 of
  [the edit_strategy fix plan](../design/2026-08-27-edit-strategy-fix-plan.md)
  landed. `domain/strategy/spec_hydration.py::spec_from_ast` reconstructs an
  `OperationalSpec` from the persisted `StrategyAst` - one criterion per
  non-combine node, keyed on the step id, holding the node's bound parameters
  verbatim - and the pre-turn hook runs it whenever the checkpoint holds no
  spec and the session holds a strategy. Measured on the thread the plan
  names: its checkpoint carried `operational_spec = None` on entry and its row
  carried 15 nodes with 15 WDK step ids, so the run that asked the user to
  re-type their filters was mechanism (a), and E1 is the batch that closes it.
  FRAME can no longer report `spec_ready` over a draft with no bound criterion,
  and its workspace prints every bound value in wire form instead of a
  60-character label. `domain/strategy/spec_diff.py::diff_specs` compares the
  spec a turn started from against the one it produced; an undeclared drop and
  a "kept" criterion whose values moved are both a `ModelRetry`, and the ledger
  renders `kept N, changed N, added N, dropped N` from the same comparison.
  Recorded as [preserved is computed, never
  written](decisions/preserved-is-computed-never-written.md). The `E6`
  checkpoint flush is owed: `StrategyDomainState` gained `spec_before_turn`.

## 2026-08-28

* **The EDA tab is no longer a dead end, and one route builder owns the canvas
  path.** A binding read that answers 422 over an out-of-vocabulary stored
  filter now offers "Open a different study" beside Retry; it sends
  `{action: "unbind"}`, clears the cached binding and the store, and shows the
  picker, with the server's detail quoted verbatim. `lib/routes.ts` gained
  `strategyStepUrl` beside `strategyCanvasUrl`, and the six hand-built paths
  call them - one of the six carried no site id, so it pointed at a route that
  does not exist. The entity tree now skips a variable whose `hideFrom` names
  `everywhere` or `variableTree`, while a filter already in force on such a
  variable keeps its chip and can still be removed. The same sweep then closed
  the chat path: eleven thread literals now call `chatUrl`, eight root literals
  call `chatRoot`, four site-less entry points redirect through the new
  `PORTAL_SITE_ID`, and a grep for a hand-built conversation path outside
  `lib/routes.ts` returns nothing.

* **A completed EDA compute puts a volcano on the thread, and the study
  detail carries the site's display advice.** `run_eda_compute_impl` reads
  `volcano_view` at the default cut and emits `data-eda.viz` through the same
  writer, right after the analysis-state chunk that names the revision the
  plot belongs to, so `eda_viz_chunk` has a production caller and the chat
  card draws a real plot. `volcano_view` now keeps a row whose effect size
  reads and whose p-value does not: it has an x coordinate, so it is drawn,
  never retained, and carries a null `pValue` that both surfaces count; only a
  row with no readable effect size is dropped. On the recorded compute that is
  201 points tested, 67 retained and 201 placed, one of them with no p-value.
  `EdaVariableResponse` and `EdaVariableOut` now carry `hideFrom`, read from
  the upstream variable in `variable_out`, so the tab can hide what the site
  hides while the chat tools keep every variable filterable.

* **EDA batch 6 is closed: the tab exists.** `/{siteId}/conversation/{id}/eda`
  mounts `features/eda/EdaWorkbench` behind the same `ChatShell` yield the
  strategy canvas uses. A `StudyPicker` searches and binds; a bound analysis
  mounts three cells keyed by `analysisId` so a switch remounts them: the
  `SubsetCell` (entity tree built from the flat detail, one `/count` per
  entity, filter editor dispatching on the server's `filterType`, chips from
  the store's parsed filters, unparsed filters reported, bar or histogram
  sparkline by `dataShape` with a coverage line), the `ComputeCell`
  (differential expression config built from live metadata with `DESeq` or
  `limma` on the wire, submit-or-poll by the byte-identical `run-compute`
  body, seven job states named), and the `VizCell` (volcano thresholded
  client side with a test proving zero `/viz` calls on a threshold change,
  the selected-gene readout beside every chart, scatter from the same
  cloud, the other charts named unavailable, refetch keyed on the completed
  job). `ExportStepButton` gates on `canExportRows` and a complete job and
  presents two success states with exact copy: the export began the
  strategy, or it added a draft root that is not pushed, decided
  structurally from the returned strategy and linked through the new
  `strategyCanvasUrl`. Before the batch, three reconciliations landed so it
  coded against the wire and not a sketch: every EDA response field became
  required (above), an export on a thread with no strategy now begins it
  through the one `persisted_graph` loader that replaced three divergent
  copies (the strict one in `strategy_ops` was the 404), with the op
  algebra's `ApplyError` rendered as 422 where it was an unhandled 500, and
  the frozen e2e journey's fixtures were corrected to the generated shapes.
  The verifier failed the first pass on evidence: local cell state outlived
  an analysis switch (measured "Sample6 of 12" after the switch), a second
  compute never refreshed the volcano (0 `/viz` calls), a Retry was missing,
  six named states had no test, and three probes survived; every item was
  fixed and re-probed, 18 of 18 killed on the second pass. Lead rulings
  recorded as backlog: the tab must honor `hideFrom` once the route carries
  it; the read path's refusal of an out-of-vocabulary filter needs a way out
  of the error state; no production path emits `data-eda.viz`, which batch 7
  owns. Ladders: unit 3223, integration 644 with 78 skipped, acceptance 56
  of 56 and 31 of 31, frontend 2512 vitest with the EDA tree at 187, three
  Python packages format-clean, `batch67-parts` red as designed.

* **Every EDA response field is required, and the analysis state counts its
  own entities.** The defaults are gone from the five parts in
  `shared_py.stream_parts.eda` and from every response model in
  `transport/http/schemas/eda.py`; a field that can legitimately be absent is
  required-and-nullable (`revision`, `pValue`, `adjustedPValue`, `job`,
  `step`, the gene-entity keys), and the request models keep the inputs a
  client may omit. `openapi.json` lists all thirteen `EdaAnalysisState` keys,
  the generated types and zod schemas carry no optional marker, and the store
  and the three card renderers read the fields with no `??`.
  `services/eda/authoring.py::subset_entity_counts` walks the study in tree
  order and fills `entityCounts`, which the only producer left empty; the
  whole size of an entity is cached beside its study detail
  (`catalog.py::unfiltered_entity_count`), so a mutation costs one count per
  entity and not two. `analysis_state` became async to own that read, so the
  subset predicates now run on the read path as well: an analysis edited
  elsewhere into an out-of-vocabulary value is refused by name rather than
  reported as a subset of zero, which is what upstream would answer. This
  closes the backlog item the batch-5 verifier raised.

* **EDA batch 5 is closed: the charts and the store exist, and the wire
  feeds both.** `lib/components/charts` is one ECharts 6.1.0 registry
  (`echartsRegistry.ts` holds the only value imports; everything else is
  `import type`), a ref-callback `EChart` wrapper that inits once, re-applies
  options and disposes in its own teardown, and pure option builders for the
  volcano (three series plus threshold guides, null p-values dropped and
  counted), the histogram and bar (label union, zero fill, real overlay), and
  the scatter (finite pairs only), each pinned to exact option arrays and
  tooltip strings. `lib/eda/volcanoSelection.ts` is the one selection rule
  (effect inclusive, significance strict, up before down) and the acceptance
  suite sweeps it with properties. `state/eda.ts` is `useEdaStore`, whose
  `supersedes()` is the overview's reconcile rule verbatim (analysis switch
  wins and clears, null revision on either side takes the last write, `>=`
  accepts), filters parsed per entry with the generated `edaFilterSchema`
  and failures counted. `lib/api/eda.ts` wraps the six routes and the GET
  through `requestJson` with generated schemas only; the three batch-4
  renderers hydrate the store in render with no effect. Two reconciliations
  landed inside the batch: `GET /conversations/{id}/eda` now carries the same
  `analysis: EdaAnalysisState | null` the part and the PATCH carry, built by
  one `read_analysis_state` that does not bump the revision (its seven flat
  fields deleted, `descriptor` made required-nullable), and the regenerated
  `conversationEdaResponseSchema` was adopted by the transport tests in the
  same window. The verifier ran twenty mutation probes and killed twenty,
  accepted eight implementer deviations on evidence (a namespace import of
  `echarts/core` because a named `use` trips the hooks lint; generated
  names over the card's), and left three notes the lead resolved: the
  palette backlog understated `--chart-3` (it fails the band, the entry now
  says so), the transport acceptance and the card spelled the compute
  payload `{appName, config}` where the wire says `{type, configuration}`
  (both corrected, the lead's one acceptance edit this batch), and the
  generated `EdaAnalysisState` marks nine always-filled fields optional
  because the Python model defaults them, which is now a backlog decision
  and a batch-6 wire truth (read the analysis through the store, never with
  `??` off a payload). Ladders: unit 3193, integration 640 with 78 skipped,
  acceptance 56 of 56, frontend 2340 vitest with batch-5 store, selection
  and transport at 31 of 31 and `batch67-parts` red as designed, four frozen
  trees byte-identical to the baseline.

* **EDA batch 4 is closed: the tab has its API and its types.**
  `transport/http/routers/eda.py` serves the seven pinned operations under
  the real `require_registered_wdk_identity` gate: study search and detail
  (one `describe_study` builder shared with the chat tool), count and
  distribution refusing an out-of-vocabulary value with 422 before any wire
  call, the thresholded volcano view, and `GET|PATCH
  /conversations/{id}/eda` with a five-way `action` union whose handlers
  call the same service bodies the agent tools call (`bind_analysis`,
  `apply_filters`, `submit_compute`, `export_analysis_step` were extracted
  into `services/eda/` so the tab and the tools cannot drift), every
  mutation bumping the thread's revision, and a `{analysis, job, step}`
  envelope with `analysis` required-and-nullable. On the TypeScript side
  one `yarn generate:types` carries the three `data-eda.*` part payloads,
  the six route schemas and, after `EdaFilter` became a PEP 695 `type`
  alias so Pydantic names it, the seven-variant `edaFilterSchema` the
  frozen store suite imports; the three text-only renderers keep the
  data-part map total. Ring 2 rejected once on evidence, and it was the
  batch's most important catch: the router shipped with a weaker
  session-presence gate because the implementer's test fixtures had not
  requested the harness's identity override that every other WDK-backed
  route test uses, so production was widened to fit a fixture omission on
  a security boundary; the verifier proved the real gate passes 10/10 and
  32/32 under the override, the gate was restored, the session gate and
  its tables deleted, and the decision doc's inaccurate paragraph
  reverted. The lead's one acceptance edit for the batch was that same
  fixture on the frozen suite. Two semantics the verifier traced are
  recorded for batch 6 rather than hidden: an export beside an existing
  strategy is a detached, never-pushed second root, and an export on a
  thread with no strategy is a 404. Ladders: unit 3191, http+eda
  integration 251, acceptance 56 of 56 (batch 4 at 10/10 under the real
  gate), frontend 2229 vitest with the acceptance config still all-skipped,
  the protocol package unchanged across three regenerations.

* **EDA batch 3 is closed: the conversational seam works end to end.** A
  researcher's thread can now search studies, open an analysis, set filters
  through a validated sheet, preview the subset, run differential expression
  as a durable background compute, and export the result as an ordinary
  step. The pieces: three `data-eda.*` stream parts in `shared_py` composed
  into the product's registration beside the strategy parts; seven Lead
  tools (`ai/tools/standalone/eda_*.py`, `ai/tools/toolsets/eda.py`) with
  `set_eda_filters` copying the `set_criterion` sheet pattern and every
  mutation bumping a per-thread revision counter on the new
  `conversation_analyses` row (migration `2026_08_28_0002`); the
  `services/eda/binding.py` hub; `create_eda_step` bridging into
  `apply_operations_and_commit` with the spec serialized once through
  `services/eda/export.py`; and `run_eda_compute` as a `@durable_tool`
  whose worker impl (`jobs/impls/eda_compute_impl.py`) drives the compute
  to `complete` before any step exists, so the WDK bridge's HTTP 202 is
  never surfaced. `durable_tool` was generalized to a two-member
  `DurableIdentity` Protocol so the Lead can call it. The proof is Verifier
  2's in-tree scripted conversation (`tests/integration/eda/test_eda_conversation.py`)
  through the real chat endpoint, worker, graph and event writer, asserting
  persisted chunk kinds and values (revisions 1 then 2, counts 4011 of 4279,
  a graph snapshot with a `GenesByEdaSubset` node), plus a live lane that
  pushed WDK strategy 330555673 whose EDA-backed step counted 5556 genes.
  Ring 2 rejected on evidence six times and each was closed by a named
  test: an unpinned longitude filter type, a vacuous hideFrom test whose
  fixture held no hidden variable, a non-atomic-increment mutant that
  returned 1 for all 20 concurrent calls, a significance-only threshold
  that escaped as a raw ValueError, a card-prescribed `import as`, and a
  duplicate view model. One verifier premise was refuted by the implementer
  with evidence (pydantic-ai dumps tool returns by alias, so the camelCase
  docstrings were right) and turned into a guard test. Docker crashed
  mid-batch from host-disk exhaustion (36 GB pruned; the killed implementer
  was resumed from an inventory of its tree). Recorded for later: the
  pre-existing resume-replay duplicate now measurably double-applies an EDA
  compute; the generic and per-dataset subset searches counted 5556 against
  5602 for one filter; the chat SSE test helper splits on U+2028. Full
  ladders green: unit 3177, serialized integration 594 passed 78 skipped,
  acceptance 46 of 47 (batch 4 pending), runtime package 354 with zero EDA
  names.

* **The plasmodb live lanes from EDA batches 1 and 2 have now run.**
  plasmodb.org returned after a day-long outage on their side, and every
  deferred live assertion passed on the first credentialed run: the client
  lane against the recorded catalog and counts (4011 of 4279), the compute
  lane reproducing the measured 5511 rows to 1543 retained (529 up, 1014
  down) at 1.0/0.05, and the search census (68 spec-carrying searches, 13
  named Eda, exactly 1 inert). One drift check failed for a true reason and
  was narrowed: a `user_submitted` study the veupathdb.org portal lists is
  invisible on plasmodb.org, because user uploads are visible per project
  and per account, so the recorded-is-a-subset-of-live assertion now
  compares curated studies only. Both batches' open items are closed.

* **EDA batch 2 is closed: the services exist.** `services/eda/catalog.py`
  resolves a dataset to its study through `/permissions` only (never derived
  from the id) and caches each study's detail under `study_cache_key`, the
  content hash for a curated study and `lastModified` for a user study, so
  a reloaded study re-fetches; `integrations/embeddings/study_index.py`
  ranks studies with the same fastembed index the WDK catalog uses, its
  three cache helpers now shared rather than copied, and never resolves.
  `services/eda/authoring.py` owns the analysis document: `serialize_spec`
  is the one `model_dump_json` site (an empty analysis serializes to the
  empty string, never `{}`; a frozen allowlist test fails on any second
  dump across six source trees), `EdaStepRequest` refuses a spec whose
  `studyId` differs from `eda_dataset_id` (both dataset ids), and
  `verified_count`/`apply_filters` run the domain predicates before any
  wire call because upstream answers an out-of-vocabulary value with 200
  and count 0. `services/eda/compute.py` submits with the STUDY id, polls
  the six-state job, and `retained_summary` applies the WDK bridge's exact
  volcano rule (a verifier replayed the recorded statistics by hand: 67
  retained of 201, 33 up and 34 down). `services/catalog/eda_backed.py`
  detects an EDA-backed search by parameter presence, never by name, and
  guards the `EDAUD_` upload sentinel so an empty-state vocabulary term is
  never offered as a choice. The frozen batch-2 acceptance module passes
  19/19 unmodified. The lead made its one allowed acceptance edit: the
  suite and the plan had constructed `WDKVocabTerm` with keyword arguments,
  but the model is the WDK wire triple, and an implementer's attempt to
  widen the production model to fit the test was rejected and reverted.
  Two verifier FAILs were closed on evidence (a sentinel word boundary and
  a guidance wiring path each survived a mutation until a test was added),
  a root fix typed `WDKSearch.dynamic_attributes` as `list[WDKAttributeField]`
  in place of a pre-existing `hasattr` probe, and the catalog integration
  file went from 47.75 s to 8.9 s by sharing one embedding cache across its
  tests. Open, not blocking: the live 5511-to-1543 assertion and the live
  search census have still not run because plasmodb.org is unreachable.

* **EDA batch 1 is closed: the integration foundation exists.**
  `integrations/eda/` now holds the hand-written Pydantic mirror of the EDA
  wire (`models.py`: the six-member variable union, the seven-member filter
  union that refuses `stringPrefixSet`, the analysis document with
  `derivedVariables` as ids, the six-state job, volcano rows that tolerate a
  missing p-value), eleven live-recorded fixtures with a value-pinning
  validation sweep, the typed httpx client (`client.py`, `analyses.py`,
  `errors.py`, `factory.py`; Accept exactly `application/json`, the STUDY id
  on computes, 400/403/422/500 mapped to typed errors, a missing registered
  token refused before the wire) hanging off `SiteInfo.eda_base_url`
  (`{site_origin}/eda`, no new setting), and `domain/eda.py`, the pure
  predicates over structural Protocols (filters against a study tree, the
  one-`VEUPATHDB_GENE_ID` rule, the differential-expression config) with an
  A-to-C cross-check proving the wire models satisfy them under pyright.
  Three Opus implementers, two Fable verifiers, then the lead. The protocol
  earned its keep on the first batch: Verifier 2 failed the predicates on
  evidence (two surviving mutations, six `match` arms statically dead to
  pyright because payload Protocols did not extend the base, an untested
  longitude epsilon) and the reopen surfaced a real behavior gap, a
  `category` variable accepted as a comparator; Verifier 1's twelve probes
  all died bar one killed only by the frozen acceptance suite, which is the
  suite doing its job. Open, not blocking: the credentialed plasmodb live
  lane has never run because plasmodb.org has been unreachable all day (its
  four pinned values were confirmed against veupathdb.org, the same
  deployment); re-run it when the host returns.

* **An edit turn is a delta over the strategy that exists, and a rebuild over
  one is refused.** Batches E4 to E6 of
  [the edit_strategy fix plan](../design/2026-08-27-edit-strategy-fix-plan.md)
  landed, and `edit_strategy` stopped being a classification nothing reads.
  `domain/strategy/spec_to_operations.py::operations_for` turns the computed
  `SpecDiff` into `GraphOperation`s over the live graph and hands them to the
  commit pipeline that already existed, so an untouched step is not rewritten.
  A build now re-keys the spec on the step ids it minted, which is what lets a
  criterion address a step at all; a thread that never framed gets the same
  invariant from the hydration. `build_strategy` refuses a thread whose graph
  has steps.

  Measured on PlasmoDB, one turn at a time through the debugger with the LLM
  mocked and WDK real. Turn 1 built strategy 330555313: `GenesByText` on
  P. falciparum 3D7 as WDK step 440180863 (129), `GenesByTaxon` on the same
  organism as 440180873 (5720), the UNION as 440180883. Turn 2 asked to swap
  the taxon criterion to P. vivax P01 and keep the rest. After it, WDK reports
  the same three step ids, `440180863` still carrying
  `text_search_organism: ["Plasmodium falciparum 3D7"]` at 129, and `440180873`
  carrying `organism: ["Plasmodium vivax P01"]` at 6861. No step was created and
  none was deleted. The ledger's diff read `kept 1, changed 1, added 0,
  dropped 0`, and the reply's preservation sentence is written from it.

  The same run found the debugger coupling two unrelated things: `--mock` set
  the mock provider AND skipped the WDK login, so a mocked run could not push a
  step and the proof had nothing to preserve. Only the LLM is mocked now; the
  login runs whenever credentials are present.

  Recorded as [an edit is a delta, not a
  rebuild](decisions/an-edit-is-a-delta-not-a-rebuild.md) and [a criterion and
  its step are one address](decisions/a-criterion-and-its-step-are-one-address.md).
  [build_strategy is not
  revision-guarded](decisions/build-strategy-is-not-revision-guarded.md) is
  amended: the exposure it accepted is closed, because the tool it applied to
  no longer runs on a strategy that exists. The checkpoint flush E3 owed shipped
  as `2026_08_28_0001`.

  Three backlog items left: the edit turn that dropped a criterion and said the
  rest was preserved, the one that rebuilt every step and reverted a hand edit,
  and the hydrated spec that made a whole strategy rebuildable with new step
  ids. A fourth left by accident: a formatter run over `src/pathfinder/tests/`
  reformatted the three EDA acceptance files ladder P's format rung was red on,
  which is the fix that item prescribed but not on its own, as it asked. Three
  arrived: the Lead has no tool to throw a strategy away now that
  `build_strategy` refuses one, the eval corpus cannot express a two-turn edit
  case, and the file-size gate is red on six modules rather than the two the
  item named.

* **The EDA plan gained a frozen acceptance layer, and it is already written.**
  [The overview](eda/plan/overview.md) now defines the protocol: a
  behavior-only conformance suite written before any implementation by QA
  agents who implement nothing, pinning live-verified VALUES at stable
  boundaries, pending until each batch closes (backend: `eda_acceptance`
  marker deselected from the default `addopts` plus `importorskip`; frontend:
  `*.acceptance.ts` files outside the default vitest include with a dedicated
  config; e2e: an env-gated playwright project), under a no-edit rule -
  implementers never touch the acceptance paths, a wrong test escalates to
  the session lead - and a new universal exit criterion: a batch closes only
  when its acceptance module passes unmodified. Verifiers additionally run
  mutation probes: flip two or three behavior-bearing lines and confirm the
  implementer's tests die. The suites exist and are pending-clean today:
  56 backend tests across four batch modules
  (`apps/api/src/pathfinder/tests/acceptance/eda/`, 4 modules skipped
  cleanly, every default gate green) and 41 frontend tests plus 3 e2e
  journeys (`apps/web/src/acceptance/eda/`, `apps/web/e2e/acceptance/`,
  default vitest and playwright collect zero of them). The QA pass also
  hardened the batch documents: the repository gained its named `increment`
  method, the 401 mapping and `install_transport` became pinned interface,
  unbind became explicitly idempotent, the count-route seam contradiction
  was resolved onto `verified_count`, `analysis` in the PATCH envelope is
  required-and-nullable, the volcano `selected` ordering is up-then-down,
  and batch 7's e2e snippets now use the rail's real accessible names.

* **The EDA integration has a verified implementation plan.** [eda/plan/](eda/plan/)
  holds an [overview](eda/plan/overview.md) - the layering, the co-edited-SSOT
  design (one analysis per thread, agent tools and tab clicks patching the
  same upstream document, both surfaces re-rendering from
  `data-eda.analysis-state` snapshots with a per-binding revision counter),
  the pinned shared contract, and the three-ring verification protocol - plus
  seven batch documents with per-implementer TDD task cards (17 implementers,
  10 verifiers, lead-closed batches). Drafted by two agents, then reconciled
  by the lead: the `PATCH /conversations/{id}/eda` route became a five-action
  union (`bind`, `set-filters`, `run-compute` as idempotent submit-or-poll,
  `export-step`, `unbind`) whose handlers call the same service bodies the
  agent tools call; the part payloads were settled on batch 3's models and
  every frontend fixture realigned; `VolcanoThresholds` gained its one
  definition; the duplicate distribution response collapsed onto the part's
  shape; and a boxplot chart with no data source and no consumer left the
  contract. Decisions taken with the user: both seams in one plan, ECharts
  for the statistical charts (canvas for the 5.5k-point volcano; networks
  stay on ReactFlow), co-edited state over read-only viewing. Execution is
  the one backlog initiative, which left the backlog when batch 7 closed.

## 2026-08-27

* **The availability cluster is closed: what a process holds is bounded, the
  server binds before the warm-up finishes, and an abandoned MCP call stops
  with its caller.** Three measured defects had one shared cause. Twelve of the
  fourteen catalog snapshots the image ships were 84.8 days old, and nothing
  persisted a refreshed one: every process start restored fourteen stale
  snapshots, spawned fourteen background refreshes at once, and each refetched
  a site and re-encoded its index - which is where the worker's 5.26 GiB, the
  api's hour-plus cold start and the `wdk-mcp` kill on a stale-cache site all
  came from. `catalogs_cache` now mounts over `apps/api/src/data/catalogs` in
  all three services, beside the `embeddings_cache` volume that already held
  the encoded rows, so a refresh is paid once and not once per recreate; a
  process-wide semaphore admits one `_fetch_from_api` at a time and a
  `KeyedLock` one build per site, so the peak is one build and not fourteen;
  `CATALOG_REFRESH_ENABLED` is `false` on `worker` and on `wdk-mcp`, because a
  build of one site was measured at 2.977 GiB and neither 2 GiB container
  survives it, and a sweep inside `wdk-mcp` restores a fresh-snapshot site in
  0.3 s for about 10 MiB; and `DiscoveryService` holds its catalogs in a
  `cachetools.LRUCache` over
  `SITE_CATALOG_BUDGET_MB` accounted megabytes (512 by default), so the held
  set is bounded by policy rather than by a kill. The accounting is measured,
  not guessed: a 7.9 MB plasmodb snapshot restores in 0.4 s with nothing
  encoded and costs 27.6 to 29.9 MiB resident, so a catalog is charged
  `1 MiB + 4 * payload + index.nbytes`. The lifespan now spawns
  `_warm_up_subsystems` instead of awaiting it and the model loads inside it
  run on a thread, so uvicorn binds while the catalogs load behind it: measured
  against the 73 minutes the item recorded, a recreate bound 43 s after
  container start and all fourteen catalogs preloaded in 5 s with nothing
  encoded, and the api settled at 2.21 GiB against the 5.66 to 8.83 GiB read
  off the same container before. The container healthcheck is `/health`,
  because a compose dependent needs a server that answers and a catalog loads
  on demand. `/health/ready` still reports per-subsystem and per-site progress for
  the UI's startup gate. On the MCP side a stateless streamable-HTTP call runs
  in the session manager's own task group, so an abandoned call is cancelled by
  nothing and the tool has to ask: `rank_public_strategies_semantic` embeds 64
  strategies per call and scores each batch as it arrives, and
  `search_example_plans` passes an embedding function that refuses once
  `Request.is_disconnected()` is true, holding that site's lock for the whole
  call so a second caller queues. Measured against the served endpoint: three
  calls abandoned at a five second budget all stopped about seven seconds after
  their clients left, the container kept `RestartCount` 0 at 1.089 GiB, the
  next call answered 200, and a patient client got its ranking in 46.2 s.
  `_encode` in the semantic index batches the same way, and the model now takes
  one document per batch: fastembed pads a batch to its longest text, and
  encoding 64 toxodb descriptions cost 166.5 s and 886 MiB at `batch_size=8`
  against 128.9 s and 186 MiB at `batch_size=1`. The eight-site sweep the
  kernel killed on its third site now finishes at 1375.8 MiB. Family 5 of the
  admission record names `search_example_plans` as the slow tool with a five
  second budget and settles all four of its checks, so three entries leave
  `UNSETTLED_CHECKS`. Recorded as
  [per-site catalogs are evicted under a budget, and the warm-up does not block
  the bind](decisions/per-site-catalogs-are-evicted-and-the-warm-up-does-not-block-the-bind.md),
  which names what was rejected: one process holding every index and serving
  the rest over MCP, parallel per-site encoding, a rebuild inside a capped
  container, `/health/ready` as the container healthcheck, and a budget sized
  from process RSS. One finding did not fit the fix and is now its own item:
  thirteen of the fourteen shipped `.npz` caches carry the retired
  `embeddings`-plus-`hash` shape that `_load_cached_rows` skips, so 7184 of the
  7699 shipped catalog entries have no usable row and a fresh deployment
  encodes them all before readiness closes.

* **The EDA bundle grew from orientation to a full specification.** Four
  parallel research passes deepened [EDA](eda/) from 4 documents to 13, every
  claim verified against commit-pinned upstream source or live calls on three
  deployments, then re-verified by a second pass. New:
  [data model](eda/data-model.md) (66664 variables scanned; the single-entity
  GET is lossy; `isCategory` never on the wire),
  [subsetting semantics](eda/subsetting-and-tabular.md) (cross-entity
  propagation proven in both directions and across sibling subtrees;
  root-vocab is not subset-sensitive; a 20-row preview tier),
  [filter algebra](eda/filters.md) (all 7 deployed types with exact error
  classes; out-of-vocabulary values return 200 count 0),
  [derived variables and merging](eda/derived-variables-and-merging.md)
  (12 plugins, 10 proven live; `relativeObservationMinTimeInterval` is dead
  upstream; `resultsAll` gates merge output with 403),
  [computes and jobs](eda/computes-and-jobs.md) (job id is a client-derivable
  MD5 shared across users; a real DESeq run observed queued to complete),
  [visualizations](eda/visualizations.md) (volcano thresholds are
  client-side, network thresholds server-side),
  [notebook presets](eda/notebook-presets.md) (the compute bridge is
  volcano-only by construction; the delayed answer is HTTP 202
  WDK-DELAYED-RESULT and the WDK call auto-starts the job; WGCNA exports
  genes through plain SQL, not EDA),
  [genomics and WDK relations](eda/genomics-and-wdk-relations.md) (four
  relations, not one; per-dataset searches derive from
  SHA-1(datasetName)[:10]; the EDAUD_ sentinel vocabulary term 400s), and
  [architecture fit](eda/pathfinder-architecture-fit.md) (layer placement,
  the durable-tool mapping named mechanism by mechanism, EDA as a second
  admitted MCP source, hand-written Pydantic mirrors with pinned wire
  samples). The four baseline documents were corrected where the deeper pass
  falsified them, most notably: `differentialexpression` takes
  identifier+value variables, not a collection; the per-dataset searches use
  `GenesByEdaSubsetGeneric`; user studies have an empty `sha1hash`.

* **A one-agent assistant reads the thread it is having.** `single_agent_graph`
  built every run from `state.user_prompt` alone and passed no history unless
  the turn answered an approval, so a site-help thread answered "Yes, please
  proceed." with "What would you like me to proceed with?". The turn state now
  carries the thread's own pydantic-ai messages as JSON, written from the run's
  result and trimmed to the last complete exchange, and the graph reads them
  back as the run's `message_history`
  ([a one-agent turn runs over the thread's own messages](decisions/the-thread-carries-its-own-messages-across-turns.md)).
  The trim is what keeps a parked approval out of the carried history:
  pydantic-ai refuses a new prompt over a history holding an unprocessed call,
  and the card keeps its own resume history regardless. Rebuilding the messages
  from the durable chunk log was rejected, because the wire carries chunks
  rather than the call-to-result pairing a provider needs; a runtime window or
  summarizer was rejected too, since no thread has yet measured too expensive
  and pydantic-ai already puts that bound on the agent. The runtime's scripted
  test model gained `current_turn`, so a script that asks what THIS turn did
  stops reading the turns before it.

## 2026-08-25

* **A regenerated turn no longer wedges its conversation, and a thread that
  cannot render no longer takes the page with it.** The dispatcher wrote the
  user's envelope on every turn, so a regenerate - which sends the thread back
  ending at the same user message - put that id in the log twice, and
  assistant-ui refused to build a thread that names one message twice. It now
  appends through `append_user_message_once`, which reads the log first and
  writes nothing when the id is already there, and the id decides rather than
  the client's `trigger`, as section 12.3 requires
  ([one id names one message in the log](decisions/one-id-names-one-message-in-the-log.md)).
  Four conversations on the dev database already held a repeat, so
  `reduceSnapshot` keeps the first message an id names and drops a later one:
  the reported conversation's 1,624-chunk log rebuilds as three messages, one
  question and both answers, with no repeated id. A unique index and a repair
  pass were both rejected, because neither can be applied to a log that already
  repeats an id without editing what was said. `ChatView` also wraps its body
  in an error boundary, so any thread that throws renders the error and a
  site-scoped way back to the conversation list instead of an application-error
  page.

* **MCP program batch G: an assistant that is not PathFinder answers with tools
  served over the network, and the program is reconciled.** `site_help`
  declares one source - two catalog reads and one control-test measurement from
  `veupathdb-wdk-mcp`, `required=False`, so a deployment that admits no such
  server still serves the assistant - and reaches it through its own typed
  per-turn channel rather than a widened runtime factory, because the graph is
  compiled before the turn's sources resolve
  ([a declared source reaches a one-agent assistant through its deps](decisions/a-declared-source-reaches-a-one-agent-assistant-through-its-deps.md)).
  A site-help turn driven through the worker answered from a tool the wdk-mcp
  container served over the compose network, and the source's one writing tool
  parks a card that the next request's answer runs - which is the program's
  whole claim: an assistant declares a source and the runtime does the rest.
  Two runtime defects are backlog items, neither in the source path:
  `single_agent_graph` builds every run from `state.user_prompt` alone, so a
  one-agent assistant forgets the previous turn; and a resumed approval turn
  emits `tool-input-available` with no `tool-input-start`, which the strict
  client tolerates and PROTOCOL 6.2 does not describe. A third finding - a
  suite-order red blamed on the runtime - was disproven by the review: the
  test double's in-process uvicorn installed process signal handlers that
  latch sse_starlette's process-global shutdown flag; the double no longer
  captures signals, and the ladder is order-independent again.

  The closing sweep found the bundle already honest: the six items the program
  touched are deleted or edited to their residual, the backlog index and its
  directory agree file for file, and every decision the program recorded is
  indexed. The three dated documents that outlived their claims are annotated,
  not rewritten. The execution plan's status line reads executed and points
  here; the design document's section 8 and appendix B carry dated notes, since
  four of appendix B's seven findings have closed and one of them closed before
  the program began; and the platform assessment's addendum carries the WS4
  entry with the two corrections its own debts paragraph needed - a failed turn
  is visible after a reload, and the max-lines gate is red on two modules
  rather than five.

* **MCP program batches E and F: the suite a foreign team can run, and the
  packages publish alone.** `packages/mcp-conformance` ships 32 checks in six
  families as a pytest plugin that never imports pathfinder or
  assistant_core, proven by fifteen planted defects that each name their
  exact failing checks; run against our own served endpoint it answers
  `incomplete` honestly - 26 passed, none failed, six unsettled checks
  pinned by name - and its first real run surfaced three defects
  (an ortholog vocabulary shape the domain model refuses, an abandoned slow
  call that outlives its client and OOM-kills the server, the file-size gate
  red at HEAD), each now a measured backlog item. Nightly, CI and pre-commit
  lanes carry it. On the packaging side, assistant-core shed its last
  product dependency and installs into a clean venv with pathfinder absent;
  the client builds a dist whose tarball proves the three rings (core and
  legacy import with zero dependencies, the ai-sdk ring requires `ai` and
  only `ai`); `data-turn-failed` joined the protocol at 1.3.0 so a reloaded
  thread finally says the turn died, deduplicated against the live error
  card; and the task card left the per-task SSE dialect - the thread carries
  the whole lifecycle, the reattach fires at task start because a
  completion-fired design is provably impossible, and the fan-out lane
  collapse that removal exposed is a filed item, not a surprise. One review
  round each: the conformance dev-dependency had broken the api image build
  (three COPY lines), and one spec header still described the deleted
  subscription. Fable review: both accepted.

* **MCP program batch D: veupathdb-wdk-mcp is served.** Sixteen tools over
  streamable HTTP in a container of their own on the api image, binding in
  about three seconds because the entrypoint preloads nothing. Fourteen
  declare readOnly; the two writers declare non-destructive with per-tool
  `_meta` call budgets the live suite enforces by setting the client's
  read timeout from the served declaration - enrichment measured 508.9 s at
  the 200-gene cap against its declared 600, and the controls estimate held
  at under nine seconds against 180. Bearer auth chains the SDK's own
  middleware (the fastmcp shortcut silently drops the credential subclass,
  so the SDK path is pinned by a test that fails without the context
  middleware). Memory ceilings landed on the two growers (worker and
  wdk-mcp at 2 GiB, the api uncapped by measurement); sizing them
  reproduced the api OOM incident on purpose, and the live proof then
  showed a cold-site catalog read killing the served container at
  3.269 GiB - the eviction half stays in the backlog for batch F. The
  isolation case ran against a real foreign-owned public strategy and
  leaked neither the step nor its count. One review round: the server
  advertised fastmcp's version as its own; it now declares the
  deployment's, pinned at build and on the wire. Fable review: accepted.

* **MCP program batches B and C: the tool protocol lives in the runtime, and
  the sixteen tools' service seam exists.** `assistant_core/mcp/` now holds
  declarations, admission, the deny-by-default approval predicate, the
  untrusted-output wrapper with real jsonschema payload validation, the fixed
  wrapping order, and per-turn resolution: a declared source is built,
  credentialed at the transport and nowhere else, opened with the turn and
  closed with it, proven against an in-process FastMCP server with the
  design's P1 exit criteria each named in a test. The turn runner enters the
  resolution around the drive; a spec that declares nothing constructs
  nothing. The three sub-agents left their module singletons for
  per-dispatch factories. On the service side, the four gated catalog tools
  split into pure retrieval halves under `services/catalog/` with
  byte-identical wrapper behaviour pinned, `pathfinder/mcp/` gained bearer
  auth that reuses the api's verifier by identity plus the RFC 9728 document
  from the SDK's own helpers, and `enrich_gene_ids` runs enrichment by value
  through the same WDK plugin machinery with the wire field names pinned
  three ways. Fable review: both batches accepted with zero defects; the
  next batch inherits two measured corrections (the api venv lacks the
  fastmcp server extra, and the enrichment tool cannot fit the default
  60 s call budget).

## 2026-08-24

* **MCP program batch A: the trust base.** Three changes an external consumer
  of the runtime depends on, executed from the plan in
  `docs/design/2026-08-24-mcp-sdk-execution-plan.md`.

  **Every named tool is callable.** The gene chain VERIFY's instructions
  order (`literature_search`, `lookup_gene_records`,
  `resolve_gene_ids_to_records`) is registered on its toolset, the two
  catalog tools joined FRAME, and `update_search_decision` is deleted with
  its module. An agreement suite now walks every agent's instructions and
  the extractor registry and asserts each named tool is callable by that
  agent - it caught a fourth instance on EXECUTION and seven extractor
  orphans on the way, and the orphaned `SearchOverview` selection fields it
  exposed are a backlog item.

  **The deferred-tool cycle exists once.** The Lead's duplicated approval
  code folded onto `assistant_core.graph.approvals`: `parked_call` is the
  one construction of the shared fields, the Lead adds its product fields by
  `model_copy(update=...)`, and its thirty approval tests pass unchanged.
  The two resume helpers this file's earlier entry placed in `_lead_turn.py`
  now live in the runtime; the Lead keeps sub-agent re-entry, the
  dispatch-answer fan-out and `is_pure_approval` only.

  **The checkpoint allowlist is real.** It never was: with strict msgpack
  off, `with_msgpack_allowlist` returns the serializer unchanged, so every
  declared type was discarded and both hypotheses in the backlog item were
  wrong (the item leaves with the correction that `astream` warned
  identically). The serde now binds the allowlist at construction
  (decision recorded), `CombineOp` completes the PathFinder list, and an
  integration test reads a real thread under the library's serde-event
  listener and asserts zero unregistered-type events. Found on the way and
  filed: the api and package lockfiles resolve `langgraph-checkpoint` to
  4.0.1 and 4.2.0 under identical pins, and two api integration tests fail
  under machine load only.

* **Every tool an instruction or an extractor names is callable by the agent
  that reads it.** VERIFY told the model to resolve control gene IDs through
  `literature_search` then `lookup_gene_records` then
  `resolve_gene_ids_to_records`, and its toolset held none of the three, so a
  controls-needing verification spent a model turn on a tool that did not
  exist; all three are registered now. FRAME registers
  `browse_search_categories` and `list_transforms`, which the context extractor
  already claimed observations from. `update_search_decision` and its module
  are gone, superseded by the `set_criterion` flow, and the outage-rejection
  detector that was its only reader goes with them. A new agreement test walks
  each agent's instruction text and the extractor registry against the tools
  its toolsets register; it found a fourth case nobody had reported, EXECUTION
  naming `get_estimated_size` and `get_sample_records` under "Read-only
  inspection" while registering neither. The backlog item leaves with the fix;
  a new one records the six selection fields on `SearchOverview` that the
  deleted tool was the only writer for.

* **A rehydrated thread can keep talking: the request parses the protocol's
  own reduction output.** The snapshot reduction attaches `errors`, `aborted`
  and `finishReason` to an assistant message, and a live stream records
  `resultProviderMetadata` on an output-error tool part; pydantic-ai's strict
  message union refused both on resend, so any conversation whose history was
  rehydrated - a reload, a restore from dismissed, a branch - answered every
  later send with a 422 and the raw error list. `ChatRequestBody` now parses
  those members away in one before-validator, PROTOCOL.md 1.2.2 says a runtime
  MUST ignore them, and the restored-strategy e2e journey proves the turn end
  to end on a rebuilt stack. This closes the resend-brick investigation from
  the 2026-08-17 UI run; its backlog item leaves with it. `site_id` on the
  same body gained the String(50) bound the transport sweep gave every other
  request field.

* **The e2e mocks now speak the wire they test.** Five route-mocking specs
  sent `data:`-only SSE frames that section 3 of the protocol orders a client
  to reject, and parameter-sweep still spoke the pre-v6 `messages/partial`
  dialect against a dead per-task mock; all six now build their streams from
  one conformant fixture (`e2e/fixtures/sse.ts`) and pass. The "durable path
  never fires" scare dissolved with them: no e2e spec drives a real durable
  turn by design, and that coverage lives in the backend integration suites.
  What remains of the fourteen reds is worker contention on three feature
  specs that pass standalone, recorded with the adjudication in the residual
  item.

* **Every transport request string that lands in a bounded column is bounded.**
  One `SiteId` type now covers the five schemas the re-review flagged and the
  nine more a residual sweep found - body fields, write-path query params via
  `RequiredSiteIdQuery`, the auth routes' defaulted params - plus the gene-set
  and control-set name/searchName/recordType/source fields, each sized to its
  column, so an oversized value answers 422 at the edge instead of 500 at
  INSERT. Seventeen red-first cases pin the bounds; the spec and generated
  types carry them.

* **The stalled-turn releaser and the thread log survived their review.** The
  P2 verifier's findings, closed the same day: `_chat_stream_is_open` now
  reads only turn-tagged rows, so task progress written into the gap between
  turns neither reopens an ended turn nor hides a stalled one; `_ThreadLog`
  clears its pending update only when it wrote that update, so a concurrent
  scoped child's offer is no longer dropped while an append awaits the
  database; the first chat POST of a fresh test process paying the PIGuard
  model load against a 5 s enqueue ceiling is a backlog item with the
  measured runs.

## 2026-08-23

* **WS-V batch P1: the one-agent assistant can ask, and the loop guard finally
  runs.** Two mechanisms the runtime declared and never reached are now wired,
  each with the turn that proves it.

  **Approvals.** `single_agent_graph` admits `DeferredToolRequests` as a
  per-run output type, so a tool marked approval-required no longer reaches the
  user as "`DeferredToolRequests` is not among output types". The cycle lives
  in `assistant_core/graph/approvals.py` - park the call as a `PendingApproval`
  with the run's full history, rebuild `DeferredToolResults` from the user's
  answer, replay that history, and hand the emitter the hint that re-announces
  the call - and the graph runs it in about thirty lines. The phase a one-agent
  turn parks is `"agent"`, the name of the only node that can raise one; a
  one-agent assistant has one role and it is the graph's. A turn that answers
  nothing supersedes the card rather than re-running the call the user never
  approved. Nine package cases drive request, approve, deny, the parked state
  and the superseded card end to end, and three more do it over HTTP in
  `apps/api` with a site-help-shaped assistant whose one tool needs confirming,
  through the route, the worker and the resume. `site_help`'s own tools are
  read-only and stay silent.

  **The repetition guard.** `ToolRepetitionGuard.check` had no caller since
  batch C. It now runs from `RepetitionGuard`, an `AbstractCapability` the
  driver passes per run, on the guard the turn's deps carry - the same
  interception surface `ToolResilience` uses, chosen because the Lead's tools
  are registered with `tools=` and no toolset wrapper can see them. Both
  blocks return the refusal as the tool's ordinary result, never as a
  `ModelRetry` (a retry raised in the wrapper shares the tool's retry budget
  and can abort a run whose tool already retried); the first names the
  repetition so the model can route around it, the second sets
  `stopped_call_id` and the driver stops consuming the stream once that
  result has reached the client, so the turn ends with `finish`/`stop` and no
  dangling part. It is
  wired on the Lead, the three sub-agents and the single-agent graph, and the
  synthetic assistant grew a loop arc that asks for one reading five times: the
  third is refused, the fourth ends the turn, and the fifth is never made.

  Two things the wiring found. `graph_modifying_tools` was a constructor
  argument with no behaviour - both of `check`'s early branches reset the
  counter and return `None` - so it is gone and a tool outside the vocabulary
  is what clears a streak. And `READ_ONLY_TOOLS` named ten tools, nine of which
  no agent has carried since the FRAME/BUILD/VERIFY split; the guard would have
  watched `get_plan` and `search_catalog` forever. It now names the 26 real
  inspectors across the four agents, and a seam test fails when a watched name
  is not a tool some agent offers.

  `PROTOCOL.md` is **1.2.0**: section 6.2 states the approval cycle a turn
  really runs, the `error` example the reference assistant used to produce
  because of this defect is gone, and `tool-approval-request` is captured in
  its place. `@pathfinder/assistant-client` re-synced and its reducer already
  read both chunks; two conformance cases now say so. Devtools' loop diagnosis
  reports guard refusals, and one refusal is enough to name a loop, because the
  guard measured it rather than inferring it from a failure count.

  `lead_node.py` crossed the 400-line cap on the way, so model selection left
  it for `_lead_model.py` and the two approval-resume helpers joined the rest of
  the Lead's approval code in `_lead_turn.py`; the five known files are the only
  ones over the cap again.

  Verified: package `uv run pytest` 205 passed with no `pathfinder` installed,
  ruff, ruff-format, mypy --strict 54 files; `apps/api` ruff, mypy --strict 577
  files, pyright 0/0/0, import-linter 7 kept, 2626 unit tests, the integration
  suite; the client's 200 vitest cases; `openapi check` exit 0 and `yarn tsc`
  clean on the web app; knowledge gate 120 files.

* **The protocol grew a request side and stopped needing two readers.** PROTOCOL.md
  1.1.0 answers the two questions section 6.4 of the MCP/SDK design named as ours to
  close before an external client is written. The turn-start contract is section 12:
  the identity a request must prove, the `X-Requested-With` rule that applies to a
  cookie and not to a bearer, the body split into the nine fields any assistant on
  this runtime takes and the one this product adds, the approval answer that rides in
  the body instead of inventing a user message, the six refusals including the `409`
  a thread's fixed assistant produces, and the fact that the POST's response is a tail
  from the last turn terminator rather than a stream the turn depends on. Two request
  examples are on the page and a gate validates both through `ChatRequestBody`; a
  second gate asserts the two field tables together name every field the model
  accepts, so a field added without a row on the page fails.

  The durable-task half is its own subsection of section 6.
  `data-background-task-started` was already in the log; `data-task-progress` and
  `data-task-completed` are now written there too, untagged, so the chat stream
  carries them and a client that reads the thread learns the whole lifecycle with one
  reader and one cursor. Progress is coalesced - first
  update, every five-point advance, ten seconds of silence, and always the last one -
  because the alternative is on the order of 900 rows replayed on every read of a
  thread that once ran a sweep. The comparison is in whole percentage points, since
  `0.15 - 0.10` is `0.049999999999999996` and a fraction rule would skip the tick it
  names. The chunk carries the task id as its `id`, so however many are written the
  reduced message holds one part.

  The per-task endpoint keeps working byte for byte and is now written down rather
  than merely known: section 13 states its `event: stream` framing, its `custom`
  envelope, its missing cursor and the two payloads that differ from their logged
  counterparts, and an integration test pins its exact frames against that section.
  It is deprecated, `@pathfinder/assistant-client/legacy` says so, and the web app's
  migration is a backlog item rather than a break.

  All three gates were made to bite before they were trusted. Removing the
  `phaseReasoning` row from the document's core table failed the field-table test with
  "Extra items in the right set: 'phaseReasoning'"; adding one space inside the pinned
  legacy frame failed the golden test on that byte; renaming the changelog's newest
  row failed the new assistant-core test with `assert '1.2.0' in {'1.0.0', '1.1.0',
  '1.2.1'}`. All three were restored.

* **The published OpenAPI spec is the production contract, whatever the process environment.** `openapi check` answered 0 or 1 depending on who ran it: the generator built the app under the ambient profile, so a mock-profile shell put `/api/v1/dev/login` into `packages/spec/openapi.yaml` and a production shell then reported drift. `create_app` takes `include_dev_routes` (None follows settings; the generator passes False), the committed spec is regenerated without the dev route, and a unit test pins that a mock-profile environment still produces a spec with no `/api/v1/dev/` path.

* **WS-V batch 4: the eval system, and the consent that feeds it.** Consent is
  `users.eval_data_consent`, default on, with `eval_notice_seen_at` beside it so the
  one-screen notice is shown once per account rather than once per browser; both are
  read and written through `GET`/`PATCH /api/v1/me/privacy`. The notice renders over
  the app and is dismissible - Escape, the backdrop, **OK**, or the inline **Turn off**
  that opts out and records the notice in one call - and Settings gained a **Privacy**
  tab whose toggle disables and re-enables. Extraction is a daily `maintenance` task
  that reads finished threads of consenting users, strips email addresses and URL
  credentials, and writes `eval_staged_cases`; `EvalExtract` refuses to be constructed
  if either pattern survives, so an unredacted candidate cannot be queued. Curation is
  `pathfinder.devtools.evals`: `staged`, `show`, `promote`. A promoted case is a JSON
  file under `apps/api/src/pathfinder/evals/corpus/`, on the manifest-and-provenance
  shape the WDK fixture store introduced in batch 3. Every chunk in the extraction
  suites is built by the code that writes it to the log - `user_message_chunk`,
  `TextDeltaChunk`, `ledger_update_event` - so a renamed chunk kind fails the tests
  instead of quietly emptying the queue.

* **The linkage rule became a check constraint.** "Extraction severs user linkage" and
  "an opt-out clears the user's staged items" cannot both describe the same row, so the
  linkage was given a lifetime instead: a staged row names its user, its thread and its
  extract; promotion nulls all three and keeps the content hash, the corpus name, the
  site and the assistant. Any other combination is unwritable, and the foreign keys
  cascade, so deleting an account removes its staged rows with no code running while
  promoted cases are already out of reach. `DELETE /api/v1/user/data` reports
  `stagedEvalCases` beside its other counts. Recorded as
  [a staged eval case carries its user until promotion](decisions/a-staged-eval-case-carries-its-user-until-promotion.md).

* **The harness is pydantic-evals, and the promotion policy is written down.** The spike
  found `pydantic-evals` **2.22.0** already installed as a hard dependency of the pinned
  `pydantic-ai`, providing the dataset, the case loop, the evaluator protocol and the
  report; the run summary stays a local model so the SLI feed does not follow a library's
  dataclass. Four cases encoded from the cataloged UI-run failures ran **4/4 green in
  32.7 s** against the deterministic provider, and a case given a wrong
  expectation fails with its named difference rather than silently. One
  extraction pass over the development database read 50 threads and staged **6**
  candidates across four sites. `conventions/verification-gates.md` now
  carries the ruled policy: an eval starts as a tracked trend, becomes a hard gate only
  after it catches or would have caught a real regression and holds stable, and a flaking
  gate is demoted or deleted, never suppressed. Recorded as
  [the eval harness is pydantic-evals](decisions/the-eval-harness-is-pydantic-evals.md).

* **Two deviations and one finding.** Four cases rather than ten: the deterministic
  provider routes on keywords, so a case whose red comes from a test-double marker
  reports a regression that is not there. Exact structural match rather than NTED: the
  only tree-edit-distance implementation in the repo is in the retired thesis harness and
  depends on `zss`, `numpy` and `scipy`
  ([backlog](backlog/eval-scoring-is-exact-match-only.md)). And reading a thread through
  `graph.aget_state` prints eleven "Deserializing unregistered type" warnings, including
  for three types that are on the allowlist `assistant_core.conversation.serde` builds,
  where the same checkpoint read by `astream` prints none
  ([fixed](decisions/the-checkpoint-allowlist-binds-at-construction.md)).

## 2026-08-22

* **WS-V batch 3: the science verifies in two lanes, and the WDK rule bundle has one
  unenforced entry left.** Per-PR: 31 of the 32 untested rules became hermetic tests over a
  pinned fixture store, so `check-wdk-rules` reports **78 enforced, 4 partial, 1
  unenforced** where it reported 32 unenforced, and three `PARTIAL` entries closed with it
  ([WDK-STRAT-002](wdk/rules/strategies-and-steps.md), `-003` and
  [WDK-MAP-003](wdk/rules/pathfinder-mapping.md), all three by one test that runs the
  projection to its third function and asserts on the serialized `WDKStepTree`). Nightly:
  `pytest -m live_wdk` collects **139** tests, skips cleanly with no credential, deletes
  every strategy and step it creates, and writes a JSON summary of outcomes, per-site
  tallies and drift. The recording path is `pathfinder.devtools.wdk_fixtures`: a
  declarative manifest of 12 exchanges, provenance stored as data rather than as a comment,
  and one command - `yarn wdk:record` - that refreshes the store a confirmed drift
  invalidates. The gate now fails a rule whose status is `UNENFORCED` and whose block
  carries no `reason`, so the column cannot fill with silence again.

* **Four defects the rules found, each in the code the rule anchors.**
  `get_duplicated_step_tree` parsed WDK's `{"stepTree": ...}` envelope with a model that
  declared no camelCase alias, so the only supported way to graft one strategy's branch
  into another raised on every call
  ([WDK-STRAT-007](wdk/rules/strategies-and-steps.md)). `StepValidation` defaulted `level`
  to `NONE` and `is_valid` to `True`, and `WDKStep.validation` defaulted to that model, so
  a step document carrying no validation object at all read as a positive claim of
  validity - both defaults are gone, and an absent bundle is now `None`
  ([WDK-VALID-001](wdk/rules/validation.md)). A 4xx body was truncated to 200 characters
  and its `byKey` messages discarded, where a validating endpoint answers with a validation
  bundle; `integrations/veupathdb/_failures.py` now parses it and carries the per-parameter
  messages on the error ([WDK-VALID-006](wdk/rules/validation.md)). And a `date-range`
  bound in any format was accepted locally and sent to WDK, where a badly formatted one is
  a **500** that names nothing ([WDK-PARAM-006](wdk/rules/parameters-and-vocabularies.md));
  a bound is now an ISO date or a local refusal. `step_status` also read `is_valid` without
  its level, so a `NONE` bundle - which WDK emits as `isValid: false` - read as INVALID.

* **The hidden-defaults sweep ran, and the answer is smaller and sharper than the question.**
  On plasmodb.org, **237** of 359 transcript searches carry a hidden required parameter with
  a published default (182 of 325 on 2026-08-14). Binding every published default, 19
  answered 200 and **exactly one returned zero rows**:
  `GenesByRNASeqpfal3D7_Lee_Gambian_ebi_rnaSeq_RSRCWGCNAModules`, on `eda_dataset_id` and
  `wgcnaDataset`. Of the 158 refusals, **not one names a hidden parameter** - every
  parameter WDK named is visible, `samples_percentile_generic` 77 times - so no hidden
  default was refused, and what blocks the remaining measurement is the visible half of
  [WDK-PARAM-010](wdk/rules/parameters-and-vocabularies.md). `channel` (75 searches) and
  `dataset_url` (56) stay unmeasured for that reason, and
  [the item](backlog/hidden-required-default-chooses-the-science.md) now carries the
  numbers instead of the question.

* **The lane's first run found seven dead live tests, and they are fixed.** Every
  `live_wdk` suite under `tests/integration/strategies/` read the persisted plan off
  `Conversation.strategy_ast`, which moved to `ConversationStrategy` when the runtime
  became a package. The tests skip without a credential, so nothing had run them since;
  under the account all seven raised `AttributeError`. They read the projection now, and
  the whole lane - 94 rule and sentinel checks plus the 45 that existed - is **139 green**.

* **One live drift, measured rather than assumed.**
  [WDK-FILTER-006](wdk/rules/filters.md) recorded a **400** naming the column when
  `byValue` is applied where the record-type document advertises it and the step will not
  take it. On 2026-08-22 the same four columns answer **500 `Internal Error`**, and
  `gene_product` still answers 200. The refusal holds, the diagnosis is gone, and a 500 is
  retried three times where the 400 was refused at once. Guest reads have also closed:
  `GET /record-types/transcript/searches/...` is a **401** without a registered token,
  which is why the recording command needs `VEUPATHDB_AUTH_TOKEN` and why the bundle's
  "most live checks need no credential" note no longer holds.

* **WS-V batch 2: the runtime proves the conversation works, and the wire has a written spec.** `packages/assistant-core/tests/synthetic.py` is a complete `AssistantSpec` built from runtime code alone - `single_agent_graph` over bare `TurnState`, an `Agent` whose model is a `ScriptedModel` with four arcs (plain answer, `add` tool call, an approval-required `wipe_everything`, and a `stop_turn` that sets the cancel from inside the run), a `UsageLedger` as the `charge_usage` hook, and a `turn_epilogue`. The suite drives it through the package's public surfaces only, so 128 tests became **192**: turn lifecycle (the graph's chunks reach `conversation_events`, reduce to the `UIMessage` a client renders, and leave one `messages` row whose `usage.totalTokens` equals what the ledger was charged), durability (a reader that reconnects at cursor N gets the remainder **byte for byte**, cursors are strictly increasing and unique, the snapshot equals the live accumulation, two turns split cleanly on `done`), resume (a turn with `is_resume=True` names no prompt field at all, so `turn_input` omits it and the checkpointed prompt survives - the resumed turn answers from it), cancellation, cost, tenancy (two threads driven with `asyncio.gather` share no event id and neither sees the other's chunks), SSE framing against a real Postgres LISTEN channel (a strict `tests/sse.py` parser that accepts `id`/`data` frames and comment frames and nothing else), and a strict-msgpack round trip of every `CORE_CHECKPOINT_TYPES` entry plus the state type a spec declares - which the package could not prove alone before, because the only such suite lived in `apps/api`. **One real bug, found by the suite and fixed**: `_stream_answer` returned on the first event seen after the cancel was set, and pydantic-ai runs the agent in a background task that had already executed the tool and produced its `FunctionToolResultEvent`, so a stopped turn discarded a result it was holding and persisted the call in state `input-available` forever - a tool part that spins after a reload for a tool that finished. The rule is now *a cancelled turn ends before the next part the model starts*: the step already in flight reports its outcome, and the existing guarantee that no further model call is streamed is unchanged (`test_a_cancelled_turn_makes_no_further_model_call_and_finalizes` still passes beside the new `..._still_reports_the_tool_that_already_ran`). **One real gap, named not fixed**: the shipped turn graph resolves no deferred tool call, so `Tool(x, requires_approval=True)` on a one-agent assistant produces `tool-output-error` plus an `error` chunk reading "`DeferredToolRequests` is not among output types" instead of a `tool-approval-request` card, and `TurnState.pending_approval` is a channel no turn ever writes; PathFinder's Lead implements the cycle, `assistants/site_help` cannot - a backlog item with the fix and the chunk sequence it would produce (closed in WS-V batch P1). **`packages/assistant-core/PROTOCOL.md` is version 1.0.0** of the wire: frame grammar, cursor semantics (`after` is exclusive, cursors are per-deployment and not dense), the snapshot/tail contract and the `204` fallback, the `start ... finish done` turn shape, the three `finishReason` values and the rule that an `error` chunk does not end a turn, the full chunk vocabulary, the reduction rules, and the additive-only versioning rule. Its examples are captured from real turns and its tables are compared to `register_core_stream_parts` and to pydantic-ai's `vercel_ai.response_types`, so a new chunk kind or a changed payload fails `test_protocol_document.py`; only generated ids and instants are edited. Recorded as [the wire protocol is a written spec, verified against captured frames](decisions/the-wire-protocol-is-a-written-spec.md), which names the rejected alternatives: generating the page from the models (true by construction, and with nowhere to put a rule) and leaving it hand-written (silent drift). **Where the boundary cuts**: `run_turn`, the cancel watcher that polls `chat_turn_cancellations`, the durable-tool interrupt stream, the title generator, `identity_gate` and the user-message envelope all live in `apps/api`, so the suite composes their package-side equivalent in `drive_turn` (start chunk, `astream`, epilogue, finish, done) and says so; `turn_epilogue` is exercised, `identity_gate` is not reachable without a transport. `docs/knowledge/conventions/verification-gates.md` gained the package lane. Verified: from the package, `uv run pytest` 192 passed with `find_spec("pathfinder") is None`, ruff over `src tests`, ruff-format, mypy --strict 53 files; from `apps/api` - untouched this batch - ruff, ruff-format, mypy --strict 557 files, pyright 0/0/0, import-linter 7 kept 0 broken, 2392 unit and 379 integration tests, `python -m pathfinder.devtools.openapi check` exit 0; knowledge gate clean at 110 files. No file under `apps/web/` was touched.

* **WS-V batch 1: the runtime is a package, and the boundary is now an installation fact.** `packages/assistant-core` is its own distribution - own `pyproject.toml`, own `uv.lock`, `src/assistant_core` importable with no `pathfinder.` prefix, own `tests/` tree, own CI job - and `apps/api` consumes it as an editable path dependency beside `pathfinder-shared`. The eleven-module surface that batch D pinned as "what the runtime may reach outside itself" moved with it, because every entry was runtime-owned by nature: `platform/{config,context,db,logging,pydantic_base,types}.py`, `integrations/embeddings/{model,prefixes}.py` (now `assistant_core/embeddings/`), and the four tables the runtime reads and writes - `conversations`, `messages`, `conversation_events`, `memory_tombstones` - with `MessagesRepository`, `MessageMetadata`, the `GUID` type, the application-id column and the declarative `Base`. **Three modules split rather than moved, each along what it imports**: `config.py` became `RuntimeSettings` (database URL, engine echo, SSE keep-alive, log level and format) in the package with `Settings` subclassing it in the product and installing itself through `use_settings_source`, so one instance still serves the process and `get_settings.cache_clear()` still works in tests; `context.py` kept `veupathdb_auth_token_ctx` and `request_base_url_ctx` product-side and moved the six the runtime and its logger read; `db.py` moved the engine, the session factory and the request-scoped session, and left `init_db` - which runs alembic against `alembic.ini` - as `platform/migrations.py`. `errors.py` and `principal.py` stayed, because their taxonomies name WDK, VEuPathDB bearers and PathFinder service tokens; the one thing `db.py` took from `errors.py` was a sqlite guard, which now raises `ValueError` with the same detail (both reach the client as a 500). **One declarative base, not two metadatas.** A cross-package foreign key resolves only inside the `MetaData` that holds both tables, and the keys cross in both directions (`conversations.user_id` and `conversation_events.task_id` point at host tables; `conversation_strategies`, `background_tasks`, `chat_turn_cancellations` and the two scratchpad tables point back at `conversations`), so the package exports `Base` and the product maps its twelve tables on it. `alembic/env.py` is untouched, `target_metadata` still lists all sixteen tables, and every migration stays hand-written. The package's own test kit declares stub `users` and `background_tasks` tables so `create_all` works with nothing else installed. **The thread lost its relationship to the science**: `Conversation.strategy` and `Conversation.strategy_view` named `ConversationStrategy`, which a package class cannot, so `ConversationRepository.get_with_strategy` and the two listings now select the thread beside its projection through one outer join (one query where `selectinload` issued two), `get_strategy` reads the projection alone, `get_owned_thread_or_404` returns both, and `build_conversation_response`/`build_conversation_summary` take the projection as an argument; `build_conversation_summaries` states the list mapping once. `Conversation.user` was deleted, because a package class cannot name `User`; `User.conversations` stayed as a **one-directional** relationship, because the unit of work reads it to insert a user before the thread that references it, and dropping it turned 22 integration tests into `conversations_user_id_fkey` violations. `TurnContextFactory` became `Callable[[TurnContextRequest], Awaitable[TurnContext]]`, because PathFinder's factory read `strategy_view` off the row it was handed and now has to read its own projection. **Contract 7 was replaced, not deleted twice over**: the package's pyproject names no dependency on this application (the enforcement), `tests/unit/test_package_boundary.py` walks every module in the package and fails on an import naming `pathfinder` while pinning the two `shared_py` wire-type modules it does read (the belt), and the seventh in-repo contract now says *the science never imports an assistant's composition root* - direct-only, like the six layer contracts, because the chat dispatcher still reaches the registry through the job runner. `test_core_boundary.py` moved to composition level and reads the installed distributions instead of the import graph: the science requires the runtime, the runtime requires no part of the science, and the two source trees do not nest. Recorded as [the runtime is a package, so the boundary is an installation fact](decisions/the-runtime-is-a-package.md), which names the rejected alternatives: keeping the runtime in-repo behind contracts only, and leaving `conversations` product-side. Verified: `cd packages/assistant-core && uv run pytest` passes 128 tests with **no `pathfinder` installed** (the isolation proof, testcontainers Postgres, `importlib.util.find_spec("pathfinder") is None`), plus its own ruff and mypy --strict (53 files); from `apps/api`, import-linter 7 kept 0 broken, ruff, ruff-format, mypy --strict (557 files) and pyright zero findings, 2771 tests green in one run (2392 unit, 379 integration, 50 skipped, 98 subtests), `packages/spec/openapi.json` byte-identical, the file-size gate reporting the same five known files (it now scans the package too), and the knowledge gate clean at 108 files. No file under `apps/web/` was touched.

* **WS3 batch 2: a second assistant answers through the same runtime, and its diff contains no orchestration.** `pathfinder/assistants/site_help/` is 3 modules - a spec, one pydantic-ai agent with two read-only catalog tools (`list_veupathdb_sites` over `services.catalog.sites.list_sites`, `describe_site` over `get_record_types` plus `get_raw_searches` for the per-record-type search count), and a ScriptedModel script - registered beside PathFinder in the one registry. It declares `TurnState` with no domain field, a bare `TurnContext` with no strategy session and no research clients, no stream parts, no memory kinds, no checkpoint types, no turn epilogue and **no identity gate**, so a signed-in application user with no VEuPathDB login is served; PathFinder's 401 `WDK_LOGIN_REQUIRED` on the same route with the same body is re-asserted byte for byte in the same test file. A boundary test walks the pilot's modules and fails on a single import of `pathfinder.ai`, and pins the eleven modules it does reach. **Lifted into core to serve it, each because the single-agent path needed it and none of it names a product**: `cost_for_run` moved from `ai/cost.py` to `assistant_core/cost.py` (token-to-USD is the runtime's accounting, and the module imported only `genai_prices`); the chunk-emit primitive became `assistant_core/graph/emit.py`, which also collapsed the two identical copies `_lead_capture.py` and `sub_agent_stream.py` each carried; and the assistant-message write became `assistant_core/graph/turn_message.py`, which read no PathFinder field before the move and now guards its own `SQLAlchemyError` so both finalize paths inherit it. `ScriptedModel` scripts may return a `TextPart`, because an agent whose output is prose has no `final_result` tool to call. `assistant_core/graph/single_agent.py::single_agent_graph` compiles the reusable turn graph: it streams the agent's text and tool calls through the same `PhaseStreamEmitter` the Lead uses, accumulates `RunUsage` into `turn_total_tokens`/`turn_total_cost_usd`, stops on the turn's cancel event without a further model call, and ends in the runtime's finalize step. It compiles **two** nodes, not one: the message row is reduced from chunks the durable log only holds after the agent's step has ended, so a same-node finalize would race the writer. Quota persistence stays product-side - `services.quota` is forbidden to core by contract 7 - so the helper takes the charger as a declared hook and the pilot's turns count against the same monthly budget. The pinned core surface grew by exactly `persistence.repositories.message` and its `_message_metadata`. **Creation paths**: `POST /api/v1/conversations/{id}/begin` takes an optional `assistantId` with the chat route's semantics (new thread takes it, existing thread keeps its own, mismatch 409, unknown 404) and the seed-title generation now uses that assistant's mock rather than the default's; `devtools/chat.py` takes `--assistant`. Verified: import-linter 7 kept 0 broken, ruff, mypy strict (596 files) and pyright zero findings, 2489 unit and 388 integration tests, openapi drift additive only (`BeginConversationRequest.assistantId`), types regenerated, `tsc --noEmit` and 2177 vitest clean, file-size gate reports the same five known files.

* **WS3 batch 0/1: the assistant declares its own architecture, and the runtime routes to it.** `assistant_core/spec.py::AssistantSpec` is a frozen model with `assistant_id` and eight declarations - a graph factory (`checkpointer -> CompiledStateGraph`), an initial-state factory (`TurnStart -> TurnState`), a turn-context factory (`TurnContextRequest -> TurnContext`), a mock-model factory, `checkpoint_types`, a stream-part hook, `memory_kinds`, an identity gate and a turn epilogue - and each one replaces something the pipeline previously hard-coded about PathFinder: `build_pathfinder_graph` named by four processes, `_build_turn_input`'s dict, `_turn_helpers._build_runtime_context` with its two stub research clients, `title_generator`'s `get_mock_model` import, the import-time `register_checkpoint_types` call in `ai/graph/state.py`, `_stream_parts_schemas`'s direct `register_strategy_stream_parts`, `PRODUCT_MEMORY_KINDS`, the chat route's `require_registered_wdk_identity` dependency, and `turn_runner._emit_strategy_revision`. The spec module imports `persistence.models` and `platform.types` and nothing else outside core, pinned by an extension to the core-surface test; `pathfinder.assistants` joined contract 7's forbidden list, so the runtime cannot reach the composition root either. `pathfinder/assistants/` builds PathFinder's spec from the existing `ai/` pieces and `registry.py` is the one composition root that main, the worker, the durable-resume runner and devtools consume. **Routing**: `conversations.assistant_id` (`NOT NULL DEFAULT 'pathfinder'`, indexed, alembic `2026_08_22_0001`, both directions tested against a real database) is the record; an optional `assistantId` on the chat body is read only when the thread is created, an unknown id is 404 `ASSISTANT_NOT_FOUND` and naming another assistant on an existing thread is 409 `ASSISTANT_MISMATCH` rather than a silent substitution - a caller that believes it is talking to B and reads A's answers has no way to notice. The `ChatTurnPayload` carries the resolved id to the worker and `jobs/runner.py` reads it off the row on a durable resume; `dispatch` re-checks the row `begin_conversation` returned against what it resolved, so a concurrent first turn that created the thread under another assistant is refused rather than deferred under the wrong one. **Identity**: the chat route's gate is now `resolve_chat_assistant`, a dependency that resolves the assistant and runs `spec.identity_gate` when one is declared; PathFinder declares `require_registered_wdk_login`, so the refusal is the same 401 `WDK_LOGIN_REQUIRED` with the same title and detail, and `test_wdk_login_required.py` passes untouched. The route table gained a `SPEC_GATED` section with the reason and two cases that fail if the chat route ever carries both gates or stops resolving an assistant. The state factory returns a model and the runtime sends only `model_fields_set`, so an approval resume still leaves the checkpointed prompt alone. Recorded as [the orchestration belongs to the assistant, not to the platform](decisions/the-orchestration-is-the-assistants.md), which names the rejected alternative: one platform graph parameterized by config, rejected because a config-shaped Lead is still a Lead - a simpler app declares a different graph, not a defanged one. Verified: import-linter 7 kept 0 broken, ruff, ruff-format, mypy strict (594 files) and pyright zero findings, 2460 unit and 380 integration tests (98 subtests), openapi drift additive only (`ChatRequestBody.assistantId`, `ConversationResponse.assistantId`, two `ErrorCode` members; the chat request body `$ref` is byte-identical), types regenerated, `yarn tsc --noEmit` and 2177 vitest clean, knowledge gate clean.

* **WS2 batch D: the assistant runtime is a directory, and a contract keeps it one.** The last batch of the platform program (`docs/superpowers/specs/2026-08-21-ws2-in-repo-seams.md`) moved the runtime-generic modules into `apps/api/src/pathfinder/assistant_core/` - 25 modules across `capabilities/`, `conversation/` (chunk reducer, AI SDK adapter, event writer and stream, checkpoint serde and saver, stream-part registry), `graph/` (`TurnState`, `TurnContext`/`AssistantDeps`, the pre-turn and agent-factory hook types, the runtime chunk builders), `memory/` and `models/scripted.py` - and 210 references in 106 files followed, with no alias and no re-export shim. Membership was decided by walking each candidate's transitive imports, not by its name: what reaches nothing of PathFinder's moved, and what does not stayed and is named below. Three files held both halves and split along the line batch A drew: `ai/graph/runtime.py` (`TurnContext`/`AssistantDeps` to core, `Context`/`AgentDeps`/`build_node_deps` product), `ai/graph/stream_events.py` (the chunk builders whose kinds the core registry registers to core; enrichment, strategy revision and ledger stay product), and `integrations/embeddings/semantic_index.py`, whose fastembed singleton was the runtime's only indirect route to a WDK type and is now `integrations/embeddings/model.py` - the cache key still hashes the same model-name string, so no stored `.npz` row was invalidated. `PreTurnHook` and `TurnAgentFactory` became PEP 695 generic aliases bound to `TurnState`, `TurnContext` and `Agent`, so core states the hook shape and `builder.py`, `lead_node.py` and `composition.py` name `PipelineState`, `Context` and `LeadAgent` at the call. **Contract 7** (`The assistant runtime never imports the science, directly or indirectly`) is the only one of the seven that also rejects indirect chains, because a runtime that reaches the science through one hop is not a runtime a second assistant can take; it was proved to bite by planting `from pathfinder.ai.graph.state import PipelineState` in `event_writer.py`, which it reported both as a direct violation and as a two-hop chain to `pathfinder.domain.strategy.staleness`. What stays reachable is the whole allowed surface and nothing else - `pathfinder.platform`, `pathfinder.persistence.models`, `pathfinder.integrations.embeddings` - pinned as an exact set by `tests/unit/assistant_core/test_core_boundary.py`, which caught its own batch when the `ReasoningEffort` de-duplication added `platform.types` to it. That de-duplication collapsed three identical `Literal["none", "low", "medium", "high"]` declarations (`graph/runtime.py`, `conversation/request_body.py`, `platform/types.py`) onto the platform one. Left product-side deliberately, with the blocking import named: `ai/graph/builder.py` names `make_lead_node` and `finalize_turn_node`, and injecting a graph's node set is a seam this batch did not design; `ai/conversation/dispatcher.py` defers `jobs.tasks.run_chat_turn_job` and opens the thread through `services.conversations.begin`; `turn_runner.py` and `_turn_helpers.py` reach `services.conversations.responses` and `graph.runtime.Context`; `request_body.py` publishes `PhaseRole`; `title_generator.py` calls `get_mock_model()`. Recorded as [the assistant runtime is a package boundary, not a contract over scattered modules](decisions/assistant-core-is-a-package-boundary.md), which names the rejected alternative: a contract over a module list with no move, which leaves the extraction an archaeology exercise over a 100-file tree. Verified: import-linter 7 kept 0 broken, ruff, ruff-format, mypy strict (587 files) and pyright zero findings, 2423 unit tests (33 of them the new boundary cases) and 369 integration tests with 98 subtests, `packages/spec/openapi.json` byte-identical, the knowledge gate clean at 105 files, and no file under `apps/web/` or `packages/` touched.

## 2026-08-21

* **WS2 batch C: the runtime hard-codes nothing of PathFinder's any more.** The seven pluggability entanglements (assessment Appendix A rows 5, 6, 7, 9, 12, 13, 14) are inverted. **Roles**: `TurnContext.phase_models`/`phase_reasoning`, `resolve_phase_tier_config`, the agent registry and `PendingApproval.phase` all take a plain string; `PhaseRole` survives only in `ai/agents/roles.py` and the three models that publish it, and `SUB_AGENT_APPROVAL_PHASE` moved to `ai/lead/sub_agent_tools.py`. **Pre-turn**: the live WDK staleness read left the turn node for `ai/lead/pre_turn.py` and reaches the graph as a required `pre_turn` hook. **Agent**: `lead_agent` is no longer a module singleton - `build_lead_agent()` is a factory the builder takes, so each turn owns its instance and its `override`; the dead `isinstance(agent.model, FunctionModel)` branch went with it. **Guards**: `ToolRepetitionGuard` and `ToolResilience` take their tool-name sets and thresholds as constructor arguments, with PathFinder's in `ai/agents/tool_vocabulary.py`. **Instructions**: `_instructions.py` keeps the two generic pinned renderers (typed on `AssistantDeps`); the system prompt, FRAME workspace, graph, ledger and discovered-searches renderers moved to `strategy_instructions.py`, byte-identical (pinned by a render digest before the move, then retired for a per-agent order contract). **Memory**: the store, retriever, tombstone index and re-embed all key by `str`; `auto_write_memories` takes candidates and a user id, so `ai/memory/` imports no product module at all, and `ai/lead/memory_candidates.py` owns the four kinds and the turn-to-candidates mapping. **Mock**: the reusable half (role markers, sequence advance, `FunctionModel` wiring, context vars) is `ai/models/scripted.py`; `mock.py` is PathFinder's script for it, with all 71 mock unit tests unchanged. One `build_pathfinder_graph` composition root replaced five duplicate `build_graph` call sites. Three copies of "read the model id off an agent" collapsed into `ai/models/settings.baked_model_id`, and `ConversationUpdate` left the conversation repository for its own module so the file-size gate reports only the five known files again. Recorded as [the runtime takes the vocabulary as an argument; the wire keeps it](decisions/vocabulary-is-an-argument.md) and [the Lead agent belongs to the turn that runs it](decisions/the-agent-belongs-to-the-turn.md). Found on the way and filed rather than fixed: the repetition guard is registered on no agent, so the mechanism this batch made injectable never actually runs (closed in WS-V batch P1). Verified: ruff, mypy strict, pyright and ruff-format zero findings, import-linter 6/6, 2390 unit tests (67 of them new seam tests), the integration suite, and `packages/spec/openapi.json` byte-identical - the frozen wire contract is what kept the three published role enums and `MemoryValue.kind` narrow.

* **The embedding cache holds one row per entry, and the encode no longer runs on the event loop.** The whole-file cache validated a site by hashing its whole catalog, so any drift in the fetched content re-encoded everything: the same api process built the portal index twice in one boot at 2472 and then 2934 entries, tritrypdb (414) and vectorbase (923) re-encoded hours after another process had written their npz to the shared volume, and a worker chat turn on the portal held the worker at 785% CPU for 2 h 39 m while every queued turn and the heartbeat waited. The cache is now content-addressed per entry: `SearchIndexEntry.cache_key` is a sha256 over the model name, the document prefix and the enriched text, the npz carries `keys` beside `embeddings` with the rows aligned to them, and `build()` reads the file as a key-to-row map, encodes only the entries with no row, assembles the matrix in the canonical `(record_type, search_name)` order from cached and fresh rows, and writes back exactly the current keys, so stale rows leave the file instead of accumulating. A catalog that drifts by N searches costs N encodes, where the portal's second build of that boot paid for all 2934. Files in the old `embeddings + hash` shape, the bundled ones included, read as a miss and are not converted, so each site pays one more full encode and only deltas after that. Two invalidations are automatic: the model name is inside the key, so a model swap invalidates every row, and a cached row whose width does not match the model's output re-encodes the site. Writes are staged under a pid-suffixed name and renamed into place because api and worker share the `embeddings_cache` volume, and a truncated file now reads as a miss rather than raising. Off the loop: `build()` is `async` and the fastembed call runs through `asyncio.to_thread`, which ONNX makes real work rather than a formality since it drops the GIL for the encode; `SearchCatalog._build_semantic_index` is the only caller and both of its call sites were already coroutines, so the seam is three awaited lines and no service changed shape. The turn that triggers a cold build still waits for its own index, but nothing else on the worker does. Eight unit tests pin it, including a delta encode that receives only the new entry's text, a removed entry that keeps the others and drops its key from the file, the old-format and truncated misses, the width miss, and an event-loop responsiveness test whose fake blocks inside `embed` on a `threading.Event` and fails if the loop cannot release it. Verified: ruff, mypy strict and pyright clean, 2351 unit tests.

* **WS2 batch B: a conversation is a thread again, and its strategy is an attachment.** The second hard entanglement (`persistence/models.py`, assessment Appendix A row 4) is gone. Ten columns left `conversations` for a new `conversation_strategies` table whose primary key is also its `ON DELETE CASCADE` foreign key: `record_type`, `wdk_strategy_id` (with its unique partial index), `is_saved`, `step_count`, `strategy_ast`, `estimated_size`, `gene_set_id`, `gene_set_auto_imported`, `experiment_id` and `imported_saved_strategy_ids`. The thread keeps identity, name, dismissal, fork lineage and its timestamps. The child carries **no** owner column: scoping is the parent's `(user_id, application_id)` pair and `services/conversations/authz.py` did not move, so every query that reaches the side table drives from `conversations` and inherits its predicates. Absent means never built: a thread starts row-less, the first strategy write inserts, and readers take `Conversation.strategy_view`, a frozen `ConversationStrategyView` whose field defaults **are** the absent-row semantics, so no call site grew a `None` branch. The relationship is `lazy="raise"` with one explicit `selectinload` in the repository reads that need it (plus `populate_existing`, because the side row is written by Core statements that do not synchronize a loaded relationship - the `expire_all()` that `apply_operation` used to need is deleted and pinned by a test instead); the consumers listing does not load it, because its caller reads names. Two pieces of debt died on the way: `ConversationUpdate.strategy_ast_set` existed only to write SQL `NULL` into a `NOT NULL` column (SQLAlchemy's `none_as_null=False` turned it into a JSON `null`), replaced by `ConversationRepository.clear_strategy`, which updates in place so a never-built thread stays row-less and a cleared graph keeps its gene-set and experiment links; and alembic `2026_08_21_0002` normalizes those stored `null`s to `{}` while moving only the rows that actually hold strategy state. Both directions of the migration are tested against a real database. Verified: ruff/mypy/pyright zero findings, import-linter 6/6 kept, 2317 unit + 369 integration tests, `packages/spec/openapi.json` structurally unchanged (the HTTP contract does not move in this batch). Recorded as [a conversation is a thread; its strategy is an attachment](decisions/conversation-thread-and-strategy-split.md), which names the rejected shape: one table with nullable strategy columns, which would still hand a second assistant's threads two foreign keys into PathFinder's science tables.

* **WS2 batch A: the turn state and the wire vocabulary are seamed.** The first two seams of the platform program (`docs/superpowers/specs/2026-08-21-ws2-in-repo-seams.md`) landed together. `PipelineState` is now `TurnState` (the generic turn: message, accounting, approvals, consults, memories) plus one `domain: StrategyDomainState` field holding the eight strategy fields; `Context`/`AgentDeps` split the same way into `TurnContext`/`AssistantDeps` plus product subclasses; the checkpoint serializer keeps a core allowlist and takes product registrations at import, and a guarded migration flushes old-shape checkpoints while sparing the checkpointer's own DDL ledger. The strict round-trip tests caught three REAL pre-existing decode bugs on the way: `ToolApprovalResponded`, `UserQuestionAnswer` and `StepPushFailure` reached checkpoints unregistered, so a strict decode returned plain dicts and attribute reads would have raised. Two dead fields died instead of crossing the seam (`AssistantDeps.writer`, `PendingApproval.plan_id`). On the wire side, the closed `data-*` union became a `StreamPartRegistry` (core parts in core, strategy parts registered by a product module, schema-only tier for payload models no kind emits), the TS `DataPartKind` opened to `KnownDataPartKind | (string & {})`, and the renderer map is a compile-time-total merge of a core half and a strategy half; part kinds keep their names ([decision](decisions/part-kinds-keep-their-names.md)) because a rename would invalidate persisted event replay. Verified on the combined tree: ruff/mypy/pyright zero findings, 2308 unit + 348 integration backend tests, 2177 vitest, boundaries clean, knowledge gate clean, and a live devtools turn against plasmodb through the new checkpoint shape (frame, build, verify, zero failures). Known couplings deliberately left for batch C: `PendingApproval.phase` still speaks `PhaseRole`, and `turn_state.py` imports `ai/agents/roles` for it.

* **The suite reached 120 passed / 10 failed / 0 flaky, and the feature project is fully green.** Every strategy-edit spec, both purge specs and the enrichment panels pass; the trajectory across the campaign is 94, 105, 120 of 133. The last GO-spec failures were their own lesson: the spec's follow-up question named the mock's GO marker phrase, which routed a plain question into a rebuild that re-minted every step id (the AST leaf changed from `step_65fae9c7` to `step_8b4f3fc6` across one turn) - the question now avoids marker phrases, the precondition reads the vocabulary half through `values`, and the file passes in 33 s. The ten that remain are deep in composite flows and are a healthier class of red: two cross-feature flows now live long enough to fail their axe checkpoint with serious/critical accessibility violations, five journeys share one `rail-strategy-panel` wait, and three are tail-of-run environment flakes; all filed with next steps in [the backlog item](backlog/e2e-suite-residual-failures-after-auth-overhaul.md). One operational lesson is recorded beside them: a worker chat turn on the portal built the portal's semantic index in-process for 2 h 39 m at 785% CPU, freezing every queued turn - the portal's catalog varies per fetch, so a whole-file cache cannot validate, which the per-entry cache entry of the same day closes.

* **The mock now speaks the FRAME contract: discovery before binding, and one half of a GO criterion.** The run-12 edit-family failures reproduced deterministically in the chat debugger: `set_criterion` is enum-guarded to the discovered search universe, the mock never called a discovery tool, and the guard's cold start admitted the first sheet read and then locked the universe to that one search - the second criterion was refused verbatim, `search_name='GenesByTaxon' is not a known value for set_criterion. Choose one of: GenesByText`, three identical replays, retry cap, "Response failed". Separately the GO arc died on the parameter rule `go_term and go_typeahead on GenesByGoTerm are ORed halves of one criterion ... Put the criterion in go_typeahead`, because the canned values filled both. `frame_call` now emits `list_searches` before any criterion so every canned name enters the universe, and `_go_kinases` carries `go_typeahead` only. Both arcs re-run clean end to end against live plasmodb in the debugger: the interpro turn ends on the feedback prose the specs wait for and the GO turn on the success digest, zero tool failures. Six new mock unit tests pin the sequence and the halves rule; the SSE golden is untouched because its prompt rides the echo arc.

* **A transient database ping can no longer latch the API unready forever.** Both health endpoints re-verify the database with a live ping and marked it failed on any exception - and nothing ever marked it ready again, so one blip during a CPU-saturated embedding sweep left `/health/ready` at 503 (with `error: ""`, because `str(TimeoutError())` is empty) while login, writes and enrichment all served correctly; the container reads unhealthy, `web` refuses to start behind it, and every page load sits at "Starting up...". The successful ping now marks the database ready again - the live ping is the authority in both directions - and a failure records `str(e) or type(e).__name__` so the state always names a cause. Three integration tests pin recovery on both endpoints and the non-empty label.

* **The embedding cache keys content, not fetch order, and lives in a volume.** `_catalog_hash` serialized entries in catalog iteration order, and that order differs between a live fetch and a disk-restored catalog, so an identical catalog re-embedded from scratch on most boots - measured as a 4.5-minute rebuild of a 3-hour-old amoebadb index, roughly 20-25 minutes per recreate for all sites, and hours when the portal missed. `build()` now sorts entries by `(record_type, search_name)` before hashing, which also guarantees the cached rows align to the entries by construction; two unit tests pin cache survival across a reordered catalog. The cache directory is a named `embeddings_cache` volume shared by api and worker, so one process's sweep warms the other and a recreate starts warm. The e2e overlay also pins `VEUPATHDB_SITES_CONFIG` to `e2e-sites.yaml` - the portal plus the five component sites the suite drives - so an e2e boot never embeds the seven catalogs no spec touches.

* **The enrichment cluster is explained: the call is legitimately slow, and the specs now say so.** A timed probe of `POST /api/v1/gene-sets/{id}/enrich` with all five types on live plasmodb answered 200 in 163 s with real terms (GO 17/20/20, word 4; pathway reported "Analysis unavailable" for the two-gene set, which is WDK's own verdict). The pipeline is bounded server-side - a 300 s analysis poll cap, capped retries, a process-wide batch semaphore - and the run-12 traces show the request simply outliving the specs' 120 s wait (status -1, neither result nor error), where before the proxyTimeout fix the 30 s rewrite cap answered with a bare 500 that the specs accepted as an outcome. The enrichment helper's ceiling is now 360 s and it extends only its own test's budget via `test.setTimeout`; `ChatPage.goto` tolerates a lagging readiness gate for 60 s. The purge specs were reconciled to the registered-account model in the same pass: the shared WDK account carries strategies the run did not create, so both specs now assert identity, not count - `:66` imports the account's strategies first and proves a dismissed projection is not resurrected, `:120` collects the run's own `wdkStrategyId`s and proves none survives on any site.

## 2026-08-20

* **The suite reached 105 passed / 23 failed / 2 flaky / 0 did-not-run, and the 23 have three measured causes.** The run-10 deletion, durable-SSE and auth clusters are green. Of what remains, (a) the strategy-EDIT family and the edit-ending journeys time out on `/returned 0|root size is 0|too narrow|loosen/i`, the OLD mock's verification-feedback wording, which the rewritten mock never emits - the one reconciled spec (`insert-saved:15`, via `expectVerificationFeedback()`) passes, the rest carry inline copies of the dead regex; (b) the purge specs fail against the polluted shared WDK account, named outright by the flaky `user-data:66`: "sync-wdk re-imported 50 active strategies on plasmodb after dismiss purge" - prior runs left hundreds of strategies under the registered test account, so "everything deleted" cannot hold; (c) the enrichment cluster (analysis, workbench panels, all three cross-feature specs, five site journeys) waits 120 s for a result OR an error and sees neither, which predates every change this week and is the one unexplained cause. All three, with the fix each needs, are in [the backlog item](backlog/e2e-suite-residual-failures-after-auth-overhaul.md).

* **The mock model is site-aware, and two more response-path bugs are fixed.** The deterministic mock (`ai/models/mock_specs.py`, `mock.py`) now derives the organism from the conversation's site (five sites), builds four spec shapes (single, GO, a 3-node InterPro chain, a 5-node combine), and routes prompts naming InterPro/PF00069/EC 2.7 through a feedback arc whose fix-prompt succeeds - which exposed a real harness bug: the frame stage counted tool calls instead of resolved parameters, so a `ModelRetry` read as success and produced an empty build. Specs stop hardcoding node ids through new AST fixtures (`e2e/fixtures/ast.ts`). On the product side, `DELETE /api/v1/conversations/{id}` and restore committed after the response like `/open` did (commit moved before it, three integration tests reading through a second session), and Next's rewrite proxy answered any API call over its 30 s default with a bare 500 - a long multi-site purge among them - so `next.config.ts` sets `experimental.proxyTimeout: 300_000`, recorded with the alternative it rejected in [the API rewrite carries a long call](decisions/the-api-rewrite-carries-a-long-call.md). The e2e cleanup client sent no CSRF header (every non-GET postcondition 403'd silently; header applied at all seven call sites), and `auth.spec.ts` inherited the worker's cookies through `browser.newContext()`, so its signed-out cases ran signed in - it now passes an explicitly empty storage state.

* **Two bugs only a fast client could see, found by running the e2e suite against the production web image, both fixed.** First: `POST /api/v1/conversations/open` returned the new conversation id before the row was committed, because the request-scoped session commits in yield-dependency teardown and FastAPI runs that after the response is sent; the dev-mode web client was slow enough to lose that race every time, and the production build's instant sidebar refresh won it - a trace shows open returning one id and the immediately refreshed listing (HTTP 200) holding only other ids. The route now commits before returning. In-process test transports buffer the whole app call including teardown, so no integration test can reproduce the race; the e2e suite is the regression test. Second: the app's on-load `POST /api/v1/veupathdb/auth/refresh` re-minted `pathfinder-auth` from the `Authorization` cookie even when a valid internal session existed, silently switching accounts - in e2e every worker collapsed onto the one registered VEuPathDB user while older cookie snapshots kept writing as per-worker users (two requests from one test carried different `pathfinder-auth` cookies). The endpoint now honors its own docstring: a request with a valid internal token keeps it (200, no Set-Cookie); absent or expired still mints, pinned by three unit tests. The e2e stack itself was corrected on the way: the web service runs the production image (the containerized dev server was OOM-killed twice and hydrated slower than Playwright clicks), and `docker-compose.e2e.yml` now points at `pathfinder_test` instead of the dev database, into which earlier runs had written several hundred conversations. Full-suite result after all fixes: 94 passed / 26 failed / 1 flaky in 1.3 h with every one of the 254 worker turns succeeding; the residual failures are recorded as [four clusters in the backlog](backlog/e2e-suite-residual-failures-after-auth-overhaul.md).

## 2026-08-19

* **Every owned resource now belongs to a user under one application, and the same user reaching it from another application is refused exactly as a stranger is.** `application_id` (`NOT NULL DEFAULT 'pathfinder'`) joins `conversations`, `gene_sets`, `control_sets`, `experiments`, `memory_tombstones` and `monthly_usage`; the rest of the tables hang off a conversation and are scoped through it. The value comes from `application_id_ctx`, which the request resolver already set from `X-PathFinder-Service-Token` and which a worker job now sets from the conversation row - the only durable record of which application a turn belongs to - through `attach_conversation_application`, which raises rather than guessing when the row is gone. The check went **inside** the helpers that already decide ownership, so no route grew a parallel check: `owned_by_caller` in `services/conversations/authz.py` (used by the 403 helper, the 404 helper, revert, fork and WDK open), the repository list queries, `GeneSetStore.aget` and `ExperimentStore.aget` plus their cache merges (a process-local cache hit was the one path that could cross applications without touching the database), `ControlSetService` (a public control set is public to its own application, not to every application), and the durable-task queries, which now join the conversation. Memories moved with them: the namespace is `("app", <application>, "user", <user>, <kind>)` from one builder, and the alembic revision rewrites every existing `store` and `store_vectors` prefix to `app.pathfinder.user....` by copying under the new prefix before deleting the old, because `store_vectors` references `store(prefix, key)` with no `ON UPDATE` action; the rewrite is guarded by `to_regclass`, since the store tables are created by the memory lifespan and not by alembic. Quota splits attribution from the cap: `accumulate` writes the calling application's row on a `(user, application, period)` unique key, `get_current` sums every application of the user, so `GET /api/v1/me/quota` keeps its shape and a second assistant cannot double a budget. **Twenty-nine tests pin it**: the authorization matrix gained a third client - the same user, a different application - which found **21 mutating routes** serving another application's request (chat opened an SSE stream, PATCH and fork answered 200, delete answered 204, the memory PATCH and DELETE answered 200 and 204) and now finds none; six HTTP cases on the read half (conversation, gene set, experiment, control set and memory listings, and a single-resource read whose refusal must equal the refusal a stranger gets, not a status of its own); one on the purge; three on memory isolation including a tombstone; three on quota; two on the worker reading the application from the row; and six on the migration, run against real databases - a seeded old-namespace memory moves with its expiry and its vector and comes back on downgrade, the column is `NOT NULL DEFAULT 'pathfinder'` on all six tables, the four new indexes and two unique keys exist, and a database that has never opened the store upgrades without error. The two worker-boundary unit suites now also assert the job runs as the conversation's application. `DELETE /api/v1/user/data` follows the same rule: it dismisses or deletes only the calling application's conversations, gene sets, experiments and control sets, and evicts only that application's entries from the gene-set cache, because a caller that cannot read a resource must not be able to destroy it; an erase-everything action that names no application does not exist yet. Its `deleteWdk=true` arm was deleting **every** strategy in the user's VEuPathDB account for the site - website work included - because it purged what `list_strategies()` returned; it now deletes the ids the already-scoped conversations carry in `wdk_strategy_id`, intersected with what WDK still holds, and leaves a saved strategy a chat only imported alone, since nothing records whether the user made it here or on the website. Recorded as [a resource is owned by a user under one application](decisions/application-id-tenancy.md), which names the rejected shapes: one user row per application (it splits the VEuPathDB identity that `users.external_id` holds, so one researcher becomes several users with several WDK guest tokens and no single budget) and one database per application (a pool, a migration run and a backup per assistant, with no shared quota). Left per user on purpose: `exports`, a short-lived download artifact fetched by a UUID its owner was just handed, which nothing lists.

* **A VEuPathDB bearer token now authenticates, a service token names the calling application, and a bearer request is exempt from the cookie-CSRF header.** Every request resolves to one `Principal` (`platform/principal.py`: `user_id`, `application_id`, `credential`) through one function (`platform/security.py::_identify`), in a fixed order: an `Authorization: Bearer` value that verifies as a PathFinder HS256 JWT is `pathfinder-bearer`, the same header otherwise is read as a VEuPathDB token, the `pathfinder-auth` cookie is `pathfinder-cookie`, and nothing else is 401. `CurrentUser` still hands routes a UUID, derived from the principal, so no route changed. The VEuPathDB path is validated locally, not by asking WDK: the signing key is `GET <VEUPATHDB_OAUTH_URL>/jwks` (default `https://auth.veupathdb.org`), the first entry whose `kty` is `EC`, cached in-process for 120 seconds, and the token is an **ES512** JWT on **P-521** - the same protocol `OAuthClient.getValidatedEcdsaSignedToken` implements for every VEuPathDB container service. Issuer and audience are deliberately unchecked, matching the reference client, whose `validateClaims` is an empty TODO: a site mints tokens for its own client id, so an `aud` check would refuse every browser-session token. A live registered-user token proves two facts the design turns on - its header is `{"alg":"ES512"}` with **no `kid`**, so a key lookup by key id finds nothing, and its payload carries `sub`, `is_guest`, `iss`, `aud`, `azp`, `iat`, `auth_time`, `exp`, `jti`, `preferred_username`, `signature` and **no `email`**. Because `users.external_id` is the email, the bearer path still maps through the resolver the refresh route uses (WDK `GET /users/current`), so bearer and cookie land on one row rather than two; the mapping is remembered per token hash for five minutes. A guest token is 401 on the bearer path, since a guest is a new identity per request and owns nothing durable. A JWKS that cannot be read - unreachable, non-200, or carrying no EC key - is **503** naming the identity provider rather than 401, because the credential was never examined; a token that fails against a key we did hold stays 401. Application identity is the optional `X-PathFinder-Service-Token` header matched in constant time against `PATHFINDER_SERVICE_TOKENS` (`app_id:secret[,...]`, secrets at least 32 characters, parsed at settings load, absent from every repr); an unknown token is 401, an absent one leaves `pathfinder`, and the id also rides a request ContextVar for the tenancy work. `X-Requested-With` is now required of cookie requests only, because a browser never attaches an `Authorization` header by itself. OpenAPI declares all three schemes (`APIKeyCookie`, `HTTPBearer`, `APIKeyHeader`), which fell out of using FastAPI's own security classes rather than patching the schema. **Fifty-two tests pin it**: nine on the validator against a locally generated P-521 pair (expired, wrong key, HS256, missing `sub`, a JWKS with no EC key, an unreachable server, and one fetch for many tokens), twenty-one on the principal, the service-token registry and the resolver (credential order, repeated application id, short secret, missing separator, secret absent from the repr, both ContextVars published), six on the CSRF rule, six on the settings, and ten HTTP integration cases (a bearer GET with no cookie and no CSRF header, a bearer POST that creates a conversation, a cookie POST that is still 403, a guest token, an unknown service token, a PathFinder bearer that never touches the OAuth server, and one WDK lookup across two requests). Recorded as [a VEuPathDB bearer token is the user; a service token is the application](decisions/bearer-identity-and-service-tokens.md), which names the rejected `proxied-user-id`: it is honoured only beside an admin token, and PathFinder acts on WDK **as** the user, so it needs the user's own token rather than permission to name them.

* **Done and removed: a queued or silent turn now keeps its SSE stream open and says "Queued".** `iter_sse` (`ai/conversation/event_stream.py`) wraps its pull from the LISTEN tail in a pending task, so a timeout emits `: keep-alive\n\n` and the tail keeps its asyncpg connection: one comment frame per `SSE_KEEPALIVE_SECONDS` (new setting, default 15, `ge=1`) of silence, on `POST /api/v1/chat` and on the resume stream `GET /api/v1/conversations/{id}/events` alike. A comment frame carries no `id:` and no `data:`, so the durable log, the cursor the client stores at `[DONE]`, and the AI SDK's parser see nothing: `eventsource-parser` 3.0.6 returns from `parseLine` on a leading `:` and only calls `onComment`, which `DurableChatTransport` does not pass, and its `dispatchEvent` fires only when the data buffer is non-empty. Before this the response wrote nothing at all until the worker's first chunk, and a tab that waited behind another turn of the same conversation showed "Response failed - Failed to fetch" while the turn ran to completion server-side. The wait itself is now named: `dispatcher.dispatch` persists `data-turn-status {label: "Queued"}` through the same writer as the user message, before `defer_async`, so the chunk can never land after the worker's `start`; the running message reads "Queued" until `run_turn` writes `start` and `Preparing context`, which is its first pair of chunks, so no second "Running" status exists. The queued chunk carries the turn id the job runs under, so a stop pressed while the turn is still queued reaches the turn the worker polls. Deliberately not added: a queue position, which needs a procrastinate query per request. Pinned by five unit cases on the frame and the setting, two integration cases (the queued chunk is the only row after the user message while the job waits, and the finished turn replays it in the snapshot), three vitest cases on the transport (comments dropped, an all-comment stream survives, a malformed data frame still kills the stream), seven on the placeholder label, and the SSE golden fixture, which gains exactly one chunk at its head. A keep-alive also holds open a stream that nothing will ever finish, so `jobs/maintenance.py::release_stalled_jobs` reads the `ChatTurnPayload` of each stalled `chat_turn:run` job and writes `error` + `finish` + `done` through `ChatEventWriter` before it fails the job, while the conversation lock still blocks a successor turn, and only when the newest chat chunk is not already `done` so a turn that ended is never reopened. A stalled `durable:*` job is released and not closed, so a tool resume whose worker died still leaves its stream open. Pinned by two integration cases and by `cancel_active_turn`, which now has one of its own showing a stop while queued reaching the worker's turn id and not the user message id.

* **Done and removed: every workbench experiment stream POSTed without the header the CSRF middleware demands.** `lib/sse/typedEventStream.ts` hand-built its own request headers, so the five stream callers - Evaluate, Batch and Benchmark in `features/workbench/api/streaming.ts`, the seed stream in `lib/api/experiments.ts` and the threshold sweep in `lib/api/analysis.ts` - sent `accept` and `content-type` and nothing else, and `POST /api/v1/experiments` answered `403 {"detail":"Missing required X-Requested-With header"}` while the browser showed "stream failed: 403". The helper now builds every header through `getAuthHeaders` in `lib/api/http.ts`, the builder the rest of the app already used, so `X-Requested-With: XMLHttpRequest` rides on every stream request; the per-caller copy in `useTaskEventStream.ts` is gone, and with it the `headers` option no caller passes any more. A refused stream now names the API's own `detail` beside the status instead of the bare number. Six vitest cases pin it: the helper on a POST and on a GET, the thrown message on a 403, and the three workbench generators driven through the real helper against a stubbed fetch.

* **A tool the user refuses now reads "Denied" on its sub-agent step card, not "failed".** `SubAgentStepPayload.state` carries `denied` beside `started`, `completed` and `failed`; `ai/lead/sub_agent_stream.py` emits it for a `ToolReturnPart` whose outcome is `denied` and keeps `failed` for a retry prompt or a returned error directive; the card maps it to the AI SDK's `output-denied` state, which the shared tool header already labels "Denied" and which shows the denial message as the result rather than as an error. A refused `delete_step` was indistinguishable from a WDK 404 in the UI and in telemetry before this.

* **The live WDK suites act as a registered VEuPathDB user now, or they skip under their own names.** VEuPathDB serves the WDK service to registered users only, so a cookie-less live suite proves nothing. One session fixture (`tests/conftest.py::wdk_registered_token`, over `tests/_support/wdk_credentials.py`) logs in once with `WDK_TEST_EMAIL`/`WDK_TEST_PASSWORD` through the same `password_login` the login route calls, and `require_wdk_creds` hands that token to a test or skips it with "live WDK now requires a registered user; set WDK_TEST_EMAIL/WDK_TEST_PASSWORD"; five copies of the login helper and six copies of the credential gate are gone with it. The strategy suites put the token on `veupathdb_auth_token_ctx`, which is where the discovery tests move too, because they were calling WDK with no credential at all. In the authz matrix the five owner cases WDK answers - experiment enrich, re-evaluate and results/record, gene-set enrich and results/record - are one parametrized case each and send the token as `X-VEUPATHDB-AUTH`, the header the request resolver reads; without credentials each of the five skips under its own route name, and the non-owner and cross-application refusals still run, because they are refused before anything reaches WDK. With the credentials the matrix is 17 passed; without them, 12 passed and 5 skipped.

* **Done and removed: a caller that supplied every visible required value was refused for a hidden one it could not see.** `validate_parameters` reads WDK's verdict before the local checks, and WDK judges the parameter shape the contextual metadata read hands it, so a hidden parameter missing from that read comes back as "Cannot be empty.". `context_for_metadata_read` was supplying only the hidden parameters that **allow** empty; it now supplies every unset hidden parameter that publishes an `initialDisplayValue`. Measured on live plasmodb.org, `transcript/GenesByText` with the three visible required values set (`text_expression=kinase`, `text_fields=[product]`, `text_search_organism=[Plasmodium falciparum 3D7]`) answered `text_fields: At least one parameter that 'text_fields' depends on is invalid or missing. Errors: { document_type => Cannot be empty. }; document_type: Cannot be empty.` and now returns canonical values including `document_type = "gene"`, disclosed in `substituted` because the caller never stated it. The run path is unchanged: `fill_hidden_required_defaults` still decides what a hidden required parameter is worth when the search is executed, and this is the metadata read. `profile_pattern` travels in that read too, at the published `hsap=1T`, which is exactly the request already measured at 200 when both structural maps accompany it. Pinned by the three unit cases in `test_search_params_under_context.py` that the old rule owned, rewritten to the new one, and by the live pipeline test that named the contradiction. Found by running the live parameter suites with the registered token for the first time; 45 pass, 0 fail.

* **Done and removed: every WDK-backed feature now requires a registered VEuPathDB login, and PathFinder mints no guest identity at all.** VEuPathDB refuses unregistered programmatic access: measured on 2026-08-19 against plasmodb.org and toxodb.org, `GET /record-types/transcript/searches/GenesByTaxon` answers `401 "Valid API Key required for this endpoint."` with no cookie and `403 "This endpoint is only available to registered users, and requires an API key."` with a freshly minted guest cookie, `POST /users/current/steps` answers 403 the same way, and a registered token answers 200; a browser `User-Agent` and `Referer` change nothing. The refusal is one code: `ErrorCode.WDK_LOGIN_REQUIRED`, 401 problem+json, title "VEuPathDB login required", detail "Sign in to VEuPathDB to use searches, strategies and gene sets.", which the web app keys on. The gate is one route dependency, `transport/http/deps.py::require_registered_wdk_identity`, which verifies the request's token locally against the OAuth server's cached ES512 key rather than decoding claims unverified, so a forged, expired or guest token is the same refusal on the cookie path as on the bearer path, and an unreadable JWKS stays 503 naming the identity provider. It is on the 31 routes that reach a WDK account and on no others: `POST /api/v1/chat`, the seven conversation subroutes that act on WDK (step-counts, operations, open, sync-wdk, save-substrategy, insert-saved, fork), the eval pair, the seven gene-set routes that materialize or read a WDK dataset, and the fourteen experiment routes that run, refine, read or delete a WDK strategy. A listing that reads local rows is not gated, so a user with no VEuPathDB session can still list and delete their own gene sets, read and annotate their own experiments, purge their own data, and keep every conversation, note, memory and setting. `tests/unit/transport/test_wdk_gate_route_table.py` names every gated route and carries the reason for each ungated route that can still reach WDK, so a route cannot change category quietly. Guest minting is deleted rather than disabled: `mint_guest_token`, `extract_any_auth_cookie`, `ensure_wdk_identity`, the `users.wdk_guest_token` column (alembic `2026_08_19_0002`, upgrade and downgrade both pinned against a real database) and its repository setter are gone, with the autouse test fixture that kept minting inert. The service account is confined by the transport, not by convention: `_http.py::_effective_token` refuses any `/users/` path when `veupathdb_auth_token_ctx` is empty, before the request leaves the process. `/users/current` is included: it resolves which WDK account the caller is, and without a token the answer is the service account or a fresh guest. `fetch_wdk_user` returns None without a request token, so `GET /api/v1/veupathdb/auth/status` can no longer report the application's own account as the signed-in user, and `DELETE /api/v1/user/data?deleteWdk=true` skips the WDK half and reports `wdkStrategies: 0` instead of refusing the whole purge. The suites take `WDK_TEST_TOKEN` in preference to `WDK_TEST_EMAIL`/`WDK_TEST_PASSWORD`, and a suite about what a route does past the gate says so through one fixture (`signed_in_to_veupathdb`) rather than carrying a token it does not need. **Twenty-five new tests pin it**: six on the service (no token, guest token, unverifiable token, registered token returned, an unreadable key that stays 503, and no request token reading no WDK user), five on the transport guard (a step read and a step create refused with nothing on the wire, the user's own token served, a search listing served as the application, `/users/current` served), seven HTTP cases against a real ES512 key and a stubbed JWKS (chat, a gene-set route, an experiment route and a strategy operation refused with the exact code, title and detail; a guest token and a forged token refused; a registered token reaching the handler's own 404), two on the migration, one that a signed-out purge still deletes the local rows, one that the `Authorization` cookie is read like the header, and three that pin the route table. Recorded as [a WDK-backed feature requires a registered VEuPathDB login](decisions/wdk-requires-registered-login.md), which names the rejected shape: one shared guest or service identity for anonymous users, which would land every user's strategies in one VEuPathDB account where each could read, edit and delete the others' work, and where the researcher would never find the work again under their own login.

* **The web app asks for a VEuPathDB login before any WDK-backed action, and never runs as a silent guest.** One recogniser reads the refusal the API now sends ([a WDK-backed feature requires a registered VEuPathDB login](decisions/wdk-requires-registered-login.md)): `wdkLoginRequiredDetail` in `lib/api/errors.ts` parses a 401 whose problem+json carries `code: "WDK_LOGIN_REQUIRED"` and returns the server's own detail, from an `APIError` (every JSON path, including the Kubb client) and from the plain `Error` the AI SDK's `HttpChatTransport` throws with the response body as its message. `state/useAuthGateStore.ts` owns the prompt: `handleWdkLoginRequired` reports the detail through `toast.error` under one fixed toast id, so a burst of refused queries replaces one toast instead of stacking, and opens the sign-in modal with that same text; it is the one routing call in the query-cache handler, in the composer's `beginStrategy` catch and in `useChat`'s `onError`, so no refusal is retried silently and none is swallowed. The query client used to drop every 401 without a word; it now forwards this one, with the error itself on the notice so the app layer can route it. The composer is the standing gate: `useVeupathdbSignedIn` is true only when the auth status says so, and while it is false the input and Send are disabled, the placeholder and an inline `VeupathdbSignInRequired` banner read "Sign in to VEuPathDB to build strategies", and its Sign in button opens the modal. `?embedded=true` no longer skips the check - `requiresFullScreenSignIn` blocks only a standalone session with the forced modal, and an embedded one renders so the composer carries the prompt in place, which is also why the modal is now reachable in embedded mode and closable when the user opened it. Both shells hold one prompt and one handler: `app/components/VeupathdbSignInGate.tsx` registers the query error handler and renders either the forced modal or the requested one, and the conversation layout and the workbench layout each render it, so a refusal on a gene-set or experiment query opens the prompt on whichever shell the user is standing in. It replaced two copies that had drifted: the conversation layout's second `LoginModal` was dead (its `open` could only be false after the early return), and the workbench layout drove its modal from `signedIn` alone and registered no handler at all, so a refusal there was silent. No UI copy or affordance promised guest use, so none was removed. The Playwright suite acts as the registered account: the per-worker storage state adds `WDK_TEST_TOKEN` as the `Authorization` cookie the API forwards to WDK, the postcondition client in `e2e/fixtures/api-client.ts` takes the browser's whole storage state rather than copying one cookie name (it was dropping that token, which would have 401'd every postcondition call on a WDK-backed route), PathFinder identity stays per worker through `/dev/login?user_id=worker-{N}`, `wdkTestToken()` fails loudly and never prints the value, and the unreferenced `e2e/fixtures/auth.setup.ts` is gone. Pinned by 41 vitest cases over nine files (the recogniser on both error shapes, the store and its routing including a real 401 problem+json driven through `requestJson` and the shared toast id, the query-cache forward against the still-silent 401, the shared gate opening on a refused query and staying shut on an unrelated one, `useChat`'s `onError` driven by a stubbed chat POST, the composer disabled and prompted when signed out and clean when signed in, and the embedded-versus-standalone gate) and three Playwright cases in `e2e/feature/auth.spec.ts`.

## 2026-08-18

* **A non-finite enrichment value is `None`, never 0.0, and the wire says how many pasted genes the statistic used.** WDK returns `"Infinity"` for an odds ratio (and can for a fold enrichment) when the term's genes are all inside the set, and the old `SafeFiniteFloat` clamped every non-finite ratio and probability to 0.0: the strongest hits sorted last and a non-computable FDR read as maximally significant. `EnrichmentTerm` ratios and probabilities are now `float | None` through one annotated type (`platform/pydantic_base.py::NonFiniteToNone`), the ranking rule lives in `services/enrichment/ranking.py` (a `None` ratio sorts first descending, a `None` probability sorts last ascending and is never significant), CSV/TSV write `Inf` for an unbounded ratio and an empty cell for a probability, JSON writes `null`, the HTML report cannot raise, and the analysis table, dot plot and custom-enrichment section render `Inf` / `n/a` from the regenerated nullable types. `custom.py` reports `geneSetInBackground` beside the pasted `geneSetSize`, and its own odds ratio is `None` when a 2x2 cell is zero instead of a clamped finite number (`3600.0`, `180.0`, `880.0` were reported where the truth is unbounded). The authz matrix now covers experiment, gene-set, control-set and memory routes beside conversations (41 cases, five resource kinds), asserts the owner is not refused (401/403/404 or a hang) with a fresh owned resource per case, classifies ids one level into nested bodies including `list[Model] | None`, and proved it can see holes by three injected faults; it found none.

## 2026-08-17

* **Done and removed: an approval-required tool inside a sub-agent now reaches the user, and the answer re-enters that sub-agent.** `optimize_search_parameters`, `delete_step` and `clear_strategy` carry `requires_approval=True`, but a sub-agent run is not streamed through the VercelAI adapter, so its `DeferredToolRequests` output was dropped by an `isinstance` filter: `verify_strategy` raised `TypeError` and `recover_failed_steps` returned an empty `RecoveryDelta` while the real state was "waiting on the user". The suspended run is now kept. The inner call is announced to the client as its own tool part - `tool-input-start`, `tool-input-available` with the real arguments, and `tool-approval-request` whose approval id IS the inner tool call id - so the generic Approve/Deny card renders it with no frontend change; the Lead's dispatch call is deferred with `CallDeferred`, and the whole turn checkpoints on `PendingApproval.sub_agent`, which carries the sub-agent's role, its approvals and its message history. The next turn replays that history with `DeferredToolResults(approvals={...})`, closes the inner part with `tool-output-available` or `tool-output-denied`, and hands the finished delta to the Lead as `DeferredToolResults(calls={dispatch_call_id: delta})` - the value the wrapper would have returned. A second approval defers the turn again instead of running the Lead. Each dispatch is one function (`run_frame`, `run_recovery`, `run_verification`) shared by the direct call and the re-entry, so the spec sync, the build re-sync and the verification digest cannot drift between the two paths, and sub-agent usage is recorded once per half under the dispatch's call id. **Nine tests pin it**, all against the real verification and execution toolsets with scripted models: the three chunks and their ids and arguments, `PendingApproval(phase="verification", sub_agent=...)` with the Lead's dispatch call suppressed, an approval that runs the inner tool exactly once, a denial that finishes the sub-agent with the tool never invoked, a second approval that re-defers, the frame dispatch resumed from its stored arguments, and a strict-msgpack round trip of the nested approval - `PendingApproval` itself was never on the checkpoint allowlist and is now, with the two new models. `sub_agent_tools.py` was 415 meaningful lines against a 400-line gate before this work; the streaming engine moved to `ai/lead/sub_agent_stream.py` and the two spec messages to `ai/lead/dispatch_messages.py`, so every file it touches is under the cap. The turn after a deferral always resolves the dispatch call, because pydantic-ai re-executes a deferred call it is given no result for and the execution role would re-apply its edits: a typed reply resolves the card (approved when the text is nothing but an approval phrase by the injection scanner's own whitelist, otherwise denied with the text delivered to the Lead as the next message), a turn that resolves nothing keeps the card and runs no sub-agent, and two dispatches deferred in one response raise `ConcurrentSubAgentApprovalsError` naming both rather than silently re-running the second. Recorded as [a sub-agent's approval is answered inside that sub-agent](decisions/sub-agent-approvals-re-enter-the-sub-agent.md), which names the two rejected shapes: re-asking through the Lead's `consult_user` (loses the tool's identity and arguments, and re-decides the call instead of resuming it) and dropping `requires_approval` from the sub-agent tools (a ~15 minute sweep and two destructive edits would run unasked).

* **Backlog reshaped by the "stop the bleeding" batch, and one new item that a scripted run proved.** The worker-serialisation item lost its concurrency half: `jobs/worker.py` now runs `WORKER_CONCURRENCY` jobs (default 4; procrastinate 3.8.1 has one global setting, not per-queue), chat-turn and durable-tool jobs are deferred with `lock=<conversation_id>` so only one conversation's jobs serialise, and a `maintenance:release_stalled_jobs` sweep fails any job left in `doing` past `WORKER_STALLED_JOB_TIMEOUT_SECONDS` (default 3600, measured from the job's started event and not the heartbeat, because a starved loop can self-prune a live worker's row) so a killed worker cannot wedge a conversation behind its lock. What remains of that item is the SSE "queued" heartbeat. The heartbeat-starvation item now states that concurrent turns starve the loop more, not less. New, and closed the same day by the entry above: an approval-required tool inside a sub-agent never reaches the user - a scripted `FunctionModel` run shows `optimize_search_parameters` in the verification sub-agent ends in `TypeError`, `delete_step` in the execution sub-agent ends in an empty `RecoveryDelta` with no error, and only the Lead's `consult_user` yields a `tool-approval-request` chunk; the frontend now renders generic Approve/Deny controls for any `approval-requested` tool part, so the fix is entirely on the sub-agent streaming path. Also closed outside the bundle, recorded here so the ledger is complete: `POST /api/v1/chat` and `/api/v1/eval/strategy-gene-ids` now refuse a non-owner (404, hidden existence) with an authz matrix over every conversation-scoped mutating route; the PIGuard pure-approval short-circuit is unconditional (its detection keyed on a chunk nothing emits); `phase_models` is validated against the model catalog; agent telemetry content export is opt-in; custom-enrichment p-values use the exact hypergeometric tail (n=5000, k=200, m=50, x=15 was 2.08e-21 by normal approximation, exact 4.17e-10) and the significance count reads FDR. The wider assessment that ordered this batch is `docs/assessment/2026-08-17-veupathdb-assistant-platform-assessment.md`.

* **Done and removed: the unit tier could reach the network, so an inert stub passed against a live server.** An autouse fixture in `tests/unit/conftest.py` now patches `socket.socket.connect`, `connect_ex`, `socket.getaddrinfo` and the event loop's `create_connection` and `getaddrinfo` for the duration of every unit test, so the tier refuses every connection made through Python's socket module, and a refusal names the test, the target and the two ways out. It derives from `BaseException` rather than `Exception`, which is the difference between a guard and a suggestion: the research clients retry under `except Exception`, and a refusal they could swallow would restore the hazard. No dependency was added - `pytest-socket` is not in the project, and the guard is one fixture and five patched call sites in a file that already exists. The block is total rather than remote-only, because a rule with an exception nobody can see is not a rule. Running the suite under it exposed **zero** inert stubs, which is the honest result and not a null one: the class was found once, fixed once, and is now closed by construction rather than by inspection. What it did expose is that **two files in the unit tier were integration tests** - `test_wdk_identity.py` and `test_saved_strategy_consumers.py`, ten tests that read and write the database - and they have moved to `tests/integration/`, so no production test carries the opt-in marker at all. **2,058 unit tests pass with every socket refused**, ten of them covering the guard, including that `except Exception` cannot swallow it and that `AF_UNIX` is not the network. Two limits are recorded rather than papered over: collection-time downloads happen before the fixture runs, and a C extension holding its own socket is not covered. The [verification-gates convention](conventions/verification-gates.md) carries both, plus `ruff format --check src/`, which does not overlap `ruff check` and was silently drifting on eight files.

* **Four deferred minors from the parameter-resolution and phyletic-contract ledgers, closed.** A `profile_pattern` that states one species code twice was taking the "not a census pattern" wording, which sends the reader to look for a malformed token that is not there; `_read_census` now returns the repeated code beside the states, and the 422 names it and quotes the two ways to state it once. Both paths to the wire raise it: the expansion path and `_normalize_parameters`, which reaches WDK without expanding. The unreadable-tree fallback in the same function re-parsed the pattern it had already parsed, and now encodes the states in hand. [WDK-PARAM-008](wdk/rules/parameters-and-vocabularies.md) anchored at `domain/parameters/values.py:to_wire`, which is not where the substitution comparison lives; it now anchors at `services/catalog/wdk_substitution.py:substituted_params`, and the enforcing test is unchanged. The `_word_weights` docstring in `param_sheet.py` claimed a rare word "must outweigh any number of common words", which the arithmetic does not do: a word `n` labels hold is worth `1/n`, so a unique word is worth 1.0 and three words of weight 0.5 beat it. The comment now states that bound. Left alone and recorded here rather than half-done: `_vocab_signature` in `param_dag.py` is recomputed per call, and memoizing it is not the two-line change it looks like, because `ParameterInfo` is a mutable Pydantic model that is neither hashable nor safe to key by identity, and the dominant cost is `vocabulary()` itself, which three of the same call sites invoke directly.

* **The half of a criterion nobody wrote into is now switched off rather than asked about, and the half that widens the search is refused.** A `radio-params` pair is two required parameters one query ORs, so the intuition that filling both narrows the search is exactly backwards ([WDK-SITE-007](wdk/rules/site-model-params.md)). `set_criterion` reads the pair off the search definition - the same cached read the phyletic derivation uses, so it costs no extra GET - and binds `N/A` into the free-text half of every declared pair. A criterion written into the free text comes back as a retry that names the pair, says the vocabulary half cannot be switched off and quotes its default, lists the vocabulary entries nearest to the value with the wildcards stripped, and sends a wildcard to `get_parameter_options(query=...)` to be expanded into the entries it covers. The off value is reported in `defaulted_params`, so the user is told about a value the request never stated. Measured on plasmodb.org for *P. falciparum* 3D7: `ec_number_pattern=2.7.-.-` beside `ec_wildcard=N/A` returns **364**, and so does the published default `2.7.11.1` beside `2.7.*`, because that wildcard happens to cover the default; `2.7.11.1` beside `N/A` returns **136**, and beside `*protease*` returns **141** - the 133 protein kinases of the default carried into a search asking only for proteases. Two live behaviours this replaces: a turn that bound `ec_wildcard=2.7.*` next to a default it did not choose, and a turn that left it null and got an open slot, because the walk refuses to inherit a free-text default. The FRAME procedure states the same rule, the resolver bench arm records a refused free-text half and continues so the guard is measured, and the rule is `ENFORCED`, which empties the `SILENT` column for the third time: **32 of 83 untested, all of them HARD or CONTRACT.**

* **The search whose criterion nobody could state now states it once.** `GenesByOrthologPattern` carries one criterion - which species must have an ortholog and which must not - in three parameters: two visible free-text lists the query never reads, and a hidden required SQL `LIKE` pattern that is the only one it does read. The model could propose the lists and could not touch the pattern, so the pattern came from `initialDisplayValue`, which is `hsap=1T`, a well-formed expression in a different parameter's grammar on a different site. **The two lists are now the proposal, the pattern is derived from them, and all three are written together.** The sheet gives both lists the clade tree as their vocabulary, so the model names species and clades by code or by label; `derive_phyletic_overrides` resolves them against that tree, pushes each clade down to the species the census holds, sorts the tokens into census order, and returns the pattern beside the two canonical lists for `set_criterion` to bind. An unknown term is a retry naming the nearest labels, a code in both lists is a conflict, and two empty lists are a retry rather than a binding - the bare `%` matches every census, so it reads as a phyletic answer and is not one. Live on plasmodb.org for *P. falciparum* 3D7: the derived `%hsap:N%pfal:Y%` returns **3,347** genes, `%pfal:Y%` returns 5,389, and the published default returns **0**. On the 20 gold strategies, 332 parameters, the propose arm moves from 285 exact / 18 wrong to **288 exact (stated 226, defaulted 62) / 15 wrong**, questions and unset values unchanged at 20 and 9, with the pattern and both lists exact on both gold steps of that search; the one wrong value left there is the organism strain, which is a model choice. One live turn bound the same three values after a single retry that named the nearest labels. Deleted with the work: `_build_phyletic_tree`, `_expand_entries`, the quantifier tokens and `is_census_pattern` from the wire layer, which now reads a value through `_read_census` and refuses a code that states two states; `integrations/veupathdb/phyletic_tree.py:phyletic_tree_of` is the one tree builder and the sheet, the binding and the wire guard all use it. [WDK-SITE-005](wdk/rules/site-model-params.md) and `WDK-SITE-006` are `ENFORCED` by backend tests, so the untested count is **33 of 83** and the `SILENT` column is unchanged at one. Recorded as [the two lists are the proposal](decisions/phyletic-lists-are-the-proposal.md). [The backlog item](backlog/hidden-required-default-chooses-the-science.md) keeps only its unmeasured tail: whether the hidden defaults on the other 181 searches return rows.

* **Two findings that work produced on the way, both kept.** First, "display purposes only" is a statement about the query and not about the metadata read: the contextual `POST` for that search answers **500** when the context carries `organism` and `profile_pattern` and omits the two structural maps, and either map alone is still a 500, while both together are a 200 with `validation: {level: SEMANTIC, isValid: true}`. Every hidden parameter that allows empty now goes into a metadata read's context at its published default, by shape rather than by name, at all three read sites. Second, that fix could not land until substitution detection was corrected. When the contextual read fails, the client falls back to the static `GET`, whose echoed values are the published defaults, so every value the caller set differs from the echo and none of those differences is WDK substituting anything ([WDK-PARAM-008](wdk/rules/parameters-and-vocabularies.md)). The comparison is now against the canonical values actually sent, a vocabulary echo is compared as a set, a hidden parameter this read supplies is never reported, and `values_were_read` gates both the comparison and the validation verdict when the read fell back.

* **Fixed: `PF00069` was not `PF00069 : Pkinase`, and the retry pointed away from it.** A typeahead vocabulary writes its terms as `<accession> : <label>`, and a proposal of the accession alone was refused as off-vocabulary. The nearest-entry list that came back was ranked by character similarity, so it offered `PF00569 : ZZ` and `PF00169 : PH` and not the one entry the accession identifies; two retries later the model changed `domain_database` to `INTERPRO` and bound `IPR000023 : Phosphofructokinase_dom`, which is the wrong science. Three changes, together: `match_exact_option` accepts a proposal that is the leading accession of exactly one entry, and refuses it when two entries share it; the nearest entries lead with the ones the proposal starts, so `PF0006` answers `PF00069 : Pkinase`; and the sheet pins an entry whose accession appears in the request as a word, not only one whose whole term appears. A shared accession is refused by naming the entries that share it, so the ambiguity is recoverable in the same turn rather than reading as an absent value. An accession holds a digit and is at least four characters, so a leading word such as `Plasmodium` is a label and matches nothing. [The decision](decisions/unmatched-accession-stops-the-chain.md) is amended again.

* **Done and removed: parameter resolution had three proposers and no contract.** There is one now, and it is the model. `set_criterion` with no `params` returns a parameter sheet - every visible parameter with its type, help, default, bounds, dependency and vocabulary - beside a `params_template`, the object to copy and fill, and the next call takes a value or an explicit null for each of them. A second sheet for the same criterion carries the parameters without the vocabularies, which the model already holds. The walk validates and binds: unknown names and off-vocabulary values are did-you-mean retries, numbers and JSON-encoded lists are coerced, a null binds the disclosed default or opens a slot, a dependent whose vocabulary changes under the bound parents comes back to be decided once, and a numeric parameter left null while the criterion states a quantity comes back unread rather than defaulting in silence. Measured on the same 20 gold strategies, 332 parameters: **exact 285 (stated 222, defaulted 63), wrong 18, asked 20, unset 9**, against a floor of **154 exact (all of them defaults), wrong 48, asked 115, unset 15** for the walk with no proposer at all. The four arms recorded before this work - 168/48/101 as the recorded baseline, 184/58/75 for production with the resolvers discarded, 205/62/56 with the resolvers allowed to bind, and the experiment harness at 255/54/14 and 276/27/20 - were measured before a held-back numeric default counted as a question and before the scorer compared wire values by kind, so they are history and not a column beside the new floor. Deleted with the work: both resolver agents and `ai/agents/vocab_resolver.py`, `ValueResolvers`, `bind_inferred`, `Provenance.INFERRED`, `map_intent_to_value` and every rule in it that read English, `narrow_candidates` and `vocab_narrowing.py`, the dead `resolve_search_parameters` and `get_parameter_dependencies` tools with the `DagResolution` half of the walk, and `organism_scope`, `direction` and `param_overrides` from the tool surface. The sheet does **not** embed, which is the one place the design changed under measurement: embedding a 5,461-entry vocabulary takes 238 seconds in the api container, so a shortlist is by word overlap with the goal, with anything the request names verbatim pinned. Recorded as [one proposer, one validator](decisions/one-proposer-one-validator.md); [the 2026-08-10 resolver decision](decisions/the-model-reads-the-request-not-a-cosine-score.md) is amended rather than deleted, because embeddings still may not decide a value - and its evidence section had claimed a profileset "binds correctly" that never bound, which is now struck. [An unmatched accession](decisions/unmatched-accession-stops-the-chain.md) and [a value the request already states](decisions/a-value-in-the-request-is-not-a-question.md) keep their principles and lost their rules; both now name what carries them. The live DeRisi prompt then built end to end, 16 steps, with zero invented parameter names, on the fourth run - the sheet arriving from `set_criterion` itself and the repeat losing its vocabularies are the two changes between that run and the third.

* **Also from the measurement: a search can offer the same criterion twice, and both halves are ORed.** [WDK-SITE-007](wdk/rules/site-model-params.md). ApiCommonModel declares the pairs in a `radio-params` property list - `go_typeahead`/`go_term`, `domain_typeahead`/`domain_accession`, `ec_number_pattern`/`ec_wildcard`, `metabolic_pathway_id_with_genes`/`pathway_wildcard` - and the property is published on the wire. The intuition a form gives is that filling both narrows the search; the query unions them. Measured on plasmodb.org for *P. falciparum* 3D7: `GO:0004672` alone returns 105 genes and the same pick beside the wildcard `*kinase*` returns **192**; `PF00069 : Pkinase` alone returns 81 and beside `*kinase*` returns **144**. Both halves are `allowEmptyValue: false`, and two of the published defaults are refused by the search that published them, so there is no off position - only a value that matches nothing. The worst case is `GenesByEcNumber`, whose typeahead half cannot be empty and whose published default is a real EC number: a search asking only for proteases carries 133 protein kinases and nothing in the response says so. The rule says which half is authoritative; the guard that enforces it is the entry above.

## 2026-08-16

* **The resolver bench was scoring the wrong input, and the design turned out to be sensitive to exactly that.** Every gold strategy carries `prompts.precise` - the request a user would type - and the bench loaded it but never used it, because it took the step's listing label whenever there was one. So the whole recorded baseline described resolution on a short phrase rather than on the shape production hands it. Feeding the request instead moves wrong values from **48 to 68** and makes the heuristics assert that the request stated **23** values it never stated about that parameter. More of the user's own words makes them more confident and less correct. First cut taken from that: an identifier in the text was written into every vocabulary-less param of a search, because only a *sibling's vocabulary* counted as a rival home - one `GO:0016301` landed in both a free-text query and a document-type selector, each claiming the request said so. It now binds only where one param can hold it, the rule the numeric slots already follow. **Wrong 68 to 58, exact 173 to 183, no new questions**, and the label baseline is unchanged.

* **Fixed: the published `profile_pattern` default reached the query unexamined.** The census guard returned early unless the value was wrapped in `%`, and WDK's own `initialDisplayValue` for `GenesByOrthologPattern` is `hsap=1T` - unwrapped, and an expression from OrthoMCL's grammar. So the one value most likely to be wrong was the one value nothing checked, and it returns an empty answer with HTTP 200. A pattern that is not built from census tokens is now a 422 naming the two tokens that work.

* **Fixed: a spec could be `ready_to_build` and still not convert.** Readiness reports that every criterion is bound and a structure exists; it does not run the conversion. A nine-criterion turn passed it, then died on `ValueError` after FRAME had spent the expensive part of the turn. The conversion failure is now a retry that names the structure, so the turn survives and the Lead can fix it.

* **A value the search chose is now visible as one.** `defaulted_params` was recorded per criterion and shown to the framing agent, but never reached the Ledger or the browser, so the only account of an assumed value was whatever the reply chose to narrate. The Ledger's criterion card now marks those params as assumed.

## 2026-08-15

* **Fixed: leaving a conversation and returning lost it.** Two independent defects, both found in the browser and both fixed with tests. (1) The transcript query was cached with `gcTime: Infinity`, so the list a mount read was the list every later mount got. A conversation created in this tab reads its transcript before the first turn exists, gets a 404, and caches the resulting empty list forever - so returning from the workbench, or from another chat, showed an empty conversation and only a page reload recovered it. The transcript is now re-read per mount. (2) A running turn was never re-attached, because `resume` was derived from `allowMissing`, which compares the URL id to a UUID the tab generated. Every conversation starts from a locally generated id, so that comparison stays true for the life of the tab and the chat kept treating a real conversation as an uncreated draft: no resume request was issued at all, the composer showed Send while the turn ran, and a reload appeared to fix it only because it minted a new UUID. Resumability is now its own flag - the URL names a conversation - and it is captured at mount, so the draft-to-URL rewrite cannot open a second stream over the live one.

* **Fixed: a durable task finished and the answer never appeared.** A turn that defers to a durable tool ends its own response at the interrupt, by design. The worker then runs the task, resumes the graph, and writes the rest of the turn to the event log - but nothing told the page that was still open to read it, so the user was left with a progress bar at 100% and no conclusion. The whole final message existed in the database the entire time and appeared only after navigating away and back. Three things had to hold at once, and finding the third took two failed attempts that are worth recording. (1) A trigger: the task's own progress stream now announces when the task settles, and the card re-attaches the chat. (2) The announcement cannot depend on the terminal chunk alone - a stream opened while the task ran can end without one, while a stream opened after it finished always gets it on connect, which is why the reload path looked healthy and the live path did not. It now announces when the stream ends, whatever the reason. (3) The re-attach then failed silently, because the event log stores the user's own message so a snapshot can rebuild the transcript, and that row is not an AI SDK chunk. The transport calls `controller.error` on anything its schema rejects, so the replay died on its first row, before the assistant's first token. The transport now drops that row rather than failing on it. The same `controller.error` path explains a `reading 'state'` TypeError seen earlier.

* **Fixed: two Lead tools turned a wrong argument into a dead turn.** Asking for control tests on a combined step made the Lead pass `Combine` - the label the strategy view renders for a combine node - as a variant's `search_name`. WDK rejected it once the run reached the server, so the turn spent itself and reported no metric and no way forward. Both variant tools now refuse a combine step before running anything and name `run_control_tests_on_step`, which takes a step id, instead. Separately, `import_control_ids_from_strategy` and `compare_variants_scored` parsed their id arguments with `UUID()`, so a WDK strategy id - which the conversation shows everywhere - raised `ValueError` and ended the turn with `badly formed hexadecimal UUID string` in the user's face. Both now answer with a retry that names the value they got and the kind of id they want.

* **Fixed: an invalid phyletic state emptied a strategy in silence.** A plain ToxoDB request for kinases with no ortholog in *C. parvum* framed correctly and then wrote `%cpar:0%` into `profile_pattern`. The census tokens are `code:Y` and `code:N`; `:0` matches nothing, WDK answers 200 with a count rather than an error, the ortholog step returned 0 and the whole intersection collapsed to 0. Opening that step in the editor read "0 included, 0 excluded, 864 unconstrained", which is the same symptom the widget used to produce before its encoder was corrected - so the grammar was fixed on the widget side and not on the agent side. The code half of each entry was already validated against the site's vocabulary, and `cpar` is real, so nothing objected. The state half is now validated too and an entry that states neither presence nor absence is a 422 naming the entry and the two tokens that work. This is the hazard `WDK-SITE` was written for, reached from an ordinary prompt rather than from a hand-made pattern.

* **Fixed, both halves: an edit made outside the flow that produced an artefact never reached the artefact.** A parameter changed in the graph editor moved a step from 3,259 to 897 and the root from 15 to 3. Two things then disagreed with reality, and they needed opposite fixes, which is the part worth carrying: **WDK owns the strategy**, so anything stored here is either stamped with when it was true or re-read from the server. (1) The Ledger's Build tab kept showing 3,259 and 15 marked `ok`, and the Lead quoted 15 as current while asserting nothing had changed. The Ledger is a record of what the build did, so it stays frozen and now says its counts are from the build. The reason its staleness check never fired is that `detect_build_staleness` compared the recorded counts against `live_step_counts`, which read the same persisted AST the build wrote - **a cache compared with itself, unable to detect any edit by construction**. The live side now reads WDK, and `live_step_counts` is gone. (2) A gene set went the other way: it stores its member ids and rendered its results by re-reading the step it came from, so the panel showed "15 genes" beside a table of 3, and an enrichment saved against it stopped describing its own input. Membership is what the set stores, so results are now reported from a step materialized from those ids. WDK refuses to run a step belonging to no strategy, so the materialized step is held by an internal one, cached by the membership hash.

* **Verified in the browser, not reproduced: the two open agent items.** A request stating "top 10 percent" bound `min_expression_percentile` to 90 against a declared default of 80, selected the trophozoite sample window, and asked no questions under an explicit use-defaults instruction. Both [numeric intent](backlog/numeric-intent-ignored-then-reported-as-honoured.md) and [use-defaults](backlog/frame-ignores-use-defaults.md) are held open pending their original repro, since this search carries two numeric slots and so does not exercise the single-slot rule that was added for them.

## 2026-08-14

* **A hidden parameter was choosing the science, and the bundle covered none of it. Added `WDK-SITE`, a rule family whose falsifier is ApiCommonModel rather than WDK.** `GenesByOrthologPattern.profile_pattern` is hidden, required, 4000 characters of free text, and it is a **SQL `LIKE` pattern** matched against a colon-joined species census - `%code:Y%` for present, `%code:N%` for absent, `%` being the wildcard rather than a separator. Nothing upstream states that grammar in prose; it was reconstructed from [the query's own SQL](wdk/rules/site-model-params.md) and confirmed by measurement on plasmodb.org and toxodb.org. Four things follow and none of them is a refusal: a wrong pattern is not refused, tokens out of ascending code order match nothing (`%atum:Y%bant:Y%` returns 387 and the reverse returns 0, on three separate pairs chosen because tree order and code order disagree), a clade code matches nothing, and **WDK's own published default returns nothing** - `initialDisplayValue` is `hsap=1T`, which is a valid expression in OrthoMCL's *different* `phyletic_expression` grammar (it returns 9691 groups there) and is meaningless here. Six `WDK-SITE` rules plus [two `WDK-PARAM` rules](wdk/rules/parameters-and-vocabularies.md) for the general lesson: `initialDisplayValue` is whatever the spec holds, the model default behind it is stored by [a setter whose javadoc promises validation and whose body does not](wdk/rules/parameters-and-vocabularies.md), and `isVisible: false` is presentation only - a grep of the whole WDK repository finds `Param.isVisible()` read in exactly two places, one of which just publishes it. The new explainer is [site-model parameters](wdk/model/site-model-parameters.md); `scripts/check-wdk-rules.mjs` learned the `SITE` namespace and its suite went from 27 tests to 28. ApiCommonModel had been pinned since the bundle was created with a note admitting nothing cited it; that note is now deleted rather than softened.

* **Filed two defects the research found, both PathFinder's rather than WDK's.** The phyletic profile widget writes a pattern that matches nothing is ranked first in the WDK section because the trigger is an ordinary user action: pick species in the step editor, submit a valid form, get zero genes and no error. `encodeProfilePattern` emits `code>=1T` / `code=0T` - OrthoMCL syntax, measured at 0 on both sites - and three separate faults have to be fixed together, since the token grammar, the ordering and the clade-versus-leaf expansion each independently yield zero. Its own test file asserts `pfal>=1T` literally in three places, so **the test pins the defect and has to be rewritten rather than patched around**; `decodeProfilePattern` cannot read the correct form either, so a step built by PathFinder's own backend opens in the editor reading "0 included, 0 excluded". Second, [filling a hidden required parameter from `initialDisplayValue` chooses the science](backlog/hidden-required-default-chooses-the-science.md): the fill is the right shape - WDK demands these parameters and the model cannot supply them - and the value it fills carries no guarantee at any layer. The same belief is written into `param_dag.py:_is_free_text_query` as a comment, and both have to move together.

* **Review caught the worst of it, and it made the finding worse rather than smaller.** The query is a `UNION`, and its **first** branch never touches `LIKE`: it inspects the pattern *string* with `not like '%:Y%'` and, when the string carries no `:Y`, returns every ortholog-less protein-coding gene for the selected organism. So "a wrong pattern returns zero" was the wrong statement of the hazard. **A wrong pattern returns whatever that branch yields for that organism**, which is zero here and is guaranteed nowhere - and a plausible non-zero count from a meaningless pattern is the worst answer this product can give. Four of the measured forms carry no `:Y` (`hsap=1T`, `hsap>=1T`, `hsap=0T`, prose) and their zeros are a property of the data; the two `:Y`-bearing zeros (`%zzzz:Y%`, `%MAMM:Y%`) are intrinsic. **Every string PathFinder's widget can emit lacks `:Y`**, so it never reaches the matching branch at all. I isolated that branch with `hsap=1T` on **eleven organisms across both sites** and it was empty on all eleven - recorded as a limit of the measurement, not as a refutation. A residue argument that had been offered as reassurance was deleted rather than repaired: it was vacuous, since both patterns it compared lack `:Y` and so both include the same branch. Also from review: `WDK-SITE-001`, `-002`, `-004` and `-005` are **live-only** - `profile_string` is built outside all four pinned repositories - so each now says so in the rule itself, and [sources.md](wdk/sources.md) gained the mirror image of its source-only ledger, with a re-run instruction per rule. A rule with no upstream and no re-run is unfalsifiable, which the charter forbids. Vocabulary counts were re-derived with `jq`: 865 terms, 818 lowercase, 47 uppercase, no duplicates, every term four characters except the three-character root `ALL` - so `three_letter_abbrev` is wrong about its own contents for 864 of 865 rows.

* Recounted the rule bundle honestly afterwards. **81 rules, 45 UNENFORCED**, and the number that matters is that the `SILENT` untested column went from **0 to 5**: four of the new site rules and the `initialDisplayValue` rule. The backlog item that claimed the `SILENT` class was closed no longer claims it.

## 2026-08-10

* **Read what WDK already answers, and stop reporting numbers it did not give.** Five changes, all from the pinned rule set rather than from a failing run. (1) One named count: the two count paths returned different quantities, because `estimatedSize` tracks `displayTotalCount` while the fallback read `totalCount`, and only the view pair matches the records returned. (2) The four counts became optional, so an absent count can no longer read as a scientific zero; the response schema and generated types were made honest rather than kept convenient. (3) A negative `estimatedSize` now reads as no count instead of surfacing as a gene count. (4) The validation bundle returned by the search endpoint is read instead of discarded, honouring the rule that a false verdict at level `NONE` means nobody checked. (5) WDK reports which values it substituted, so provenance is now corrected by the server that already knew it. Writing the first rule test also found a live contradiction: the model was told to send the synthetic tree root as a select-all shortcut, and the canonicalizer rejects it, as WDK does. Also closed: the delayed-result sentinel is recognised by shape and retried.

* **Added `docs/knowledge/wdk/`, a falsifiable WDK reference, and a gate that fails when its evidence stops resolving.** Four groups - [rules](wdk/rules/), [model](wdk/model/), [rest](wdk/rest/) and [pathfinder](wdk/pathfinder/) - carrying **73 assertions** about WDK, each with a GitHub link pinned to a 40-character sha and an anchor naming the PathFinder symbol it governs. Most are confirmed live on plasmodb.org and toxodb.org rather than reasoned about; six are source-only and [sources.md](wdk/sources.md) lists them by name. The new gate `scripts/check-wdk-rules.mjs` (pre-commit and CI, with its own fixture suite) fails on an unpinned citation, a moved anchor, a named test that no longer exists, and prose citing a withdrawn rule. Every `ENFORCED` and `PARTIAL` status was then audited against one standard - would the named test go red if the rule were broken - which downgraded three: [WDK-VOCAB-002](wdk/rules/parameters-and-vocabularies.md), whose test drove the canonicalizer while its anchor is a second, untested expansion in `integrations/`, and [WDK-STRAT-002 and WDK-STRAT-003](wdk/rules/strategies-and-steps.md), whose hypothesis trees came out of `flatten_tree` and so satisfied single-rootedness and reachability by construction. The honest tally is **8 ENFORCED, 9 PARTIAL, 56 UNENFORCED**, and the number that matters is that **19 `SILENT` rules have no test** - the class where WDK answers 200 and the science is wrong. Filed as one item, 56 of the 73 WDK rules have no test, which ranks the conversion `SILENT` first and carries the open questions the research left behind, including a `JSESSIONID` belief that did not reproduce on three live probes.

* **Root-caused the recurring crash, correctly this time, and fixed the seam behind three earlier bugs.** Pushed back on: the same issues kept returning, which was right. Two findings. (1) `No tool invocation found for tool call ID` is thrown by the Vercel AI SDK **client**, not OpenAI, when a `tool-output-error` names a call the client never saw announced -- it never reaches a backend log, which is why it read as a silent provider rejection. [no-openai-item-ids](decisions/no-openai-item-ids.md) misattributed it and now carries a correction; the real one is [chunk suppression follows the call, not a list of chunk types](decisions/suppression-follows-the-call-not-the-chunk-type.md), since fixed and verified in the browser. (2) "Get a search's parameters under a context" had **no owner**: six call sites, four exception types caught, five recoveries, two with no handling at all -- and the two with none are exactly where B16, the default-vocabulary read, and the abandoned criterion landed. One owner now: [a contextualized param view is an enrichment](decisions/contextualizing-params-is-an-enrichment.md). Verified against the live 500: WDK fails, we log once and return all 6 params.

* **The multi-criterion mega prompt, in the browser, on a real account.** No crash, on either the Portal or PlasmoDB -- the turn that used to die on `No tool invocation found for tool call ID` now completes. On PlasmoDB, FRAME operationalized all five criteria (four kinase routes as a UNION, the non-syntenic orthology transform, the trophozoite mass-spec-or-microarray alternative, Broad 3K variation, and phyletic specificity) for $0.03. It then declined to build, because one criterion's search 5xx'd -- correct behaviour, wrong conclusion: the value WDK 500s on the refresh endpoint runs fine (a non-empty result). That 5xx has since been root-caused and fixed at the seam behind it -- see [a contextualized param view is an enrichment](decisions/contextualizing-params-is-an-enrichment.md). Two claims the same run made on the Portal were checked and are Portal artifacts: `GenesBySnps` genuinely does not exist there, while `GenesByOrthologs` does and retrieval simply missed it among 2,356 searches.

* **Done and removed: the dependent-param false rejection.** Two independent defects, both proven on live WDK. The tool was reading a dependent vocabulary under WDK's DEFAULT parents, so the model saw HB3's time points for a criterion bound to 3D7 and correctly reported hours that do not exist in what it was shown ([decision](decisions/a-dependent-vocabulary-is-read-under-its-parents.md)). Separately, a multi-pick answer was serialized to wire form at the tool boundary, so the whole array counted as one option and the model was told its own correct answer was invalid ([decision](decisions/an-override-list-stays-a-list.md)). Same prompt, before and after: 4 `set_criterion` failures to **0**, and the built strategy built (a large result protein-coding, intersected with a large result top-percentile trophozoite and 81 `PF00069` kinases, giving the intended genes). Filed from that run: [a numeric bound stated in the request is ignored, then reported as honoured](backlog/numeric-intent-ignored-then-reported-as-honoured.md).

* **Fixed: an unmatched accession stops the chain.** "InterPro domain PF00069" bound `IPR000023 : Phosphofructokinase_dom` and returned almost nothing with verification reporting success, because the accession is Pfam and the dependent vocabulary was IPR-only. Live re-run now binds `PF00069 : Pkinase` and the intended genes. See [decisions/unmatched-accession-stops-the-chain.md](decisions/unmatched-accession-stops-the-chain.md).

* **Fixed: numeric defaults were being discarded.** WDK types numeric bounds as `string`, so the free-text guard (which exists to stop `GenesByText` inheriting `*reductase`) swallowed their declared defaults and asked five needless questions on `GenesBySnps`. That criterion now resolves with zero open slots. See [decisions/numeric-default-is-not-an-example.md](decisions/numeric-default-is-not-an-example.md).

* **Fixed: a parent term is a selection.** The organism tree matched only leaves, so a step scoped to "Plasmodium falciparum" (a node with 20 children on live WDK) rendered as "0 of 62 selected", and edits filtered the raw value so unchecking a leaf did nothing. See [decisions/parent-term-is-a-selection.md](decisions/parent-term-is-a-selection.md).

* **Fixed: the strategy structure is a tree.** `set_structure` left-folded a flat list, so `(B UNION C)` on the secondary input was inexpressible; the Lead correctly refused to flatten it. The nested form recovered a gene the flat form lost (3 vs 2). See [decisions/structure-is-a-tree.md](decisions/structure-is-a-tree.md).

* **Root-caused and fixed the tool-call-id crash.** Not orphaned tool pairs (`pair_tool_calls` logged zero corrections); it was `openai_send_reasoning_ids`, which defaults to True for reasoning models and echoes provider item IDs back from a history we rewrite. See [decisions/no-openai-item-ids.md](decisions/no-openai-item-ids.md).

* Real-account browser testing on a multi-criterion reference strategy. Fixed [build_strategy's unactionable retry](decisions/build-retry-must-be-actionable.md). Filed three findings: the tool-call-id crash on complex turns (since root-caused and fixed, see above), [FRAME ignoring an explicit defaults instruction](backlog/frame-ignores-use-defaults.md), and the organism param rendering as unset (since fixed, see above).

## 2026-08-09

* Done and removed: **FRAME turn cost**. The 40K bar was arithmetically impossible, but investigating it found a real defect: elision made agents re-fetch data they already had (a large share of tool calls in one turn). Fixed by keeping a digest. See [decisions/elision-caused-refetching.md](decisions/elision-caused-refetching.md). **Backlog is empty.**

* Done and removed: **FRAME to BUILD to VERIFY migration**. The flip was already complete in code; what remained was prose describing the deleted architecture to the model, and verification. Proven end to end on live WDK ( 590/598 transcripts, verification passed). Two decisions recorded: [prompts-match-the-architecture](decisions/prompts-match-the-architecture.md) and [strict state + flushed checkpoints](decisions/no-checkpoint-truncation.md) (reversed once the compat shim was pointed out). The live run also exposed a real cost gap, since investigated and fixed: [elision-caused-refetching](decisions/elision-caused-refetching.md).

* Removed as stale: **experiment controls and scoring (Phase 2b)**. Already built, wired, and tested. The real gap was discoverability: the unscored comparison tool never named its scored counterpart, and nothing guarded that either stays registered. See [decisions/capability-must-be-reachable.md](decisions/capability-must-be-reachable.md).

* Done and removed: **test fixtures should not cast to their type**. 32 casts removed, 10 lying fixtures fixed (including one using a raw string where the API returns a typed `ParamValue`), shared factories added. See [decisions/fixtures-are-built-not-cast.md](decisions/fixtures-are-built-not-cast.md).

* Done and removed: **devtool reports handled issues as anomalies**. The `silent_*` detectors now read the reply, and `RunCapture` no longer discards it. See [decisions/silent-anomaly-must-read-the-reply.md](decisions/silent-anomaly-must-read-the-reply.md).

* Closed as won't-do: **restore faker and msw generation**. Reproduced at 586 type errors, traced to a hardcoded `Partial<T>` override shape no plugin option controls, and concluded the output conflicts with the real-data testing rule. See [decisions/no-faker-or-msw-generation.md](decisions/no-faker-or-msw-generation.md). Replaced by the narrower fixtures-should-not-cast item, which is what the drift was actually about and which is now done: [decisions/fixtures-are-built-not-cast.md](decisions/fixtures-are-built-not-cast.md).

* Removed as stale: **JSONValue name collision**. `JSONValue` had already been deleted; the three remaining names (`JSONObject`, `JSONArray`, pydantic's `JsonValue`) do not collide even case-insensitively, no post-generation casing patch exists, and generation is byte-identical across consecutive runs. Investigating it did surface a live break, recorded in [decisions/one-way-to-generate-types.md](decisions/one-way-to-generate-types.md).

* Done and removed: **step creation takes spec objects**. `create_step` and `create_transform_step` already took `NewStepSpec`; only `create_combined_step` was the outlier, which is why it carried a `PLR0913` noqa. It now takes `CombinedStepSpec` and the noqa is gone. Added [decisions/boolean-operator-is-a-type.md](decisions/boolean-operator-is-a-type.md).

- Bundle created. Seeded from the R1-R6 graph rewrite session: the backlog that survived it, and the five decisions taken during it that are not recoverable from the code.

* **The DeRisi empty-branch item was retired by measurement rather than by a fix.**
  Its three candidate causes were tested live on plasmodb.org against
  `GenesByMicroarraypfal3D7_..._Percentile`, holding everything else constant:
  `any_or_all=any` at the top 10 percent over the fourteen trophozoite hours
  returns **871**, `all` returns **233**, and the looser top-20-percent forms
  return 1741 and 486. None is zero, so neither the any/all binding, nor the
  percentile tightening, nor the sample count empties the branch. The two ways
  to bind it wrongly both fail **loudly**: a sample set read under one
  profileset and sent under another is a 422 naming the terms that do not exist
  there (`23 Hour`, `29 Hour` are 3D7-only), and a branch term instead of leaves
  is the `countOnlyLeaves` 422. The step in the strategy that prompted the item
  reads **942**, not 0. The zero in that conversation was the phyletic-profile
  step, which is [WDK-SITE-002](wdk/rules/site-model-params.md) and understood.
  What survives is smaller and already filed elsewhere: that step bound
  `profileset_generic` to WDK's default `DeRisi HB3 Smoothed` rather than the
  3D7 set the request named.

* **Seven backlog items closed in one pass, and three of them by measurement
  rather than by code.** The orphan-delete ordering, the lossy search-config
  write, the verb-blind POST retry, the one-sided range, the two analysis-status
  defects and the logout credential were fixed with tests. The DeRisi empty
  branch, the doomed auth refresh and half of the FRAME budget item turned out
  not to be defects: the first does not reproduce (871 genes live), the second
  was already fixed and tested, and the third's "partial progress is discarded"
  half was already handled - only its report said otherwise.

  The three heuristics tried against the parameter-resolution benchmark were all
  refuted by it, which is the benchmark doing its job: holding a numeric default
  back whenever the request mentions a number costs 14 correct answers to save
  2, and grouping the ends of a range costs 7 to save none. What shipped is the
  one form that scored at parity on exact and one better on wrong.

  `SILENT` is at zero unenforced again, 30 of 31, having been reopened by the
  five site-model rules the phyletic research added.

* **The wire protocol got a consumer, and the consumer got a suite that fails
  when the page changes.** `@pathfinder/assistant-client` is built from
  `PROTOCOL.md` and not from the app it replaces: a dependency-free core that
  reads the frames section 3 defines, refuses the shapes it does not, resumes on
  the cursor rule of section 4 and reduces a turn by the rules of section 9;
  one module that subclasses the AI SDK's transport, because `useChat` takes a
  class; and one named `legacy`, because the durable-task endpoint frames a
  third shape the protocol tells a client to reject. The app deleted five
  modules and imports them instead, so there is one reduction and one framer in
  the repository rather than two.

  The gate is a generator and a comparison, and it was measured rather than
  asserted: adding one row to the document's chunk table failed the sync test
  with `+ "checkpoint"`, and regenerating the capture then failed the reducer
  test with the same word. A protocol change now has two ways to be caught and
  no way to be silent.

  Three things the port found, all of them in code that was passing its own
  tests. A chunk kind the SDK's schema did not know killed the whole turn,
  which is exactly what section 10's additive rule exists to prevent - the
  client now drops what its protocol version does not define and hands the rest
  on. The snapshot reader knew one of the three log envelopes, so a
  `system-message` or `assistant-message` row would have reached a reducer that
  had no place for it. And the cursor advanced only at turn boundaries for a
  reason that lived in a comment; it is now a function with a name and a test
  that says a mid-turn cursor names a chunk whose `start` the client would not
  have.
