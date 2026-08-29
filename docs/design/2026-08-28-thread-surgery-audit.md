# Thread surgery: why branch, revert and durable resume keep breaking (2026-08-28)

> Status: **AUDIT, read-only.** No production code was changed. Every measured value
> comes from throwaway rows created and deleted on the dev stack on 2026-08-28, or
> from the filed UI-run items of 2026-08-17. Every claim about LangGraph cites the
> installed source under `apps/api/.venv/lib/python3.14/site-packages/` (langgraph
> 1.1.6, langgraph-checkpoint-postgres 3.0.5). Companion backlog items:
> [fork-drops-the-assistant-id](../knowledge/backlog/fork-drops-the-assistant-id.md),
> [fork-log-rows-cascade-with-the-parents-task-rows](../knowledge/backlog/fork-log-rows-cascade-with-the-parents-task-rows.md),
> [revert-leaves-the-strategy-at-post-turn-state](../knowledge/backlog/revert-leaves-the-strategy-at-post-turn-state.md),
> plus mechanism corrections written into the four previously filed items.

## 0. The answer in one page

**Why they break repeatedly.** Branch and revert are surgery on a data model whose
every invariant is owned somewhere else. The log's append-only shape, the one-id
rule, the cursor rule and the snapshot/tail equivalence are owned by
`assistant_core` and written down in PROTOCOL.md; the checkpoint rows are owned by
LangGraph and addressed here only through raw SQL against a private JSONB field;
the strategy, gene sets and WDK ids are owned by the product's services. `fork.py`
(424 lines) and `revert.py` (176 lines) sit in `services/conversations/` and
re-derive all of those invariants by hand, so every time an owner adds one - the
amnesia fix put `thread_messages_json` on the checkpoint, the E-era put a task's
lifecycle on the thread, `assistant_id` became load-bearing for routing - the
surgery silently misses it. That is the pattern behind all seven defects below,
and it is why point fixes have not converged.

**Durable resume breaks for one reason,** and it is a library contract, not a bug
in the worker: `interrupt()` is called beneath two LLM runs inside one LangGraph
node, and LangGraph resumes a node by re-executing it from its first line
(`langgraph/types.py:705-722`). The suspended sub-agent run is not parked
anywhere durable, so the resume value has nowhere to land. Section 3 traces it.

**Should surgery move into assistant-core?** The log/checkpoint half, yes - it is
the runtime's own data and the runtime is the only place that can mint ids under
the one-id rule and copy checkpoints beside the serde that wrote them. The
product half (strategy revision, WDK duplication, gene sets) cannot move and
should become a spec-shaped hook. Revert needs a protocol decision first, because
PROTOCOL 1 currently makes a conforming client *unable to see* a revert. Section 5
lays out the shapes and sizes as decision points.

---

## 1. Invariant inventory

What the thread/checkpoint model promises, with the owner that states it:

| # | Invariant | Stated by |
|---|---|---|
| I1 | A thread is an ordered, **append-only** log; the log alone rebuilds the conversation | PROTOCOL.md section 1 |
| I2 | **One id names one message**; a client keeps the first | PROTOCOL.md section 1; `decisions/one-id-names-one-message-in-the-log.md`; `event_writer.append_user_message_once` |
| I3 | **Cursors strictly increase** within a thread; snapshot + tail from its cursor equals the live bytes | PROTOCOL.md sections 2, 4 |
| I4 | The last user message's **id becomes the log row's id**, and the `messages` table holds a row under that same id | PROTOCOL.md section 12.2; `dispatcher.py:93-109` |
| I5 | A thread's **checkpoints describe that thread's transcript** - `thread_messages_json` (the amnesia fix), `spec_before_turn`, `pending_approval`, `turn_message_id` all ride the checkpoint | `turn_state.py:85-117`, `state.py:95-118`, `decisions/the-thread-carries-its-own-messages-across-turns.md` |
| I6 | The **assistant id is set at creation and never changed**, "so replaying it always runs the same architecture" | `assistant_core/persistence/models.py:112-118`; dispatcher 409 (`dispatcher.py:81-87`) |
| I7 | The **strategy row and the transcript agree**: what the thread says it built is what `conversation_strategies` holds | implied by `conversation-thread-and-strategy-split.md` and every live-state read |
| I8 | A **durable task's whole lifecycle is on the thread**; gap chunks belong to no turn | PROTOCOL.md 6.1; `decisions/durable-task-progress-belongs-in-the-thread-log.md` |
| I9 | A **parked approval** survives on the checkpoint with the history that resumes it (`PendingApproval.prior_messages_json`) | `turn_state.py:36-48`, `graph/approvals.py` |
| I10 | Checkpoint **serde is allowlisted**; state shape changes flush checkpoints rather than tolerate drift | `conversation/serde.py`, `decisions/no-checkpoint-truncation.md` |
| I11 | Cross-thread **memory is user-namespaced**, not conversation-namespaced | `memory/` |

