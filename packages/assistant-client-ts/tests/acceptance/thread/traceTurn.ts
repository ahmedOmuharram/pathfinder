/**
 * The recorded turn, chunk by chunk, as the wire carried it.
 * Frozen with the buildTrace acceptance modules: implementers may not touch tests/acceptance/**.
 */
import type { Chunk } from "./traceTypes";
import {
  ANALYSIS_STATE,
  DATASET,
  MESSAGE_ID,
  SAMPLE,
  SUBSET_PREVIEW,
  SUB_AGENT,
  TASK_ID,
  VOLCANO,
} from "./tracePayloads";

export const TURN: Chunk[] = [
  { type: "start", messageId: MESSAGE_ID },
  { type: "data-turn-status", data: { label: "Thinking...", waitingOnLlm: true } },
  { type: "text-start", id: "t1" },
  {
    type: "text-delta",
    id: "t1",
    delta: "I looked at the heat shock study and subset it to the febrile samples.",
  },
  { type: "text-end", id: "t1" },
  { type: "tool-input-start", toolCallId: "call_1", toolName: "search_eda_studies" },
  {
    type: "tool-input-available",
    toolCallId: "call_1",
    toolName: "search_eda_studies",
    input: { query: "heat shock", limit: 5 },
  },
  { type: "tool-output-available", toolCallId: "call_1", output: { studies: 3 } },
  {
    type: "data-tool-summary",
    data: {
      toolCallId: "call_1",
      summary: "3 studies matched heat shock",
      status: "ok",
    },
  },
  { type: "tool-input-start", toolCallId: "call_2", toolName: "open_eda_analysis" },
  {
    type: "tool-input-available",
    toolCallId: "call_2",
    toolName: "open_eda_analysis",
    input: { datasetId: DATASET, purpose: "subset the febrile samples" },
  },
  {
    type: "tool-output-available",
    toolCallId: "call_2",
    output: { analysisId: "a-1" },
  },
  { type: "data-eda.analysis-state", data: ANALYSIS_STATE },
  {
    type: "data-tool-summary",
    data: {
      toolCallId: "call_2",
      summary: "Opened Febrile samples on DS_e973eadd57",
      status: "ok",
    },
  },
  { type: "data-sub-agent-call", id: "sa_1", data: { ...SUB_AGENT, state: "started" } },
  {
    type: "data-sub-agent-step",
    data: {
      parentToolCallId: "sa_1",
      kind: "tool",
      state: "started",
      toolCallId: "s1",
      toolName: "search_for_searches",
      args: { query: "heat shock" },
    },
  },
  {
    type: "data-sub-agent-step",
    data: {
      parentToolCallId: "sa_1",
      kind: "tool",
      state: "completed",
      toolCallId: "s1",
      resultSummary: "12 searches",
    },
  },
  {
    type: "data-sub-agent-step",
    data: {
      parentToolCallId: "sa_1",
      kind: "tool",
      state: "started",
      toolCallId: "s2",
      toolName: "set_criterion",
      args: { criterionId: "c1", searchName: "GenesByText" },
    },
  },
  {
    type: "data-sub-agent-step",
    data: {
      parentToolCallId: "sa_1",
      kind: "tool",
      state: "completed",
      toolCallId: "s2",
      resultSummary: "c1 set to GenesByText",
    },
  },
  {
    type: "data-sub-agent-call",
    id: "sa_1",
    data: {
      ...SUB_AGENT,
      state: "completed",
      succeeded: true,
      tokens: 12300,
      costUsd: "0.004",
    },
  },
  { type: "tool-input-start", toolCallId: "call_3", toolName: "preview_eda_subset" },
  {
    type: "tool-input-available",
    toolCallId: "call_3",
    toolName: "preview_eda_subset",
    input: { entityId: "ENT_8151325d", distributionVariableId: "VAR_7033e90f" },
  },
  {
    type: "tool-output-available",
    toolCallId: "call_3",
    output: { entityCounts: [SAMPLE] },
  },
  { type: "data-eda.subset-preview", data: SUBSET_PREVIEW },
  {
    type: "data-tool-summary",
    data: { toolCallId: "call_3", summary: "6 of 12 Sample", status: "ok" },
  },
  {
    type: "tool-input-start",
    toolCallId: "call_4",
    toolName: "run_control_tests_on_step",
  },
  {
    type: "tool-input-available",
    toolCallId: "call_4",
    toolName: "run_control_tests_on_step",
    input: { wdkStepId: 132 },
  },
  {
    type: "data-background-task-started",
    data: {
      taskId: TASK_ID,
      toolName: "run_control_tests_on_step",
      estimatedDurationSeconds: 3,
    },
  },
  {
    type: "data-task-progress",
    id: TASK_ID,
    data: { taskId: TASK_ID, percent: 0.66, message: "Comparing controls" },
  },
  { type: "data-task-completed", data: { taskId: TASK_ID, status: "success" } },
  {
    type: "tool-output-available",
    toolCallId: "call_4",
    output: { recovered: 8, total: 10 },
  },
  {
    type: "data-tool-summary",
    data: {
      toolCallId: "call_4",
      summary: "8 of 10 positive controls recovered",
      status: "ok",
    },
  },
  {
    type: "tool-input-start",
    toolCallId: "call_5",
    toolName: "optimize_search_parameters",
  },
  {
    type: "tool-input-available",
    toolCallId: "call_5",
    toolName: "optimize_search_parameters",
    input: { target: { wdkStepId: 132 }, controls: { setId: "ctrl_1" } },
  },
  { type: "tool-approval-request", toolCallId: "call_5", approvalId: "call_5" },
  { type: "data-eda.viz", data: VOLCANO },
  { type: "text-start", id: "t2" },
  {
    type: "text-delta",
    id: "t2",
    delta: "Approve the parameter sweep and I will run it.",
  },
  { type: "text-end", id: "t2" },
  {
    type: "data-lead-usage",
    id: "lu_1",
    data: { modelId: "openai:gpt-5.6-luna", tokens: 41800, costUsd: "0.0131" },
  },
  { type: "finish", finishReason: "stop" },
];
