---
type: Plan
title: "Batch 1: protocol, runtime, client, tool summaries"
description: The wire learns one additive data part - a tool call may carry a one-line summary of what it did - and PathFinder's tools each write their own, at the tool, where the numbers are. The two conforming reducers implement the rule, and the client gains buildTrace, the one place the grouping rule lives.
tags: [thread, pathfinder, plan, batch, protocol, assistant-core, assistant-client, tools]
generated: { by: claude-code/opus-5, at: 2026-08-29T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-29T00:00:00Z }
status: accepted
---

# Batch 1: protocol, runtime, client, tool summaries

**Goal:** after this batch the wire carries, for every tool call PathFinder
makes, one sentence saying what that call did, in words and numbers written by
the tool itself. Nothing renders differently yet. Batch 2 draws it.

**Prerequisites:** batch 0 frozen. Its
`packages/assistant-client-ts/tests/acceptance/thread/*.acceptance.ts` modules
are this batch's exit gate.

**Read before starting:**

- [overview.md](overview.md) - sections 1 and 2 of the pinned contract are law.
- `packages/assistant-core/PROTOCOL.md` sections 5.2, 6, 9, 10 and 14.
- `packages/assistant-client-ts/src/core/reduce.ts`, `reduceTool.ts`,
  `message.ts`, `chunks.ts`.
- `packages/assistant-core/src/assistant_core/conversation/_chunk_handlers.py`
  and `conversation/stream_parts/core_parts.py`.
- `apps/api/src/pathfinder/ai/tools/durable.py` and
  `apps/api/src/pathfinder/ai/tools/standalone/_eda_stream_parts.py` - the
  metadata path this batch reuses.
- `apps/api/src/pathfinder/tests/unit/ai/test_tool_surface_agreement.py` - the
  enumeration test this batch's coverage test copies.

## The mechanism, decided

**A tool emits its summary as a `DataChunk` on its `ToolReturn.metadata`.**
That path already exists and already works: pydantic-ai's
`iter_metadata_chunks` (`pydantic_ai/ui/vercel_ai/_utils.py` line 171) yields
every `DataChunk` on a `ToolReturnPart.metadata` immediately after the call's
output chunk. The durable path emits its summary from `chunks_from_result`
BEFORE the output chunk instead
(`apps/api/src/pathfinder/ai/tools/durable.py` lines 96 to 116). The producer
rule accepts both, because a reducer addresses a summary by `toolCallId` and
not by position. The EDA tools ride the metadata path today for `data-eda.*`;
the scratchpad tools ride it for `data-scratchpad-updated`; `build_strategy`
rides it for `data-graph-snapshot`.

**A field on `tool-output-available` is not possible.** The AI SDK declares
every tool chunk with `z.strictObject` (`apps/web/node_modules/ai/dist/index.mjs`
from line 5084), and the live stream is parsed by the SDK, not by our reducer:
`DurableChatTransport` re-frames accepted payloads into
`DefaultChatTransport.processResponseStream`. An extra key makes the SDK throw
mid-turn. This is not a preference; it is the reason the shape is a data part.

**The model sees no difference.** `ToolReturn(return_value=X)` puts `X` into
the message history exactly as `return X` does; `content` is the only field
that changes what the model reads, and this batch never sets it. A test proves
it rather than a paragraph asserting it.

## Files

### Implementer A: the wire and the two reducers

**Modify**

- `packages/assistant-core/PROTOCOL.md`
- `packages/assistant-core/src/assistant_core/graph/stream_events.py`
- `packages/assistant-core/src/assistant_core/conversation/stream_parts/core_parts.py`
- `packages/assistant-core/src/assistant_core/conversation/_chunk_handlers.py`
- `packages/assistant-core/src/assistant_core/conversation/_chunk_state.py`
- `packages/assistant-client-ts/src/core/message.ts`
- `packages/assistant-client-ts/src/core/reduce.ts`
- `packages/assistant-client-ts/src/core/reduceTool.ts`
- `packages/assistant-client-ts/src/index.ts`
- `packages/assistant-client-ts/src/protocol/version.ts`
- `packages/assistant-client-ts/src/protocol/captured.json` (through
  `yarn sync:protocol`, never by hand)
- `packages/shared-ts/src/types.ts` (`KnownDataPartKind`)
- `apps/web/src/features/conversation/content/coreDataParts.ts`
- `apps/web/src/features/conversation/content/DataPartRenderer.tsx`

**Create**

- `packages/assistant-client-ts/src/core/trace.ts`
- `packages/assistant-client-ts/tests/conformance/toolSummary.test.ts`
- `packages/assistant-client-ts/tests/conformance/trace.test.ts`
- `packages/assistant-core/tests/integration/conversation/test_tool_summary.py`

### Implementer B: the summaries

**Create**

- `packages/assistant-core/src/assistant_core/graph/tool_summary.py` (lead
  ruling at close: the helper names nothing of PathFinder's, and the pilot's
  boundary test forbids `site_help` from importing `pathfinder.ai`, so the
  helper is runtime code and every assistant returns through the one builder)
- `apps/api/src/pathfinder/tests/unit/ai/tools/test_tool_summaries.py`
- `packages/assistant-core/tests/unit/graph/test_tool_summary_helper.py`
- `apps/api/src/pathfinder/tests/unit/ai/lead/test_sub_agent_stream_summary.py`
- `apps/api/src/pathfinder/tests/unit/ai/lead/test_sub_agent_phase_names.py`