### 1.1 Fork against the inventory (`services/conversations/fork.py`)

What fork does, line by line, against each invariant:

- **I1 preserved.** The fork writes a new thread by appending copies in source
  order (`fork.py:44-93`); the source is untouched.
- **I2 violated.** New `Message` rows get `id=uuid4()` (`fork.py:399-408`) while
  the copied chunks keep the parent's `messageId`/`message.id` (only scratchpad
  note ids are rewritten, `fork.py:96-126`). The branch renders the parent's ids,
  so every per-message action 404s - the filed
  [branch-keeps-parent-message-ids](../knowledge/backlog/branch-keeps-parent-message-ids-so-revert-404s.md)
  bug. Measured deeper this audit: the ids can never be reclaimed, because
  `messages.id` is the PK alone (`models.py:162`) and
  `insert_message` is `on_conflict_do_nothing` on it
  (`repositories/message.py:27-37`) - inserting the id into the fork persisted
  nothing while the parent held it (`b_has_row: false`).
- **I3 preserved.** Copies insert through the global sequence in source-id order
  (`fork.py:52-64`), so the fork's cursors are fresh and monotonic.
- **I4 violated**, as a consequence of I2: the fork's log ids have no `messages`
  row, and the fork's `messages` rows have no log presence.
- **I5 preserved, mechanically.** `_copy_checkpoint_state` (`fork.py:129-198`)
  copies `checkpoints` with `(checkpoint->>'ts')::timestamptz < next-message
  created_at`, all `checkpoint_blobs` whole, and the writes joined to surviving
  checkpoints. Verified against the installed schema: `checkpoints.checkpoint` is
  JSONB carrying `ts` (ISO 8601, writer's clock,
  `langgraph/checkpoint/base/__init__.py:588`), blobs are keyed
  `(thread_id, ns, channel, version)` so a whole-copy is inert surplus
  (postgres `base.py:37-85`). The cutoff is pinned by
  `test_fork_resume_returns_anchor_state` and
  `test_fork_writes_only_reference_surviving_checkpoints`. Two soft spots: the
  comparison mixes the checkpoint writer's clock with the DB's `now()` on message
  rows (same host today, unversioned assumption), and the whole mechanism reads a
  private LangGraph format with no version pin.
- **I6 violated, measured.** The fork constructor (`fork.py:360-367`) omits
  `assistant_id` and `application_id`; a fork of a `site_help` thread came back
  `assistant_id="pathfinder"`. Its next turn resolves the wrong spec and runs the
  Lead graph over single-agent checkpoints. Filed:
  [fork-drops-the-assistant-id](../knowledge/backlog/fork-drops-the-assistant-id.md).
- **I7 violated**, filed: the strategy row copied is the latest, the checkpoints
  are branch-point, so the fork disagrees with itself
  ([branch-copies-latest](../knowledge/backlog/branch-copies-latest-strategy-not-strategy-at-branch-point.md),
  sharpened this audit). `gene_set_id`/`experiment_id` are copied **by value**
  (`fork.py:377-379`): the fork points at the parent's rows, another cross-thread
  lifetime coupling nothing tests.
- **I8 violated, measured.** Copied rows keep `task_id` verbatim (`fork.py:71-72`)
  against an `ondelete="CASCADE"` FK; deleting the parent's task row deleted the
  fork's chunk (5 -> 4). Filed:
  [fork-log-rows-cascade](../knowledge/backlog/fork-log-rows-cascade-with-the-parents-task-rows.md).
  `background_tasks` rows themselves are not copied, so a fork taken **during** a
  suspension copies a checkpoint with a pending interrupt that no job will ever
  resume (the worker resumes by source thread id, `jobs/runner.py:321`), leaving
  the fork permanently mid-turn. Unmeasured; noted, not filed.
