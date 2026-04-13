/**
 * Realistic SSE event sequence for a single-step epitope search
 * with tool calls + build. Matches actual PlasmoDB backend output.
 */

import type { ChatSSEEvent } from "@/lib/sse_events";

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
        id: "step-001",
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
  {
    type: "strategy_update",
    data: {
      graphId: "strat-001",
      step: {
        id: "step-001",
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
  {
    type: "strategy_meta",
    data: {
      graphId: "strat-001",
      name: "Epitope vaccine targets",
      recordType: "transcript",
    },
  },
  {
    type: "strategy_link",
    data: {
      graphId: "strat-001",
      wdkStrategyId: 987654,
      wdkUrl: "https://plasmodb.org/plasmo/app/workspace/strategies/987654",
      name: "Epitope vaccine targets",
    },
  },
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
