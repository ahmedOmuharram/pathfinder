/**
 * Realistic SSE event sequences for integration-style frontend tests.
 *
 * These match what the backend actually produces during live WDK flows,
 * including real PlasmoDB search names, gene IDs, and parameter values.
 */

import type { ChatSSEEvent } from "@/lib/sse_events";

// All event types (including graph_plan, message_end, etc.) are part of
// the ChatSSEEvent union — no broad type hack needed.

// Execute mode: single-step epitope search with tool calls + build
export const EXECUTE_EPITOPE_SEARCH_EVENTS: ChatSSEEvent[] = [
  {
    type: "message_start",
    data: {
      strategyId: "strat-001",
      strategy: {
        id: "strat-001",
        name: "New Conversation",
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
  // Tool call: search_for_searches
  {
    type: "tool_call_start",
    data: {
      id: "tc-1",
      name: "search_for_searches",
      arguments: { site_id: "plasmodb", query: "epitope antigen" },
    },
  },
  {
    type: "tool_call_end",
    data: {
      id: "tc-1",
      result: JSON.stringify([
        {
          name: "GenesWithEpitopes",
          displayName: "Genes with epitope evidence (P. falciparum)",
          description:
            "Identify genes with predicted or experimentally validated epitopes",
          recordType: "transcript",
        },
      ]),
    },
  },
  // Tool call: create_step
  {
    type: "tool_call_start",
    data: {
      id: "tc-2",
      name: "create_step",
      arguments: {
        search_name: "GenesWithEpitopes",
        record_type: "transcript",
        parameters: {
          organism: '["Plasmodium falciparum 3D7"]',
          epitope_confidence: '["High","Medium"]',
        },
        display_name: "P. falciparum epitope genes",
      },
    },
  },
  {
    type: "tool_call_end",
    data: {
      id: "tc-2",
      result: JSON.stringify({
        stepId: "step-001",
        searchName: "GenesWithEpitopes",
        displayName: "P. falciparum epitope genes",
        recordType: "transcript",
        graphId: "strat-001",
        graphName: "New Conversation",
        parameters: {
          organism: ["Plasmodium falciparum 3D7"],
          epitope_confidence: ["High", "Medium"],
        },
      }),
    },
  },
  // Strategy update from create_step
  {
    type: "strategy_update",
    data: {
      graphId: "strat-001",
      step: {
        stepId: "step-001",
        kind: "search",
        displayName: "P. falciparum epitope genes",
        searchName: "GenesWithEpitopes",
        recordType: "transcript",
        parameters: {
          organism: ["Plasmodium falciparum 3D7"],
          epitope_confidence: ["High", "Medium"],
        },
        graphName: "New Conversation",
      },
    },
  },
  // Tool call: build_strategy
  {
    type: "tool_call_start",
    data: {
      id: "tc-3",
      name: "build_strategy",
      arguments: { strategy_name: "Epitope vaccine targets", record_type: "transcript" },
    },
  },
  {
    type: "tool_call_end",
    data: {
      id: "tc-3",
      result: JSON.stringify({
        graphId: "strat-001",
        wdkStrategyId: 987654,
        wdkUrl: "https://plasmodb.org/plasmo/app/workspace/strategies/987654",
        name: "Epitope vaccine targets",
        recordType: "transcript",
        plan: {
          recordType: "transcript",
          root: {
            id: "step-001",
            searchName: "GenesWithEpitopes",
            parameters: {
              organism: ["Plasmodium falciparum 3D7"],
              epitope_confidence: ["High", "Medium"],
            },
          },
        },
      }),
    },
  },
  // Graph plan from build_strategy
  {
    type: "graph_plan",
    data: {
      graphId: "strat-001",
      plan: {
        recordType: "transcript",
        root: {
          id: "step-001",
          searchName: "GenesWithEpitopes",
          parameters: {
            organism: ["Plasmodium falciparum 3D7"],
            epitope_confidence: ["High", "Medium"],
          },
        },
      },
      name: "Epitope vaccine targets",
      recordType: "transcript",
    },
  },
  // Strategy meta
  {
    type: "strategy_meta",
    data: {
      graphId: "strat-001",
      name: "Epitope vaccine targets",
      recordType: "transcript",
    },
  },
  // Strategy link with WDK ID
  {
    type: "strategy_link",
    data: {
      graphId: "strat-001",
      wdkStrategyId: 987654,
      wdkUrl: "https://plasmodb.org/plasmo/app/workspace/strategies/987654",
      name: "Epitope vaccine targets",
    },
  },
  // Assistant message deltas
  {
    type: "assistant_delta",
    data: {
      messageId: "msg-001",
      delta: "I've built a strategy for P. falciparum ",
    },
  },
  {
    type: "assistant_delta",
    data: {
      messageId: "msg-001",
      delta: "genes with high or medium epitope evidence.",
    },
  },
  // Final assistant message
  {
    type: "assistant_message",
    data: {
      messageId: "msg-001",
      content:
        "I've built a strategy for P. falciparum genes with high or medium epitope evidence.",
    },
  },
  { type: "message_end", data: {} },
];

// Optimization progress events
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

// Sub-kani delegation events
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
  // Tool call: delegate_strategy_subtasks
  {
    type: "tool_call_start",
    data: {
      id: "tc-del",
      name: "delegate_strategy_subtasks",
      arguments: { goal: "Build a multi-step gene strategy" },
    },
  },
  // Sub-kani events
  {
    type: "subkani_task_start",
    data: { task: "delegate:build-step-1" },
  },
  {
    type: "subkani_tool_call_start",
    data: {
      task: "delegate:build-step-1",
      id: "sub-tc-1",
      name: "search_for_searches",
      arguments: { site_id: "plasmodb", query: "epitope" },
    },
  },
  {
    type: "subkani_tool_call_end",
    data: {
      task: "delegate:build-step-1",
      id: "sub-tc-1",
      result: '[{"name":"GenesWithEpitopes"}]',
    },
  },
  {
    type: "subkani_tool_call_start",
    data: {
      task: "delegate:build-step-1",
      id: "sub-tc-2",
      name: "create_step",
      arguments: { search_name: "GenesWithEpitopes" },
    },
  },
  {
    type: "subkani_tool_call_end",
    data: {
      task: "delegate:build-step-1",
      id: "sub-tc-2",
      result: '{"stepId":"step-d1","searchName":"GenesWithEpitopes"}',
    },
  },
  {
    type: "subkani_task_end",
    data: { task: "delegate:build-step-1", status: "done" },
  },
  // Strategy updates from delegation
  {
    type: "strategy_update",
    data: {
      graphId: "strat-del",
      step: {
        stepId: "step-d1",
        kind: "search",
        displayName: "Delegated epitope search",
        searchName: "GenesWithEpitopes",
        recordType: "transcript",
      },
    },
  },
  {
    type: "tool_call_end",
    data: {
      id: "tc-del",
      result: '{"status":"done","stepsCreated":1}',
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