- **I9 partially handled.** A fork anchored before the approval turn excludes the
  parked state with the checkpoints. A fork anchored **on** it copies a
  `pending_approval` whose card the fork's log does render (chunks copied), and
  answering it posts against the fork's thread - plausible but unexercised by any
  test.
- **I10 silently bypassed.** The copy moves blob bytes with raw SQL and never
  passes through the allowlisted serde. Correct today; invisible to the refusal
  design when the format drifts.
- **I11 correct by construction** - memory is user-namespaced; fork changes nothing.
- Scratchpad notes: copied under fresh ids with chunk rewrite (pinned by two
  tests), but the **checkpoint blobs keep the source note ids** - `fork.py:390-391`
  says so itself. State that names a note id references a note the fork does not
  hold.

### 1.2 Revert against the inventory (`services/conversations/revert.py`)

- **I1/I3 violated by design, invisibly.** Revert deletes log rows
  (`revert.py:117-124`). PROTOCOL 1 has no truncation or replacement signal, so a
  conforming client that holds a cursor keeps the deleted prefix forever - the
  filed [revert-does-not-truncate-client-thread](../knowledge/backlog/revert-does-not-truncate-client-thread.md)
  bug is the protocol gap wearing a UI face. Snapshot/tail equivalence (I3) breaks
  for any reader connected across the revert.
- **I2 interacts subtly.** Deleting the target envelope lets the same id be
  re-posted (edit flow), and `append_user_message_once` will re-append it - one id
  now names, across time, two different messages. The reducer's first-wins rule
  makes any surviving stale copy shadow the new one.
- **I4 preserved** for the surviving prefix; the tuple cut
  `(created_at, id) >= (cutoff, target_id)` (`revert.py:100-108`) is deterministic
  and pinned (`test_same_timestamp_siblings_cut_by_id_order`). Note the tiebreak
  orders by uuid, not thread order; rows tied on `created_at` survive or die by id
  bytes. Adjacent deletes (notes, events, tasks) cut on timestamp alone with no
  tiebreak.
- **I5 preserved, same caveats as fork.** The checkpoint cut
  (`revert.py:134-164`) is the same raw `(checkpoint->>'ts')::timestamptz`
  comparison, pinned by `test_deletes_checkpoints_at_and_after_target` and
  `test_checkpoint_just_before_target_message_survives`. `checkpoint_blobs` are
  **never deleted** - orphaned blob versions accumulate for the life of the thread.
- **I6 preserved** (row untouched).
- **I7 violated, measured.** The strategy row and the WDK strategy survive a
  revert that deletes the turns that built them (marker AST intact, 4 steps).
  Filed: [revert-leaves-the-strategy-at-post-turn-state](../knowledge/backlog/revert-leaves-the-strategy-at-post-turn-state.md).
- **I8 half-handled.** `background_tasks` rows at/after the cutoff are deleted
  (`revert.py:125-132`), but the procrastinate job is not cancelled. The worker
  will run the tool, then `_announce_completion` appends a `data-task-completed`
  chunk to the thread **before** checking whether anything is resumable
  (`runner.py:157`, guard at `runner.py:322-329`), so a revert during a running
  task leaves an orphan completion chunk on the truncated log and repository
  updates against a deleted row. Code-level; not separately filed (it needs a
  timed repro), recorded here.
- **I9 handled by deletion**: reverting past an approval turn deletes the
  checkpoints holding `pending_approval`; the surviving checkpoint predates it.
  The client-side card survives only if its chunks predate the cutoff, in which
  case answering it targets a turn the server no longer holds - unexercised.
- **I10 bypassed** the same way fork bypasses it.

### 1.3 Violation count

| Operation | Preserved | Violated or silently ignored |
|---|---|---|
| Fork | I1, I3, I5 (with caveats), I11 | **I2, I4, I6, I7, I8** + note-id blobs, mid-suspension fork, serde bypass (I9/I10) |
| Revert | I4, I5 (with caveats), I6 | **I1/I3 (protocol-invisible), I7, I8 (in-flight race)** + blob orphans, re-posted-id shadowing (I2), serde bypass |
| Durable resume | I8 (thread lifecycle, post-E) | **I5's point: the suspended run is not on the checkpoint** (section 3) |