**Modify** (every tool module named in the summary table below)

- `apps/api/src/pathfinder/ai/tools/standalone/catalog.py`,
  `catalog_discovery.py`, `frame_spec.py`, `research.py`, `gene.py`,
  `strategy_graph.py`, `strategy.py`, `strategy_attach.py`, `conversation.py`,
  `execution.py`, `results.py`, `experiment.py`, `optimization.py`,
  `workbench.py`, `workbench_read.py`, `export.py`, `escape_hatch.py`,
  `memory_tools.py`, `think.py`, `variant_comparison.py`,
  `scored_comparison.py`, `control_sets.py`, `eda_catalog.py`,
  `eda_analysis.py`, `eda_compute.py`, `eda_step.py`
- `apps/api/src/pathfinder/ai/scratchpad/tools.py`
- `apps/api/src/pathfinder/ai/lead/lead_agent.py`,
  `ai/lead/sub_agent_dispatch.py`, `ai/lead/edit_dispatch.py`,
  `ai/lead/sub_agent_stream.py`
- `apps/api/src/pathfinder/ai/tools/durable.py`
- `apps/api/src/pathfinder/assistants/site_help/agent.py`

## Interfaces

**Produced by A, consumed by B:**

```python
# assistant_core/graph/stream_events.py
ToolSummaryStatus = Literal["ok", "empty", "warn"]

class ToolSummaryPayload(CamelModel):
    tool_call_id: str
    summary: str
    status: ToolSummaryStatus = "ok"

def tool_summary_event(
    *,
    tool_call_id: str,
    summary: str,
    status: ToolSummaryStatus = "ok",
) -> DataChunk:
    """One line saying what a tool call did. Rides the call's return metadata."""
```

`ToolSummaryPayload` carries a `@field_validator("summary")` that strips,
collapses internal whitespace to single spaces, and refuses an empty string or
one over 120 characters. A tool that writes a bad summary fails its own unit
test, not the turn.

**Produced by A, consumed by batch 2:**

```ts
// packages/assistant-client-ts/src/core/message.ts
export type ToolSummaryStatus = "ok" | "empty" | "warn";
// added to EVERY member of the ToolPart union:
//   summary?: string;
//   summaryStatus?: ToolSummaryStatus;

// packages/assistant-client-ts/src/core/trace.ts
export type TraceRowStatus =
  | "running" | "ok" | "empty" | "warn"
  | "error" | "denied" | "awaiting-approval";

export interface TraceRow {
  key: string;
  toolCallId: string;
  toolName: string;
  summary: string | null;
  status: TraceRowStatus;
  input: unknown;
  output: unknown;
  errorText: string | null;
}
export interface TraceGroup {
  key: string;
  phase: string;
  rows: TraceRow[];
  tokens: number;
  costUsd: string;
  state: "started" | "completed" | "failed";
}
export interface Trace {
  groups: TraceGroup[];
  figures: DataPart[];
  rowCount: number;
  running: boolean;
}
export interface BuildTraceOptions {
  renderingKinds?: ReadonlySet<string>;
}
export function buildTrace(
  parts: readonly MessagePart[],
  options?: BuildTraceOptions,
): Trace[];
```

**Produced by B, consumed by nothing yet:**

```python
# packages/assistant-core/src/assistant_core/graph/tool_summary.py
# Written with PEP 695 syntax in the code: def with_summary[T] ...
def with_summary(
    value: T,
    summary: str,
    *,
    ctx: RunContext[Any],
    status: ToolSummaryStatus = "ok",
    extra: Sequence[BaseChunk] = (),
) -> ToolReturn[T]:
    """Return a tool's value with its one-line summary and any other chunks."""
```

`with_summary` drops the summary chunk when `ctx.tool_call_id` is `None`,
because a summary that names no call is unreducible. It never raises: the
line is normalised by `truncate_summary` (ASCII fold, whitespace collapse, cut
on a word boundary, no trailing period) before the payload validator sees it,
so a call site never wraps its string in `truncate_summary` itself.
`count_noun(n, noun)` writes the singular where the count is one.

**Lead rulings at close, where the batch as executed departs from the text
below:**

- The five Lead dispatch tools (`frame_problem`, `build_strategy` on the Lead
  surface, `edit_strategy`, `recover_failed_steps`, `verify_strategy`) emit
  NO `data-tool-summary`. Their native tool chunks never reach the wire
  (`_lead_events.is_suppressed_sub_agent_chunk`), so a summary naming that call
  patches no part; their line already rides `data-sub-agent-call.summary`.
  The coverage test names the two dispatch modules as the reason it skips
  them.
- `data-sub-agent-call.subAgent` carries the phase role (`frame`,
  `execution`, `verification`) on every chunk of one call, from the dispatch
  and from the run alike. The dispatch tool's name is not a second vocabulary.
- The MCP wrapper appends `"{tool_name} returned"` unconditionally. No
  mechanism exists for a source to declare a summary of its own, so the
  "source wins" branch would guard nothing; it is written when a source can
  declare one.
- The coverage test enumerates every registered tool by a static walk of its
  return paths, and drives the `empty` cases, the durable builders and the
  pinned strings at runtime. The FunctionModel-driven run over all 83 tools
  with stubbed services was not built; the live worker turn and the EDA
  conversation test are the runtime proof.

