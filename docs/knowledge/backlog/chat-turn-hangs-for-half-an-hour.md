---
type: Backlog Item
title: A chat turn can run for 16 to 32 minutes and then error, while the same turn normally takes under a minute
description: The same mock build prompt ("create step") completes in 12.7 s on tritrypdb, 15.1 s on cryptodb and 15.8-29.6 s on plasmodb, and reaches 42.9 s when two turns run at once. Against that, one fungidb turn lasted 1039 s, a second ran 1909 s and ended with Error, and a tritrypdb turn ran 939 s and ended with Error. The worker logs asyncio "Task was destroyed but it is pending" errors from langgraph/store/base/batch.py:330 in the same windows. A turn that runs this long also holds its worker slot, so every other conversation queues behind it.
tags: [investigation, jobs, worker, e2e, availability]
generated: { by: claude-code/opus-5, at: 2026-08-23T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-23T00:00:00Z }
status: stable
---

# Investigation (e2e stack, 2026-08-23)

**What I did.** Ran the journey specs against the isolated e2e stack (mock chat
provider, live WDK, `pathfinder_test`) and read every `chat_turn` job's duration
out of the worker log. Each journey sends the same three messages: two questions,
then the mock build prompt `create step`.

**What I got.** Build-turn durations by site, from
`procrastinate.worker` "ended with status: Success, lasted N s":

| site | normal build turn | outlier |
|---|---|---|
| tritrypdb | 12.665 s | 939.356 s, Error |
| cryptodb | 15.112 s | - |
| plasmodb | 15.758 s, 29.614 s | - |
| fungidb | none observed | 1039.392 s; 1909.618 s, Error |

Two turns running at once reach 42.9 s, so the normal band is under a minute.
The 1909 s fungidb turn started at 18:58:56 and logged no end line for 31
minutes, through two later spec runs, before ending with Error. In the same
windows the worker logged:

```
Task was destroyed but it is pending!
task: <Task cancelling name='Task-785' coro=<_run() running at
  langgraph/store/base/batch.py:330> wait_for=<Future cancelled>>
```

**Why that is wrong.** The researcher asks for a strategy and the reply never
arrives; the composer stays in its streaming state, with no error, for half an
hour. The turn also holds its worker slot for that whole time, so every other
conversation on the deployment queues behind it: in the same run, turns on
tritrypdb and plasmodb waited about 18 s for a slot before starting, which is
longer than they take to run.

**Why it happens.** Not yet established. The batch coroutine named in the error
belongs to the LangGraph store, which the turn uses for memory retrieval at Lead
entry and for the auto-write in `finalize_turn`, so a store batch that never
resolves is the first place to look. It is not one site's problem: fungidb and
tritrypdb both produced one, and fungidb produced two.

**Fix (to decide).** Reproduce one hanging turn with the pipeline debugger
(`pathfinder.devtools.chat`) and capture where it stops. Then either bound the
store batch with a timeout that fails the turn loudly, or fix the coroutine that
never resolves. A turn that cannot finish must end as an error the user can see,
not as a slot held for half an hour.

**What you would get.** Every build turn finishes inside the measured band or
fails visibly, and one stuck conversation no longer delays every other
conversation on the deployment.

# Blast radius today

`e2e/journey/fungal-pathogenesis.spec.ts` carries `test.fixme` naming this item:
the spec cannot pass while the turn does not finish, and letting it run holds a
worker slot long enough to fail unrelated journeys in the same suite. Remove the
annotation when this is fixed.
