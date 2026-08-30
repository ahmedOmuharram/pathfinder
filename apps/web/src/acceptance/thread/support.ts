import { createElement, type ReactElement } from "react";
import { render, type RenderResult } from "@testing-library/react";
import {
  AssistantRuntimeProvider,
  ThreadPrimitive,
  useExternalStoreRuntime,
  type ThreadMessageLike,
} from "@assistant-ui/react";
import type { UIMessage } from "ai";
import { reduceSnapshot, type MessagePart } from "@pathfinder/assistant-client";

import {
  AssistantMessage,
  UserMessage,
} from "@/features/conversation/content/MessageRenderer";
import {
  ChatHelpersProvider,
  type ChatHelpers,
} from "@/features/conversation/runtime/chatHelpersContext";
import { useSettingsStore } from "@/state/useSettingsStore";

import recordedTurn from "./recordedTurn.json";

/**
 * Load a module a later batch creates. Returns null while it is absent, so a
 * module gated on it skips instead of failing. The specifier stays a string, so
 * the bundler cannot resolve it at transform time and turn a missing file into
 * a collection error; this is the form `acceptance/eda/support.ts` uses.
 */
export async function loadOrSkip<T>(specifier: string): Promise<T | null> {
  try {
    const loaded: unknown = await import(specifier);
    return loaded as T;
  } catch {
    return null;
  }
}

const TURN_ID = "11111111-1111-1111-1111-111111111111";

/** The recorded turn, as the protocol chunk array the thread reduces. */
export const RECORDED_CHUNKS: readonly unknown[] = recordedTurn;

/**
 * The recorded turn plus the continuation section 6.2 describes: the user
 * approved the sweep, so a second `start` carries the same message id and the
 * call returns. No row is awaiting approval and the trace has settled.
 */
export const SETTLED_CHUNKS: readonly unknown[] = [
  ...RECORDED_CHUNKS,
  { type: "start", messageId: TURN_ID },
  {
    type: "tool-input-start",
    toolCallId: "call_5",
    toolName: "optimize_search_parameters",
  },
  {
    type: "tool-input-available",
    toolCallId: "call_5",
    toolName: "optimize_search_parameters",
    input: {
      target: { wdkStepId: 132, searchName: "GenesByText" },
      controls: { controlSetId: "cs-1" },
    },
  },
  {
    type: "tool-output-available",
    toolCallId: "call_5",
    output: { sweeps: 4, bestMinScore: 0.7 },
  },
  {
    type: "data-tool-summary",
    data: {
      toolCallId: "call_5",
      summary: "4 parameter sweeps scored",
      status: "ok",
    },
  },
  { type: "finish", finishReason: "stop" },
  { type: "done" },
];

/** The started payload of the enrichment task, which puts `geneset_enrichment`
 * on the wire rather than its agent-side name. */
export const ENRICHMENT_TASK_CHUNKS: readonly unknown[] = [
  { type: "start", messageId: "22222222-2222-2222-2222-222222222222" },
  {
    type: "data-background-task-started",
    data: {
      taskId: "00000000-0000-0000-0000-0000000000bb",
      toolName: "geneset_enrichment",
      estimatedDurationSeconds: 120,
    },
  },
  { type: "finish", finishReason: "other" },
  { type: "done" },
];

type AuiContent = Exclude<ThreadMessageLike["content"], string>;
type AuiPart = AuiContent[number];

const TOOL_PREFIX = "tool-";

function toAuiPart(part: MessagePart): AuiPart | null {
  if (part.type === "step-start") return null;
  if (part.type === "text") return { type: "text", text: part.text };
  if (part.type === "reasoning") return { type: "reasoning", text: part.text };
  if (part.type.startsWith(TOOL_PREFIX) && "toolCallId" in part) {
    return {
      type: "tool-call",
      toolCallId: part.toolCallId,
      toolName: part.type.slice(TOOL_PREFIX.length),
      argsText: JSON.stringify(part.input),
      result: part.state === "output-available" ? part.output : undefined,
      isError: part.state === "output-error",
    };
  }
  if ("data" in part) return part;
  return null;
}

interface Turn {
  id: string;
  parts: MessagePart[];
  awaitingApproval: boolean;
}

function reduceOneTurn(chunks: readonly unknown[]): Turn {
  const assistant = reduceSnapshot(chunks).find(
    (message) => message.role === "assistant",
  );
  if (assistant === undefined) throw new Error("the chunk array holds no turn");
  const awaitingApproval = assistant.parts.some(
    (part) => "state" in part && part.state === "approval-requested",
  );
  return { id: assistant.id, parts: assistant.parts, awaitingApproval };
}

function auiMessage(turn: Turn): ThreadMessageLike {
  const content: AuiPart[] = [];
  for (const part of turn.parts) {
    const converted = toAuiPart(part);
    if (converted !== null) content.push(converted);
  }
  return {
    id: turn.id,
    role: "assistant",
    content,
    status: turn.awaitingApproval
      ? { type: "requires-action", reason: "interrupt" }
      : { type: "complete", reason: "stop" },
  };
}

function chatHelpers(turn: Turn): ChatHelpers {
  const message: UIMessage = { id: turn.id, role: "assistant", parts: turn.parts };
  return {
    id: "conv-acceptance",
    messages: [message],
    status: "ready",
    error: undefined,
    setMessages: () => {},
    sendMessage: async () => {},
    regenerate: async () => {},
    stop: async () => {},
    resumeStream: async () => {},
    addToolResult: async () => {},
    addToolOutput: async () => {},
    addToolApprovalResponse: async () => {},
    clearError: () => {},
  };
}

function Harness({ message }: { message: ThreadMessageLike }): ReactElement {
  const runtime = useExternalStoreRuntime<ThreadMessageLike>({
    messages: [message],
    convertMessage: (entry) => entry,
    onNew: async () => undefined,
  });
  return createElement(
    AssistantRuntimeProvider,
    { runtime },
    createElement(ThreadPrimitive.Messages, {
      components: { AssistantMessage, UserMessage },
    }),
  );
}

export interface DevFlags {
  showRaw: boolean;
  showUsage: boolean;
}

/**
 * Render one turn through the thread's own renderer, with the two settings
 * flags set to the values under test.
 */
export function renderTurn(chunks: readonly unknown[], flags: DevFlags): RenderResult {
  useSettingsStore.setState({
    showRawToolCalls: flags.showRaw,
    showTokenUsage: flags.showUsage,
  });
  const turn = reduceOneTurn(chunks);
  return render(
    createElement(
      ChatHelpersProvider,
      { value: chatHelpers(turn) },
      createElement(Harness, { message: auiMessage(turn) }),
    ),
  );
}

/** True when `a` precedes `b` in document order. */
export function precedes(a: Element, b: Element): boolean {
  return (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
}