## Task A1: PROTOCOL.md

Red first: `packages/assistant-core/tests/integration/conversation/test_protocol_document.py`
already fails when a chunk kind, a data part or an example changes without the
page changing. Add the registration first and watch it go red, then write the
page.

The exact diff to `PROTOCOL.md`:

1. **Section 5.2 data parts table**, one row appended inside the
   `<!-- data_parts:begin -->` markers (the table is generated from the
   registry, so this row appears once `core_parts.py` registers the kind):

   ```
   | `data-tool-summary` | One line saying what a tool call did. Patches the call's part. |
   ```

2. **Section 6**, a new subsection after 6.2:

   ```markdown
   ### 6.3 A tool that says what it did

   A tool MAY carry one line of prose describing its own result. The line
   rides a `data-tool-summary` chunk naming the call:

       { "type": "data-tool-summary",
         "data": { "toolCallId": "call_a1",
                   "summary": "6 of 12 Sample",
                   "status": "ok" } }

   The chunk MAY precede or follow that call's `tool-output-available`,
   `tool-output-error` or `tool-output-denied`, in the same turn. A reducer
   addresses the summary by `toolCallId`, so the order does not matter. At
   most one summary per call reaches the log; a later one replaces an earlier
   one under the rule of section 9. A durable tool emits its summary before
   its output chunk, and that is conforming.

   `summary` is one line: no newline, at most 120 characters, and never the
   call's output re-serialised. `status` is `ok`, `empty` or `warn` and
   defaults to `ok`. `empty` says the call succeeded and found nothing, which
   a client SHOULD show differently from a call that found something, because
   a silent zero otherwise reads as a success.

   A failed call carries no `status`: its part is already in `output-error`.
   ```

3. **Section 9**, one bullet after the tool bullet:

   ```markdown
   - `data-tool-summary` addresses the tool part named by `data.toolCallId`.
     It sets that part's `summary` and `summaryStatus` and appends no part. A
     summary naming a call the client does not hold is ignored.
   ```

4. **Section 8**, one captured example, generated by the suite's capture, not
   written by hand.

5. **Section 14 changelog**, one row at the top:

   ```
   | `1.4.0` | `data-tool-summary` (sections 5.2, 6.3, 9): a tool may carry one line saying what its call did, so a reader sees the work without the call's JSON. Before this the only description of a call on the wire was its raw input and its raw output. |
   ```

Green: `cd packages/assistant-core && uv run pytest tests/integration/conversation/test_protocol_document.py -v`.

## Task A2: the runtime side

Red: `packages/assistant-core/tests/integration/conversation/test_tool_summary.py`
drives `reduce_chunks` over a tool lifecycle plus a summary and asserts one
part with `summary` set. It fails because the reducer ignores the kind.

Green, in three edits:

1. `stream_events.py` gains `ToolSummaryStatus`, `ToolSummaryPayload` and
   `tool_summary_event`, beside the existing builders.
2. `core_parts.py` gains
   `registry.register("data-tool-summary", ToolSummaryPayload)`.
3. `_chunk_handlers.py`'s `_h_data` learns the rule. It currently appends every
   non-transient data part. It gains a branch: when
   `chunk["type"] == "data-tool-summary"`, look up the tool part by
   `data["toolCallId"]` and set `summary` and `summaryStatus` on it, appending
   nothing; when the id is unknown, return. `_chunk_state.py` holds no index
   of tool parts: `_State` carries `partial_tool_calls` (in-flight input text
   only), and the tool handlers find their part with
   `_find_tool_part_by_id` (`_chunk_handlers.py` line 145), a linear scan.
   Use that same function, so the summary and the tool chunks address a part
   one way.

The runtime suite runs with no `pathfinder` installed. Nothing in this task
names a gene, a strategy or a phase.

Gates: `cd packages/assistant-core && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy --strict src && uv run pytest`.

## Task A3: the client reducer

Red: `packages/assistant-client-ts/tests/conformance/toolSummary.test.ts`,
the seven cases batch 0's `toolSummary.acceptance.ts` names, written
independently so the two suites are not one suite twice.

Green:

1. `message.ts`: add `summary?: string` and `summaryStatus?: ToolSummaryStatus`
   to every member of the `ToolPart` union, and export the status type. The
   union has six members and `exactOptionalPropertyTypes` is on, so the fields
   are added by widening the shared identity type rather than by six
   copy-pastes; `write()` in `reduceTool.ts` must carry them forward on every
   state transition or a summary that arrives before the output is lost.
2. `reduceTool.ts`: `ToolTrack` gains `summary` and `summaryStatus`, every
   `write()` call spreads them, and a new exported
   `applyToolSummary(tracker, parts, chunk): boolean` handles the kind.
3. `reduce.ts`: `applyChunk` calls `applyToolSummary` before `applyDataChunk`,
   so the summary never becomes a data part in the conforming reducer.
4. `version.ts`: `PROTOCOL_VERSION` becomes `"1.4.0"`.
5. `yarn sync:protocol` regenerates `src/protocol/captured.json`. Never edit it
   by hand; `tests/conformance/protocolSync.test.ts` is the gate.

Note the asymmetry, and write it in one comment: this reducer folds the summary
into the part, the AI SDK's reducer leaves it beside the part, and `buildTrace`
is what makes the two agree.

