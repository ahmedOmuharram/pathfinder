---
type: Backlog Item
title: Two api integration tests fail under machine load, one on a wall-clock bound and one on a teardown race
description: A full `pytest src/pathfinder/tests/` run that overlapped two other suites reported `test_parallel_fan_out_runs_variants_concurrently` failing on `assert 1.2420632909925189 < 1.2` and `test_chat_sse_golden_snapshot_simple_turn` failing on a `conversation_events` foreign-key violation plus a TimeoutError. Both pass in a quiet session, so the suite reports a machine's load as a product defect.
tags: [verification-gates, tests, flakiness]
generated: { by: claude-code/opus-5, at: 2026-08-24T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-24T00:00:00Z }
status: stable
---

# What was measured

One `uv run pytest src/pathfinder/tests/ -q` run, while two other pytest
sessions and the compose stack were running on the same machine: `2 failed,
3078 passed, 144 skipped, 100 subtests passed in 2607.38s`. The same two tests,
re-run alone in a quiet session: `36 passed in 41.39s` for both their
directories together, and `1 passed in 7.06s` for the golden test on its own.

**`integration/jobs/test_optimize_params_impl.py:205`** asserts elapsed wall
time:

    assert elapsed < 1.2, "expected parallel execution (~0.5s); got ...; likely sequential"
    AssertionError: assert 1.2420632909925189 < 1.2

The bound is 2.4 times the intended 0.5 s, which a loaded machine still
exceeds. The property under test is that the variants overlap, and wall time is
a proxy for it that the scheduler decides.

**`integration/chat/test_chat_sse_golden.py::test_chat_sse_golden_snapshot_simple_turn`**
failed with a `TimeoutError` waiting on the turn, and the in-flight request task
then wrote an event for a conversation the teardown had already truncated:

    ForeignKeyViolationError: insert or update on table "conversation_events"
    violates foreign key constraint "conversation_events_conversation_id_fkey"

The `_eager_spawn` fixture awaits pending tasks for 10 s and cancels the rest,
so a turn slower than that outlives the truncation that follows it.

# The same class, measured again with more suites running

With nine `pytest` sessions and the compose stack on one machine, three more
tests joined the two above, and the failing set moved between runs of the same
code:

- `integration/conversation/test_durable_turn.py::test_post_chat_enqueues_runs_and_streams_until_done`
  and `::test_events_endpoint_returns_204_when_turn_complete` - both end in
  `TimeoutError` from `asyncio.wait_for`, which the file bounds at 5 s for the
  enqueue and 30 s for the turn. One run reported the first alone; the next run
  of the same file reported both.
- `integration/chat/test_turn_runs_under_its_assistant.py::test_a_completed_turn_records_the_assistant_that_answered`,
  alongside the golden snapshot already named above.

`integration/jobs/test_optimize_params_impl.py:205` measured 2.07 s against its
1.2 s bound, up from the 1.24 s recorded above.

**The failing set tracks the load average.** Re-running the same four files at
load 25 rather than load 38 returned the three durable-turn tests to green and
left exactly the two named at the top of this item red. So the count in the
title is a property of one machine on one afternoon, not of the suite: the
number of tests that report load is a sliding one, and every test bounded by a
fixed deadline is a candidate.

The fix is the same for all of them: bound the property, not the clock.

# Why it matters

A gate that reports the machine's load cannot answer "did my change break
this". Every task in a batch that runs concurrent suites pays for it by
re-running failures by hand to find out they are nobody's.

# What to do

Assert the concurrency, not the clock: record the maximum number of variants
in flight (a counter incremented on entry and decremented on exit) and assert
it exceeds one. For the golden test, make the teardown wait on the turn it
started rather than on a fixed deadline, or fail the test explicitly when the
grace period expires instead of letting a cancelled task write after the
truncation.