Three of the fork violations and one revert violation were unfiled before this
audit; all are filed now.

---

## 2. The durable result path, end to end

1. **Suspend.** The verify sub-agent calls a durable tool. The wrapper creates a
   `background_tasks` row (`ai/tools/durable.py:65`), defers the worker job under
   the conversation lock (`durable.py:74-86`), then calls `interrupt()`
   (`durable.py:88`). The `GraphInterrupt` bubbles out of the sub-agent's
   pydantic-ai run, out of the Lead's run, out of `lead_node`
   (`lead_node.py:270-271` re-raises `GraphBubbleUp`); LangGraph checkpoints the
   thread with the node marked pending. The dispatcher-side driver converts the
   interrupt into `data-background-task-started` (`_turn_helpers.py:163-172`) and
   the turn closes `finishReason: "other"` (PROTOCOL 6.1).
2. **Work.** The worker runs the impl, writes progress to the thread (coalesced,
   PROTOCOL 6.1), persists the result on the task row, appends
   `data-task-completed` (`runner.py:157`, `170-188`).
3. **Resume.** `_resume_graph` re-opens the graph on the same thread and streams
   `Command(resume={status, result})` (`runner.py:311-371`), writing the
   continuation under the **same** `turn_message_id` it reads from the checkpoint
   (`runner.py:336-341, 374-381`) - which is why the second measurement in the
   filed item saw a second `start` with the same messageId; the client reducer
   merges same-id starts into one message (`snapshot.ts:68-77`), matching 6.1's
   intent.
4. **The break.** LangGraph resumes a node by **re-executing it from the start**;
   resume values are matched to `interrupt()` calls **by order within the node**
   (`langgraph/types.py:705-722`). `lead_node` re-runs the Lead from
   `state.user_prompt` as a fresh LLM call (`lead_node.py:199, 221-229`). The
   suspended verify run's messages existed only in process memory - there is no
   durable parking for a sub-agent stopped on an interrupt, unlike approvals,
   which serialize `prior_messages_json`/`sub_agent.messages_json` into
   `PendingApproval` on the checkpoint (`turn_state.py:36-48`) precisely so the
   next turn can re-enter the same call. So:
   - If the replayed Lead never calls a durable tool, the resume value is never
     consumed: no verification section, `sub_agent_dispatch.py:371` never writes
     the digest, `derive_ledger` re-renders the previous turn's verdict
     (`derive.py:144`), the phase card stays "started". Measurement 1.
   - If the replayed Lead does reach a durable call, the wrapper's pre-interrupt
     side effects **re-execute** - a second `background_tasks` row and a second
     deferred job - before `interrupt()` consumes the queued value and returns the
     *first* task's result to whatever call got there first. Meanwhile the replay
     re-framed and re-built on live WDK (all-new step ids, 136.8K tokens).
     Measurement 2.

**Verdict on the E-era.** The thread-carried lifecycle (PROTOCOL 6.1) and the
client re-attach (`DataBackgroundTaskStarted.tsx:64-76` calling
`chat.resumeStream()`; `ChatView.tsx:92-95` for mounts) fixed the third mechanism
in the filed item - visibility. They **narrowed** the bug; they did not touch the
root cause, which is a checkpoint-shape problem: the suspended sub-agent run must
be parked durably (the approval pattern) or the durable call must move out of the
nondeterministic node. The filed item now carries this mechanism.

---

## 3. Test-coverage verdict

Suites read: `test_fork_wdk_remap.py` (231 lines),
`test_conversation_fork_and_delete.py` (1917), `test_conversation_revert.py`
(543), `test_revert_route.py` (180), `tests/integration/jobs/test_runner.py`,
`tests/integration/durable/*`, `test_task_progress_on_thread.py`.