## Task A4: `buildTrace`

Red: `packages/assistant-client-ts/tests/conformance/trace.test.ts`, the nine
cases batch 0's `trace.acceptance.ts` names, written independently.

Green: `packages/assistant-client-ts/src/core/trace.ts` implements
[overview.md](overview.md)'s grouping rule, rules 1 to 9, in one pass over
`parts`. It exports `buildTrace` and the four types. `index.ts` re-exports
them.

The single hard case is rule 6 against rule 7. Write it as a state machine with
one `open: Trace | null` and one `group: TraceGroup | null`, and pin the four
transitions with their own tests:

```
part is text with content       -> close open, group = null
part is reasoning, empty text,
  or step-start                 -> nothing
part is tool                    -> ensure open; ensure group (implicit "lead"
                                   when group is null); push row
part is data-sub-agent-call     -> ensure open; when group.key differs, start a
                                   new group keyed by data.toolCallId; merge the
                                   started and completed payloads into that group
part is data-sub-agent-step     -> find group by data.parentToolCallId; merge
                                   into its rows exactly as mergeSubAgentSteps
part is a rendering kind        -> ensure open; push onto open.figures
anything else                   -> nothing
```

`mergeSubAgentSteps` lives in `apps/web/src/lib/utils/subAgentStep.ts` today and
is 40 lines of pure logic. **Move it into `trace.ts`** and have the app import
it from the package: two implementations of one merge is exactly the
duplication this batch exists to avoid. `subAgentStep.ts` keeps
`formatStepResult` and `collectSubAgentSteps`, and its consumers are updated in
the same task. While moving it, fix the em dash (U+2014) at
`apps/web/src/lib/utils/subAgentStep.ts` line 27, inside the
`${message} ... ${detail}` template of `formatStepResult`, and the two in the
doc comment at lines 48 and 49, which violate the ASCII rule today.

`yarn build` is a gate for this package: nothing else reads `dist/`.

## Task A5: register the kind on the app side

`data-tool-summary` must not reach the unknown-part toast.

1. `packages/shared-ts/src/types.ts`: add `"data-tool-summary"` to
   `KnownDataPartKind`, and add its payload to `DataPartPayloadMap`.
2. `apps/web/src/features/conversation/content/coreDataParts.ts`: add
   `"data-tool-summary"` to `CoreDataPartKind` and map it to `() => null`. It
   is read by `buildTrace`, never drawn, exactly like `data-sub-agent-step`.
3. `apps/web/src/features/conversation/content/DataPartRenderer.tsx`: add the
   `.with("data-tool-summary", ...)` arm. `.exhaustive()` fails compilation
   without it, which is the design working.
4. `dataPartDispatch.test.tsx` asserts the merged map is total and that the
   three sources are disjoint; extend its expected key set. That file is NOT
   frozen and this is a legitimate edit.
5. `yarn generate:types` from the repo root. Task A2's
   `registry.register("data-tool-summary", ToolSummaryPayload)` changes the
   `StreamPartsSchemaIndex` model
   (`assistant_core/conversation/stream_parts/registry.py` line 89, served by
   `transport/http/routers/_stream_parts_schemas.py` line 20), so the OpenAPI
   spec and the generated zod schemas move in this batch.

## Task B1: the helper and the durable path

Red: `apps/api/src/pathfinder/tests/unit/ai/tools/test_summary_helper.py`.

1. `with_summary` returns a `ToolReturn` whose `return_value` is the value
   passed and whose `metadata` ends with one `data-tool-summary` chunk naming
   `ctx.tool_call_id`.
2. `extra` chunks come BEFORE the summary chunk, so a figure part still lands
   before the line that describes it.
3. `ctx.tool_call_id is None` yields a `ToolReturn` with the extras and no
   summary chunk, and raises nothing.
4. **The model sees the same thing.** Given a tool that returns `X` and a tool
   that returns `with_summary(X, "...", ctx=ctx)`, the `ToolReturnPart` the
   agent writes into history carries the same `content`. Drive it through a
   `FunctionModel` capture rather than asserting on internals.
5. A summary over 120 characters, or containing a newline, raises at
   construction. The tool's own test catches it.

Then the durable path, which is the one place the tool body never runs:

6. `durable.py`'s `_parse_invocation` already holds the `RunContext`. Capture
   `ctx.tool_call_id` into the closure and widen `ChunkBuilder` to
   `Callable[[Any, UUID, str | None], list[BaseChunk]]`, so a durable tool's
   `chunks_from_result` can emit its own summary at resume. Update
   `_enrichment_chunks_from_result` in `workbench.py`, the only existing
   builder, and give it a summary chunk.
7. `run_control_tests_on_step`, `optimize_search_parameters` and
   `run_eda_compute` gain a `chunks_from_result` builder whose only job is the
   summary. Their strings are in the table below.

## Task B2: one summary per tool

Every tool named by `_all_registered_names()` in
`apps/api/src/pathfinder/tests/unit/ai/test_tool_surface_agreement.py`, plus
`site_help`'s two, returns through `with_summary`. `think` gains
`ctx: RunContext[AgentDeps]` as its first parameter, and so do
`list_veupathdb_sites` and `describe_site`; pydantic-ai excludes a leading
`RunContext` from the tool schema, so the model sees no change.

