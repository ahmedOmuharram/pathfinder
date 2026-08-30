---
type: Backlog Item
title: A durable task's completion replays the Lead node from its start, so the turn re-decides, re-opens and never builds the step
description: A durable tool interrupts the graph from inside the agent run (`@durable_tool` calls LangGraph `interrupt()`), and `Command(resume=...)` re-executes the whole `lead` node - the model calls again, opens a second EDA analysis, submits a second job, and `create_eda_step` finds no computation on the analysis it now holds. Measured 2026-08-30 on the febrile-versus-normal DESeq prompt. Approvals do not have this problem because they end the run as pydantic-ai deferred tools and resume from message history. The fix is to make durable tools deferred tools too.
tags: [durable-tasks, resume, langgraph, lead, eda, investigation]
generated: { by: claude-code/fable-5, at: 2026-08-30T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-30T00:00:00Z }
status: stable
---

**What I did.** Ran the prompt "I'm looking at the heat shock RNA-seq study on
PlasmoDB ... give me the genes that are at least 2-fold up or down with an
adjusted p below 0.05 as a step in my strategy" on the real provider
(conversation `f55dcbf2-a575-426e-b62a-8d611d4b50b1`), answered the consult
question ("Keep febrile + normal"), and watched the durable compute complete
and resume.

**What I got.** Turn 2 opened analysis `13FVNaz`, set the filter, previewed
"12 of 12 Sample", and deferred `run_eda_compute` as task `0c6100d2`, which
completed in 115 s with "1543 of 5511 genes pass an effect size of 1.0 and a
p-value of 0.05: 529 up and 1014 down". On resume the log shows the consult
output re-emitted (#154764), `classify_user_intent` again, a SECOND analysis
`P8zhBKT` opened (#155102), the filter set again, `run_eda_compute` answering
at once from the cached job while also deferring task `bdcf2ddf`, then
`create_eda_step` failing twice with "Analysis P8zhBKT carries no
computation" (#155350, #155379), a third `run_eda_compute` deferring
`3c906ca4`, and both later jobs logging `no pending graph state to resume`.
The turn ended without `done`, `conversation_strategies` holds no row, and
the bound analysis is `P8zhBKT` at revision 4.

**Why that's wrong.** The user asked for one step and got no step, two
analyses, three compute jobs and a turn that never closed. Every durable tool
(`run_control_tests_on_step`, `optimize_search_parameters`,
`run_gene_set_enrichment`, `run_eda_compute`) is exposed the same way; the
UI-run card `verification-durable-task-result-lost-on-resume` is the same
mechanism seen from the verify sub-agent.

**Why it happens.** `apps/api/src/pathfinder/ai/tools/durable.py` defers the
job and then calls LangGraph `interrupt()` from inside the tool, inside the
agent run, inside the `lead` node. `jobs/runner.py::_resume_graph` resumes
with `Command(resume=result)`, and LangGraph re-executes the node from its
first line: the agent run starts over, the first `interrupt()` it reaches
(the consult approval) is answered from the checkpoint, every model call and
tool side effect before the durable `interrupt()` runs again, and the stored
result is handed to whichever `run_eda_compute` call the replay reaches,
which now names a different analysis. Approvals do not replay: the consult
tool raises `CallDeferred`, the run ends with `DeferredToolRequests`, and the
next turn passes `DeferredToolResults` over the saved message history
(`ai/graph/_lead_turn.py:237-276`).

**Fix.** Make a durable tool a deferred tool. `@durable_tool` creates the
`background_tasks` row, defers the job, stores the pydantic-ai
`tool_call_id` on the row, and raises `CallDeferred`; the run ends like an
approval and the turn closes with `data-background-task-started`. On
completion the worker starts a new Lead turn on the thread with
`DeferredToolResults(calls={tool_call_id: result})` (the path
`_lead_turn.py` already takes for approvals), so nothing before the call
runs again and `chunks_from_result` emits the summary and the figure from
that turn. `_resume_graph` and its `Command(resume=...)` path go away, as
does the `interrupt()` in `durable.py`. Acceptance first: a scripted turn
that opens an analysis, defers a compute, completes it, and asserts exactly
one analysis, one job, one `create_eda_step` and a strategy row; plus the
UI-run card's verify case.

**What you would get.** The prompt above ends with one DESeq step whose
`eda_analysis_spec` names `DS_e973eadd57` and a verification digest with the
gene count, in one closed turn.