| Invariant | Fork | Revert | Durable resume |
|---|---|---|---|
| Prefix/cutoff correctness | **pinned** (from-latest, mid-chat, strictly-less-than, tie-determinism, order) | **pinned** (at-and-after x4, tuple tiebreak, envelope) | n/a |
| Checkpoint cut / anchor state | **pinned** (anchor-state resume, latest-matches-source, writes-reference-survivors, blob bytes) | **pinned** (deleted at/after, prior survives) | n/a |
| Ownership / authz | **pinned** | **pinned** (route + service) | n/a |
| WDK remap | **pinned** (unit, DFS pairing, error fallback) | n/a | n/a |
| Scratchpad ids | **pinned** (fresh ids + chunk rewrite) | **pinned** (notes deleted) | n/a |
| Fork/delete interplay | **pinned** (cascade, promote, fork-of-fork) | **pinned** (branch-point nulls child ref) | n/a |
| Log-id = message-row-id (I2/I4) | **none** | none (surviving prefix untested) | none (same-id continuation shape untested) |
| assistant_id / application_id carry (I6) | **none** | n/a (untouched) | n/a |
| Strategy/transcript agreement (I7) | **none** (bug filed, no red test) | **none** (bug filed, no red test) | n/a |
| task_id lifetime coupling (I8) | **none** | none (job-not-cancelled, orphan completion chunk) | partial (progress-on-thread golden) |
| Result reaches the suspended call | n/a | n/a | **none** - runner tests stop at "impl runs, row marked"; nothing asserts the resumed graph delivers into the same tool call, updates the digest/ledger, or avoids double-defer |
| Mid-suspension surgery (I9) | **none** | **none** | **none** |

### The five highest-value missing tests

1. **Durable resume delivers into the suspended call.** Integration: a scripted
   Lead whose verify sub-agent calls a durable tool; run the worker path; assert
   the *same* `tool_call_id` receives `{status, result}`, exactly one
   `background_tasks` row exists afterwards, and `verification_digest` names the
   new build. Red today by section 2; it is the pin for the whole resume seam.
2. **Fork id-space conformance.** After any fork, every `messageId`/`message.id`
   in the fork's `conversation_events` is the id of a `Message` row in the fork,
   and `POST /revert-to-message` on the fork's own mid-thread user message returns
   204. Red today; pins the 404 family and any future id-map regression.
3. **Fork carries the thread's architecture.** Fork a conversation created under a
   non-default assistant; assert the fork's `assistant_id` (and `application_id`)
   equal the source's and the next dispatch resolves the same spec. Red today.
4. **Fork/parent lifetime isolation.** After a fork, revert then delete the
   parent; assert the fork's event count, snapshot bytes and strategy row are
   byte-identical before and after. Red today via the `task_id` cascade.
5. **Revert leaves a self-consistent world.** Revert past a build turn; assert
   either the strategy row matches the strategy at the target message (the
   revision-store fix) or, pending that decision, that the surviving thread
   carries an explicit marker that the strategy did not follow - and always: no
   `data-task-completed` lands after the cut for a task the revert deleted, and
   the procrastinate job for a deleted task is cancelled or provably no-op
   end-to-end.

---

## 4. Should thread surgery move into assistant-core?

### What the audit says about ownership

Every defect in section 1 is a hand-rolled re-derivation of an invariant owned by
`assistant_core` or LangGraph: the id rule (I2/I4), the log's lifetime (I8), the
checkpoint format (I5, raw `checkpoint->>'ts'` in two files), the assistant
binding (I6). None of the defects is WDK science. Conversely, the parts of fork
that *work* well - WDK strategy duplication with DFS remap, scratchpad copy,
gene-set references - are product code that a runtime could never write.

That is the same split `AssistantSpec` already institutionalized: the runtime owns
the mechanics, the assistant declares the product substance
(`decisions/the-orchestration-is-the-assistants.md`,
`decisions/assistant-core-is-a-package-boundary.md`).

### Decision point A - fork as a runtime primitive with a product hook

**Shape.** `assistant_core` grows `fork_thread(source, anchor_message_id) ->
new_conversation`: copies the conversation row **including** `assistant_id`/
`application_id`, copies messages and chunks through **one id map** (mint new ids
for `Message` rows *and* rewrite every `messageId`/`message.id`/`turn_id` chunk
field - the runtime knows the chunk vocabulary; it is the only place that can),
copies checkpoints beside the serde/checkpointer that wrote them, refuses or
detaches a mid-suspension anchor, and nulls or re-homes `task_id` tags. The
product registers a fork hook on its spec - mirror of `pre_turn`/`build_graph` -
receiving `(source_conversation_id, new_conversation_id, anchor_message_id)` and
doing strategies, WDK duplication, gene sets, scratchpad. `fork.py`'s WDK half
moves there nearly verbatim.