**The rule every string obeys.** A summary names what the call produced, with
its number, in the reader's vocabulary. Never the tool's own name, never the
word "successfully", never a field name, never a JSON fragment, never a
sentence-ending period. When the result is empty, the string says so and the
status is `"empty"`.

### The seven EDA tools

| tool | summary | status |
|---|---|---|
| `search_eda_studies` | `f"{n} studies matched {query}"`; `f"No study matched {query}"` when `n == 0` | `ok` / `empty` |
| `describe_eda_study` | `f"{display_name}: {len(entities)} entities, {len(variables)} variables"`; append `", no gene id variable"` when `gene_entity_id` is None | `ok` / `warn` |
| `open_eda_analysis` | `f"Opened {display_name} on {dataset_id}"` | `ok` |
| `set_eda_filters` | `f"{num_filters} filters: {'; '.join(filter_summaries)}"`, the join truncated to 120 characters on a word boundary; on the sheet path `f"{len(decide)} filter slots to fill"` | `ok` |
| `preview_eda_subset` | one clause per entity the preview carries, `f"{count:,} of {unfiltered_count:,} {entity_display_name}"`, joined by `", "`; `status="empty"` when `count == 0` | `ok` / `empty` |
| `run_eda_compute` | from the resumed payload: `f"{genes_tested:,} genes tested, {up:,} up and {down:,} down"` | `ok` / `empty` |
| `create_eda_step` | `f"Step {step_id} added to strategy {wdk_strategy_id}"`; when `failed_step_ids`, `f"Step {step_id} added, {len(failed_step_ids)} steps failed"` with `status="warn"` | `ok` / `warn` |

This is the one entity-count format of [overview.md](overview.md) section 5,
shared with the figure captions: one clause per entity, thousands separated,
joined by `", "`, and the display name exactly as the wire gives it - never
`.lower()`, never a substituted noun such as `rows`. The heat shock preview
carries one entity, so the acceptance suite pins `6 of 12 Sample`; a preview
covering both entities yields
`6 of 12 Sample, 34,320 of 68,640 pfal3D7 htseq counts`, which is also the
`DataEdaAnalysisState` caption over the same study.

### Catalog and discovery

| tool | summary |
|---|---|
| `get_record_types` | `f"{n} record types"` |
| `search_for_searches` | `f"{n} searches"`, `status="empty"` at 0 |
| `browse_search_categories` | `f"{n} categories"` |
| `list_searches` | `f"{n} searches on {record_type}"` |
| `list_transforms` | `f"{n} transforms on {record_type}"` |
| `lookup_phyletic_codes` | `f"{n} phyletic codes for {query}"` |
| `search_example_plans` | `f"{n} example plans"` |
| `get_search_overview` | `f"{search_name}: {n} parameters"`; on `AlreadyReadNotice`, `f"{search_name} already read"` with `status="warn"` |
| `get_parameter_options` | `f"{parameter_id}: {n} options"`, `status="empty"` at 0 |
| `request_search_inspection` | same as `get_search_overview` |

### FRAME spec

| tool | summary |
|---|---|
| `set_criterion` | `f"{criterion_id} set to {search_name}"`; when the result reports unresolved slots, `f"{criterion_id}: {n} parameters still open"` with `status="warn"` |
| `set_structure` | `f"Structure set: {n} criteria"` |
| `drop_criterion` | `f"Dropped {criterion_id}"` |

### Strategy build and edit

| tool | summary |
|---|---|
| `build_strategy` | `f"{n} steps, {genes:,} genes"` from the graph snapshot the tool already builds; `status="empty"` when `genes == 0`, because a zero-gene strategy is the failure a reader must see |
| `apply_operations` | `f"{len(operations)} operations applied, {n} steps"` |
| `update_leaf_params` | `f"{step_id}: {len(parameters)} parameters updated"` |
| `update_combine_operator` | `f"{step_id} now {operator}"` |
| `update_step_metadata` | `f"{step_id} renamed to {display_name}"` |
| `delete_step` | `f"Deleted {step_id}, {n} steps left"` |
| `replace_subtree` | `f"Replaced {step_id}, {n} steps"` |
| `insert_saved_strategy` | `f"Inserted saved strategy {saved_wdk_strategy_id} at {target_step_id}"` |
| `add_step_filter` | `f"{filter_name} added to {step_id}"` |
| `add_step_analysis` | `f"{analysis_type} added to {step_id}"` |
| `add_step_report` | `f"{report_name} report added to {step_id}"` |
| `rename_strategy` | `f"Renamed to {new_name}"` |
| `clear_strategy` | `f"Strategy cleared"` |
| `get_strategy` | `f"{n} steps, {genes:,} genes"`; `f"No strategy yet"` with `status="empty"` |
| `get_live_strategy_state` | same as `get_strategy` |

### Verification and experiments

