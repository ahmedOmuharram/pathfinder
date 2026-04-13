/**
 * Realistic SSE event sequences for integration-style frontend tests.
 *
 * These match what the backend actually produces during live WDK flows,
 * including real PlasmoDB search names, gene IDs, and parameter values.
 */

import type { ChatSSEEvent } from "@/lib/sse_events";

export { EXECUTE_EPITOPE_SEARCH_EVENTS } from "./executeEpitopeEvents";

export const OPTIMIZATION_PROGRESS_EVENTS: ChatSSEEvent[] = [
  {
    type: "message_start",
    data: {
      strategyId: "strat-opt",
      strategy: {
        id: "strat-opt",
        name: "Optimization",
        siteId: "plasmodb",
        recordType: null,
        steps: [],
        rootStepId: null,
        isSaved: false,
        createdAt: "2025-02-15T00:00:00Z",
        updatedAt: "2025-02-15T00:00:00Z",
      },
    },
  },
  {
    type: "tool_call_start",
    data: {
      id: "tc-opt",
      name: "optimize_search_parameters",
      arguments: {},
    },
  },
  {
    type: "optimization_progress",
    data: {
      optimizationId: "opt-001",
      status: "started",
      totalTrials: 3,
      currentTrial: 0,
    },
  },
  {
    type: "optimization_progress",
    data: {
      optimizationId: "opt-001",
      status: "running",
      totalTrials: 3,
      currentTrial: 1,
      trial: {
        trialNumber: 1,
        parameters: { fold_change: "1.8" },
        score: 0.65,
        recall: 0.8,
        falsePositiveRate: 0.25,
        estimatedSize: null,
        positiveHits: null,
        negativeHits: null,
        totalPositives: null,
        totalNegatives: null,
      },
    },
  },
  {
    type: "optimization_progress",
    data: {
      optimizationId: "opt-001",
      status: "running",
      totalTrials: 3,
      currentTrial: 2,
      trial: {
        trialNumber: 2,
        parameters: { fold_change: "3.2" },
        score: 0.78,
        recall: 0.7,
        falsePositiveRate: 0.1,
        estimatedSize: null,
        positiveHits: null,
        negativeHits: null,
        totalPositives: null,
        totalNegatives: null,
      },
    },
  },
  {
    type: "optimization_progress",
    data: {
      optimizationId: "opt-001",
      status: "running",
      totalTrials: 3,
      currentTrial: 3,
      trial: {
        trialNumber: 3,
        parameters: { fold_change: "2.5" },
        score: 0.82,
        recall: 0.75,
        falsePositiveRate: 0.12,
        estimatedSize: null,
        positiveHits: null,
        negativeHits: null,
        totalPositives: null,
        totalNegatives: null,
      },
    },
  },
  {
    type: "optimization_progress",
    data: {
      optimizationId: "opt-001",
      status: "completed",
      totalTrials: 3,
      currentTrial: 3,
      bestTrial: {
        trialNumber: 3,
        parameters: { fold_change: "2.5" },
        score: 0.82,
        recall: null,
        falsePositiveRate: null,
        estimatedSize: null,
        positiveHits: null,
        negativeHits: null,
        totalPositives: null,
        totalNegatives: null,
      },
    },
  },
  {
    type: "tool_call_end",
    data: {
      id: "tc-opt",
      result: JSON.stringify({
        bestTrial: { parameters: { fold_change: "2.5" }, score: 0.82 },
      }),
    },
  },
  {
    type: "assistant_delta",
    data: { messageId: "msg-opt", delta: "Optimization complete." },
  },
  {
    type: "assistant_message",
    data: { messageId: "msg-opt", content: "Optimization complete." },
  },
  { type: "message_end", data: {} },
];

// Phase-scoped agent events
export const DELEGATION_EVENTS: ChatSSEEvent[] = [
  {
    type: "message_start",
    data: {
      strategyId: "strat-del",
      strategy: {
        id: "strat-del",
        name: "Delegation strategy",
        siteId: "plasmodb",
        recordType: null,
        steps: [],
        rootStepId: null,
        isSaved: false,
        createdAt: "2025-02-15T00:00:00Z",
        updatedAt: "2025-02-15T00:00:00Z",
      },
    },
  },
  // Tool calls from phase agent
  {
    type: "tool_call_start",
    data: {
      id: "tc-1",
      name: "search_for_searches",
      arguments: { site_id: "plasmodb", query: "epitope" },
    },
  },
  {
    type: "tool_call_end",
    data: {
      id: "tc-1",
      result: '[{"name":"GenesWithEpitopes"}]',
    },
  },
  {
    type: "tool_call_start",
    data: {
      id: "tc-2",
      name: "create_step",
      arguments: { search_name: "GenesWithEpitopes" },
    },
  },
  {
    type: "tool_call_end",
    data: {
      id: "tc-2",
      result: '{"stepId":"step-d1","searchName":"GenesWithEpitopes"}',
    },
  },
  // Strategy updates from delegation
  {
    type: "strategy_update",
    data: {
      graphId: "strat-del",
      step: {
        id: "step-d1",
        kind: "search",
        displayName: "Delegated epitope search",
        searchName: "GenesWithEpitopes",
        recordType: "transcript",
      },
    },
  },
  {
    type: "assistant_delta",
    data: { messageId: "msg-del", delta: "Delegation complete." },
  },
  {
    type: "assistant_message",
    data: { messageId: "msg-del", content: "Delegation complete." },
  },
  { type: "message_end", data: {} },
];