**For:** every I2/I4/I6/I8 defect becomes structurally impossible instead of
individually patched; site_help and every future assistant get fork for free;
protocol-wise a fork is just a new thread, so **no PROTOCOL change is needed**.
**Against:** the hook is a new spec surface to design well (ordering, failure -
what happens when WDK duplication fails mid-fork is today a warning and a
strategy-less fork, `fork.py:277-283`); the id map must also be offered to the
hook so product chunks (graph snapshots naming step ids) can be rewritten.
**Size:** runtime primitive with tests ~3-4 days; spec hook + moving the product
half ~2-3 days; the five tests of section 3 ride along.

### Decision point B - what revert *is*, before where it lives

Revert as deletion contradicts PROTOCOL 1, and no relocation fixes a
contradiction. Three candidate semantics, one must be chosen:

1. **Truncation signal (PROTOCOL 1.4).** Keep in-place deletion; add a chunk or a
   snapshot-epoch that tells a client "your prefix is void, re-snapshot". Smallest
   server change; makes every client and the conformance suite handle a second
   history mode; the log stops being append-only in fact while claiming it in
   words. ~2-3 days across PROTOCOL.md, event_stream, client, conformance.
2. **Revert = fork-without-tail + swap.** Reuse primitive A: build the truncated
   thread as a *new* conversation and repoint the UI. Append-only stays literally
   true, one primitive serves both operations, old thread is deletable garbage;
   cost is id churn (the client lands on a new conversation id) and redirect
   plumbing. ~2-3 days once A exists.
3. **Status quo + client patch** (the filed item's local fix). Cheapest; leaves
   the protocol lying about the log, and every future client re-discovers it.

Option 2 is the only one where the runtime's invariants survive untouched; option
1 is the honest version of today's behavior. The owner should pick between them -
this audit only insists that 3 is not an endpoint.

### Decision point C - the strategy revision store

Branch-at-point and revert-with-strategy both dead-end on the same missing thing:
no strategy snapshot per revision
(`branch-copies-latest`, `revert-leaves-the-strategy-at-post-turn-state`). This is
product persistence, stays in `apps/api`, and is the largest piece: revision rows
keyed by the `data-strategy-revision` already on messages, materialization into a
fresh WDK strategy on branch/revert, and the fork hook (A) consuming it.
~1-2 weeks. Without it, A and B still fix the id, architecture, lifetime and
resume defects - C is separable and should not block them.

### Decision point D - the durable resume seam

Independent of surgery placement: park the suspended sub-agent run durably (extend
the `PendingApproval` pattern with a `pending_durable` carrying the sub-agent
role, tool_call_id and messages_json; resume re-enters via
`deferred_tool_results` exactly as approvals do at `_lead_turn.py`) rather than
relying on node replay. This is runtime-adjacent but the parking types already
live in `assistant_core.graph.turn_state`. ~3-5 days including test 1 of section
3, and it removes the double-defer hazard because the wrapper stops re-executing.

---

## Appendix: measurements

Throwaway repro (dev stack, 2026-08-28; script created and deleted its own rows):

- fork of `site_help` conversation `e4305c57` -> fork `78db3553` with
  `assistant_id: "pathfinder"`.
- fork message rows `3147d2e5`, `a008250b` vs copied chunk ids `2e3e2a83` (user),
  `0ce32ed6` (assistant start) - two id spaces in one thread.
- fork event count 5 -> 4 after deleting the parent's `background_tasks` row
  `869d7668` (CASCADE via `conversation_events.task_id`).
- revert of `e4305c57` to its user message: `deleted_messages=1`,
  `deleted_events=4`; `conversation_strategies` row survived intact
  (`{"marker": "POST-TURN-AST", "steps": [1, 2, 3, 4]}`).
- `insert_message` of an id held by conversation A into conversation B persisted
  no row (`b_has_row: false`) - the global PK squat.