| tool | summary |
|---|---|
| `get_estimated_size` | `f"Step {wdk_step_id}: {size:,} records"`, `status="empty"` at 0 |
| `get_sample_records` | `f"{n} sample records from step {wdk_step_id}"` |
| `get_download_url` | `f"{output_format.upper()} download ready"` |
| `run_control_tests_on_step` | `f"{recovered} of {total} positive controls recovered"`; the recorded turn pins `8 of 10 positive controls recovered` |
| `run_control_tests_on_search` | same shape, on the search |
| `optimize_search_parameters` | `f"{n} settings tried, best {objective} {score:.3f}"` |
| `compare_search_variants` | `f"{n} variants: {best_label} {best_count:,} genes"` |
| `compare_variants_scored` | `f"{n} variants scored, winner {winner} at {score:.3f}"` |
| `build_control_set` | `f"{name}: {len(positive_ids)} positive, {len(negative_ids)} negative"` |
| `list_control_sets` | `f"{n} control sets"` |
| `import_control_ids_from_gene_set` | `f"{n} ids from gene set {gene_set_id}"` |
| `import_control_ids_from_strategy` | `f"{n} ids from strategy {strategy_id}"` |
| `run_gene_set_enrichment` | `f"{n} enriched terms across {len(enrichment_types)} analyses"`, `status="empty"` at 0 |
| `create_workbench_gene_set` | `f"{name}: {len(gene_ids):,} genes"` |
| `list_workbench_gene_sets` | `f"{n} gene sets"` |
| `export_gene_set` | `f"{output_format.upper()} export ready"` |
| `resolve_gene_ids_to_records` | `f"{resolved} of {len(gene_ids)} ids resolved"`, `status="warn"` when any failed |
| `lookup_gene_records` | `f"{n} genes matched {query}"`, `status="empty"` at 0 |
| the seven `get_*` workbench reads | `f"{n} rows"` in the reader's noun, or the `WorkbenchError`'s own message with `status="warn"` |

### Research, memory, scratchpad, lead

| tool | summary |
|---|---|
| `web_search` | `f"{n} results for {query}"` |
| `literature_search` | `f"{n} papers for {query}"` |
| `search_memory` | `f"{n} memories for {query}"`, `status="empty"` at 0 |
| `remember` | `f"Remembered {name} as {kind}"` |
| `note` | `f"Note saved: {title}"` |
| `update_note` | `f"Note updated: {title}"` |
| `delete_note` | `f"Note deleted"` |
| `pin_note` / `unpin_note` | `f"Pinned {title}"` / `f"Unpinned {title}"` |
| `list_notes` | `f"{n} notes"` |
| `search_notes` | `f"{n} notes for {query}"` |
| `read_note` | `f"Read {title}"` |
| `promote_to_memory` | `f"Promoted {title} to memory"` |
| `think` | the first 120 characters of `thought`, on a word boundary |
| `classify_user_intent` | `f"Intent: {intent.kind}"` |
| `read_ledger_section` | `f"Read {section}"` |
| `consult_user` | `f"{len(questions)} questions asked"` |
| `frame_problem` | already summarised by `_summarize_sub_agent_result`, which calls `_summarize_delta` and `_summarize_delta_dict`; call it and pass its output |
| `build_strategy` (lead dispatch) | as above, through `_summarize_outcome` |
| `edit_strategy` | `f"{n} edits applied"` |
| `recover_failed_steps` | through `_summarize_delta_dict` |
| `verify_strategy` | through `_summarize_delta_dict` |

The five Lead dispatch tools already compute a one-liner in
`apps/api/src/pathfinder/ai/graph/_lead_events.py` for the sub-agent card.
**Call those functions; do not write a second summariser.** Export
`summarize_delta` from `_lead_events.py` and use it, so the card and the trace
row can never disagree.

### site_help

| tool | summary |
|---|---|
| `list_veupathdb_sites` | `f"{n} sites"` |
| `describe_site` | `f"{site_id}: {display_name}"` |

The MCP-served `wdk_*` tools are wrapped by
`assistant_core/mcp/untrusted.py` lines 141 to 144, which already build a
`ToolReturn` with a declared data chunk. Extend that wrapper to append a
summary chunk reading `f"{tool_name} returned"` ONLY when the source declared
no summary of its own; a source that declares one wins. This is the runtime
half, so it is Implementer A's edit, not B's.

## Task B3: the coverage test

`apps/api/src/pathfinder/tests/unit/ai/tools/test_tool_summaries.py`, modeled
on `test_tool_surface_agreement.py`'s `_all_registered_names()`.

1. `test_every_registered_tool_emits_a_summary`: for each of the four surfaces
   plus `site_help`, call every tool through a `FunctionModel`-driven agent run
   with stubbed services, and assert the resulting `ToolReturnPart.metadata`
   contains exactly one chunk of type `data-tool-summary` whose `toolCallId`
   equals the call's. A tool that cannot be driven without live WDK is exercised
   through its module-level formatting function instead, and the test names
   which tools took that route so the list cannot grow silently.
2. `test_no_summary_repeats_the_tool_name`: no summary string contains its own
   tool name, `successfully`, `{`, `}` or a newline.
3. `test_no_summary_exceeds_the_limit`: 120 characters.
4. `test_empty_results_report_empty`: for the eight tools whose table row names
   an `empty` case, drive the zero-result path and assert `status == "empty"`.
   A silent zero reported as `ok` is the bug this test exists for.
5. `test_extractor_registry_and_summaries_agree`: every tool name in
   `ai/context/extractors.py`'s `_EXTRACTOR_REGISTRY` also emits a summary. The
   two one-liners serve different readers - the model's context and the user's
   trace - and both stay, but neither may name a tool the other does not.

## Task B4: an inner summary becomes the sub-agent step's text

A sub-agent's inner tools now emit `data-tool-summary` chunks too, and their
`toolCallId` names an INNER call. No reducer holds an inner call, so such a
chunk on the main stream is unaddressable: it patches nothing and it is
dropped. The summary is not wasted, though - it is the best text the step row
has.

Red: `apps/api/src/pathfinder/tests/unit/ai/lead/test_sub_agent_stream_summary.py`.
A scripted sub-agent run whose inner tool returns a value carrying a
`data-tool-summary` chunk on its `ToolReturn.metadata`. Assert two things: the
emitted `data-sub-agent-step` chunk carries `resultSummary` equal to that
summary string, and NO `data-tool-summary` chunk reaches the main stream.

Green, in `apps/api/src/pathfinder/ai/lead/sub_agent_stream.py`,
`_forward_inner_event` (lines 174 to 214):

1. When an inner `ToolReturnPart.metadata` carries a `data-tool-summary` chunk,
   lift its `summary` into the `SubAgentStepPayload.result_summary`, and its
   `status` onto the step, before the step chunk is emitted.
2. Do NOT forward that chunk through `_forward_tool_metadata`. Every other
   metadata chunk keeps being forwarded unchanged.
3. `_result_summary`'s JSON dump becomes the fallback: it is used only when the
   inner result declared no summary.

The step row's text is then the tool's own sentence, in the tool's own numbers,
which is the same sentence the trace would have shown had the call been the
Lead's.

## Task B5: one phase name per call id

`_lead_events.py` puts `frame`, `build` or `verification` on the wire
(`_SUB_AGENT_TOOL_TO_PHASE`, lines 36 to 42, used at lines 186 and 216).
`sub_agent_stream.py` emits `phase=role`, and `role` is a `PhaseRole`
(`ai/agents/roles.py`), whose third member is `execution`. The same reconciled
`data-sub-agent-call` id can therefore carry two different phase names, and the
thread's one label set has to guess which is meant.

Red: `apps/api/src/pathfinder/tests/unit/ai/lead/test_sub_agent_phase_names.py`.
Drive a turn that emits both chunks for one call id and assert that the set of
`phase` values on that id has exactly one member.

Green: `sub_agent_stream.py` emits the same phase name `_lead_events.py` emits
for the same call, from the same map, so the wire vocabulary is `frame`,
`build` and `verification`. `PhaseRole` keeps its own members: it names the
agent roles the settings UI configures, not the phases the wire reports.
Batch 2's label set keeps `execution` as an alias of `Build`, so a conversation
recorded before this change still reads.

## Section close-outs

**A:**

- [ ] `cd packages/assistant-core && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy --strict src && uv run pytest`
- [ ] `cd packages/assistant-client-ts && yarn typecheck && yarn lint && yarn format:check && yarn test && yarn build`
- [ ] `cd apps/web && npx tsc --noEmit && npx eslint src/ && npx vitest run`
- [ ] Report: the PROTOCOL.md sections touched with their line ranges; whether
  `captured.json` was regenerated by the script and never by hand; the four
  `buildTrace` state transitions with the test name that pins each; whether
  `mergeSubAgentSteps` moved and every consumer updated; zero-debt statement.

**B:**

- [ ] `cd apps/api && uv run ruff check src/ && uv run ruff format --check src/ && uv run mypy --strict src/pathfinder/ && uv run pyright src/pathfinder/ && uv run lint-imports && uv run pytest src/pathfinder/tests/ -q`
- [ ] `docker compose --env-file .env.dev up -d --build --force-recreate api worker`, then grep for `tool_summary_event` inside the api container.
- [ ] Report: the count of tools converted against the count
  `_all_registered_names()` returns; every tool that took the
  formatting-function route in the coverage test and why; the eight `empty`
  cases with the test that drives each; the inner-summary lift with the test
  that proves no `data-tool-summary` names an inner call id; the phase names
  `sub_agent_stream.py` now emits; zero-debt statement.

## Verifier

Re-run every command in both close-outs, plus:

```
cd /Users/ahmedmuharram/repos/pathfinder/packages/assistant-client-ts
yarn test:acceptance
cd /Users/ahmedmuharram/repos/pathfinder/apps/web
npx vitest run --config vitest.acceptance.config.ts
node /Users/ahmedmuharram/repos/pathfinder/scripts/check-knowledge.mjs
```

The two client acceptance modules must now PASS unmodified. The frontend
acceptance modules must still SKIP: batch 1 draws nothing.

Traps, by name:

1. **`captured.json` edited by hand.** Its diff must be exactly what
   `yarn sync:protocol` produces. Re-run the script and diff.
2. **`summary` added as a field on a tool chunk** anywhere - Python, TypeScript
   or the protocol page. It makes the AI SDK throw. Grep for
   `ToolOutputAvailableChunk` subclasses and for `summary` inside
   `uiMessageChunkSchema`'s neighbours.
3. **`data-tool-summary` marked `transient`.** It must survive a reload.
4. **A second `mergeSubAgentSteps`.** Grep both packages and `apps/web`.
5. **`ToolReturn(..., content=...)` set anywhere new.** It changes what the
   model reads; this batch must not.
6. **A summary computed from the tool's output by a central registry** instead
   of at the tool. Grep for a new `dict[str, Callable]` keyed by tool name in
   `ai/tools/`.
7. **A tool converted to `ToolReturn` that dropped its existing metadata
   chunks.** The EDA tools, `build_strategy`, `replace_subtree`,
   `rename_strategy`, `clear_strategy`, `create_workbench_gene_set`,
   `export_gene_set` and the nine scratchpad tools all carry chunks today. For
   each, name the test that proves its chunk still arrives.
8. **`extra` chunks emitted after the summary.** The figure must precede the
   line about it.
9. **A durable tool whose summary never arrives**, because
   `chunks_from_result` was left `None`. All four durable tools must emit one.
10. **`ctx.tool_call_id` assumed non-None.** `RunContext.tool_call_id` is
    `str | None`.
11. **A summary with a trailing period, a newline, an em dash, or over 120
    characters.** The validator should refuse it; find a tool whose string can
    exceed the limit at runtime with real data, not just in a test.
12. **`_h_data` in the runtime reducer growing a second lookup** beside
    `_find_tool_part_by_id`. One function finds a tool part by id; a second
    copy is where the two drift.
13. **`isKnownChunkKind` failing the new kind**, which would make
    `DurableChatTransport` drop it silently. Its `startsWith("data-")` branch
    should already cover it; assert it, do not assume it.
14. **`DataPartRenderer`'s `.exhaustive()` silenced** with a default arm.
15. **A type suppression** anywhere in the diff.
16. **An import-linter contract count other than 8 kept.**
17. **`assistant_core` importing `pathfinder`.** Its suite runs with no
    `pathfinder` installed; run it and read the output.
18. **A `data-tool-summary` chunk naming an INNER call id** reaching the main
    stream. No reducer holds an inner call, so the chunk patches nothing.
    Capture the chunks of a sub-agent turn, collect every
    `data-tool-summary`'s `toolCallId`, and assert each one names a call the
    main stream also opened. Any id that appears only inside a
    `data-sub-agent-step` is a FAIL.

Mutation probes, three, applied one at a time with the implementers' tests
re-run after each:

- In `_chunk_handlers.py`, make the summary branch append a part instead of
  patching. A test must fail.
- In `trace.ts`, change rule 6 so a tool part with no group open is DROPPED
  rather than joining the implicit `lead` group. A test must fail.
- In `preview_eda_subset`, swap `count` and `unfiltered_count` in the format
  string. A test must fail, and it must be an assertion on `6 of 12`, not on
  the presence of a summary.

Report format, mandatory:

```
Batch 1 verification

Gates
  assistant-core ruff/format/mypy/pytest   PASS/FAIL  <counts>
  assistant-client typecheck/lint/test/build PASS/FAIL <counts>
  api ruff/format/mypy/pyright/lint-imports/pytest PASS/FAIL <counts>
  web tsc/eslint/vitest                    PASS/FAIL  <counts>
  client yarn test:acceptance              PASS/FAIL  <passed>/<total>
  web acceptance config                    PASS/FAIL  thread skipped: <n>
  check-knowledge.mjs                      PASS/FAIL

Acceptance no-edit check                   PASS/FAIL  <diff -r output>

Per task
  A1 PROTOCOL.md 1.4.0        PASS/FAIL  <evidence>
  A2 runtime reducer          PASS/FAIL
  A3 client reducer           PASS/FAIL
  A4 buildTrace               PASS/FAIL
  A5 kind registration        PASS/FAIL
  B1 with_summary + durable   PASS/FAIL
  B2 one summary per tool     PASS/FAIL  <converted>/<registered>
  B3 coverage test            PASS/FAIL
  B4 inner summary lifted     PASS/FAIL
  B5 one phase name per id    PASS/FAIL

Summary strings  (every tool: the string, the status, the test that pins it, or MISSING)

Traps  (1 to 18, each CLEAN or the file:line that violates it)

Mutation probes  (each: the mutation, the killing test, or SURVIVED)

Definition of done
  zero debt            YES/NO  <what remains>
  adjacent reconciled  YES/NO  <what was missed>
  tests assert values  YES/NO
```

## Exit criteria

For the session lead to close batch 1:

1. Every gate green, verified by the lead's own run.
2. `PROTOCOL.md` reads `1.4.0`, `PROTOCOL_VERSION` matches, and
   `captured.json` is the script's output.
3. Both conforming reducers fold a summary onto its tool part and append
   nothing, and both ignore a summary naming an unknown call.
4. `buildTrace` returns identical output for the folded shape and the
   beside-the-part shape, proven by one test.
5. `mergeSubAgentSteps` exists once, in the client package, and `apps/web`
   imports it.
6. Every tool `_all_registered_names()` returns, plus `site_help`'s two, emits
   exactly one `data-tool-summary` chunk naming its own call, and the coverage
   test enumerates them rather than sampling.
7. The eight `empty` cases report `status: "empty"`, driven by a test each.
8. All four durable tools emit a summary at resume.
9. `packages/assistant-client-ts` acceptance modules pass unmodified; the
   frontend acceptance modules still skip.
10. An inner tool's summary reaches the reader as the `data-sub-agent-step`'s
    `resultSummary`, and no `data-tool-summary` chunk naming an inner call id
    reaches the main stream.
11. One reconciled `data-sub-agent-call` id carries exactly one phase name, and
    that name is `frame`, `build` or `verification`.
12. The verifier's report shows all eighteen traps CLEAN, three mutation
    probes killed, and "zero debt YES".
