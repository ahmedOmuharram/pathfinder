import {
  useLangGraphRuntime,
  type LangChainMessage,
  type LangChainMessageChunk,
  type LangChainToolCall,
  type LangChainToolCallChunk,
  type LangGraphMessagesEvent,
} from "@assistant-ui/react-langgraph";
import type {
  StreamEvent,
  MessagesPartialEvent,
  MessagesCompleteEvent,
  DataPartKind,
  ToolCallDelta,
} from "@pathfinder/shared";
import type { ReadonlyJSONObject } from "assistant-stream/utils";

import { getAuthHeaders } from "@/lib/api/http";

import { parseSseStream } from "./streamParser";

export interface ChatStreamArgs {
  chatId: string;
  messages: LangChainMessage[];
  parentCheckpointId?: string;
}

export interface CustomEventPayload {
  kind: DataPartKind;
  data: Record<string, unknown>;
}

function extractText(message: LangChainMessage): string {
  const content = message.content;
  if (typeof content === "string") return content;
  const pieces: string[] = [];
  for (const part of content) {
    if (part.type === "text") pieces.push(part.text);
  }
  return pieces.join("");
}

interface ChatRequestBody {
  chatId: string;
  message: string;
  parentCheckpointId?: string;
}

function buildBody(args: ChatStreamArgs): string {
  const last = args.messages[args.messages.length - 1];
  const message = last ? extractText(last) : "";
  const payload: ChatRequestBody = {
    chatId: args.chatId,
    message,
  };
  if (args.parentCheckpointId !== undefined) {
    payload.parentCheckpointId = args.parentCheckpointId;
  }
  return JSON.stringify(payload);
}

function mapToolCallDelta(d: ToolCallDelta, i: number): LangChainToolCallChunk {
  return {
    index: i,
    id: d.toolCallId,
    name: d.toolName ?? "",
    args: d.argumentsDelta ?? "",
  };
}

export interface MessageChunkMeta {
  /** Backend-reported ``provider:model`` string, e.g. ``openai:gpt-4.1-mini``. */
  model?: string;
}

// Convert a MessagesPartialEvent (our backend delta) into an AIMessageChunk
// that the LangGraph accumulator can merge via appendLangChainChunk.
function partialToChunk(
  ev: MessagesPartialEvent & { type: "messages/partial" },
  meta: MessageChunkMeta,
): LangChainMessage[] {
  // ``content`` must always be a string (possibly empty) — assistant-ui's
  // ``appendLangChainChunk`` spreads ``prev.content`` unconditionally on
  // subsequent chunks, and ``convertLangChainMessages`` spreads
  // ``normalizedContent`` on every assistant message render. Omitting
  // ``content`` when the delta is empty leaves ``undefined`` in both paths
  // and crashes with "… is not iterable".
  const chunk: LangChainMessageChunk = {
    id: ev.messageId,
    type: "AIMessageChunk",
    content: ev.delta ?? "",
    ...(meta.model !== undefined && {
      additional_kwargs: { metadata: { model: meta.model } },
    }),
    ...(ev.toolCallDeltas &&
      ev.toolCallDeltas.length > 0 && {
        tool_call_chunks: ev.toolCallDeltas.map(mapToolCallDelta),
      }),
  };

  // appendLangChainChunk expects LangChainMessage — the chunk type is a
  // structural subtype that the accumulator narrows by checking type ===
  // "AIMessageChunk". Cast through unknown to satisfy the nominal union.
  return [chunk as unknown as LangChainMessage];
}

// Convert a MessagesCompleteEvent into a full LangChainMessage.
function completeToMessage(
  ev: MessagesCompleteEvent & { type: "messages/complete" },
  meta: MessageChunkMeta,
): LangChainMessage[] {
  if (ev.role === "ai") {
    const aiMsg: LangChainMessage & { type: "ai" } = {
      id: ev.messageId,
      type: "ai",
      content: ev.content ?? "",
    };
    if (ev.toolCalls && ev.toolCalls.length > 0) {
      aiMsg.tool_calls = ev.toolCalls.map(
        (tc): LangChainToolCall => ({
          id: tc.id,
          name: tc.name,
          args: tc.arguments as ReadonlyJSONObject,
        }),
      );
    }
    const additional: {
      reasoning?: { type: "reasoning"; summary: { type: "summary_text"; text: string }[] };
      metadata?: { model: string };
    } = {};
    if (ev.reasoning !== undefined && ev.reasoning !== "" && ev.reasoning.length > 0) {
      additional.reasoning = {
        type: "reasoning",
        summary: [{ type: "summary_text", text: ev.reasoning }],
      };
    }
    if (meta.model !== undefined) {
      additional.metadata = { model: meta.model };
    }
    if (Object.keys(additional).length > 0) {
      aiMsg.additional_kwargs = additional;
    }
    return [aiMsg];
  }
  if (ev.role === "tool") {
    return [
      {
        id: ev.messageId,
        type: "tool",
        content: ev.content ?? "",
        tool_call_id: ev.toolCallId ?? "",
        name: ev.name ?? "",
        status: "success",
      } satisfies LangChainMessage,
    ];
  }
  if (ev.role === "human") {
    return [
      {
        id: ev.messageId,
        type: "human",
        content: ev.content ?? "",
      } satisfies LangChainMessage,
    ];
  }
  // system
  return [
    {
      id: ev.messageId,
      type: "system",
      content: ev.content ?? "",
    } satisfies LangChainMessage,
  ];
}

type MappedEvent = LangGraphMessagesEvent<LangChainMessage>;

async function* toLangGraphIter(
  iter: AsyncIterable<StreamEvent>,
): AsyncGenerator<MappedEvent> {
  // Track the latest per-phase model so each outgoing ``messages/partial`` /
  // ``messages/complete`` carries it as ``additional_kwargs.metadata.model``.
  // The backend reports the model via ``data-phase-start``'s ``model`` field.
  const meta: MessageChunkMeta = {};
  for await (const ev of iter) {
    switch (ev.type) {
      case "messages/partial":
        yield { event: "messages/partial", data: partialToChunk(ev, meta) };
        break;
      case "messages/complete":
        yield { event: "messages/complete", data: completeToMessage(ev, meta) };
        break;
      case "custom":
        if (ev.kind === "data-phase-start") {
          const payload = ev.data as { model?: unknown };
          if (typeof payload.model === "string" && payload.model !== "") {
            meta.model = payload.model;
          }
        }
        // Custom events route to onCustomEvent via the default branch
        // in useLangGraphMessages. The event name is the custom kind.
        yield { event: ev.kind, data: ev.data };
        break;
      case "updates":
        yield { event: "updates", data: ev };
        break;
      case "interrupts":
        yield {
          event: "updates",
          data: { __interrupt__: ev.interrupts },
        };
        break;
      case "checkpoint":
        yield { event: "checkpoint", data: ev };
        break;
      case "error":
        yield { event: "error", data: ev.message };
        break;
      case "done":
        break;
    }
  }
}

async function fetchAndStream(
  args: ChatStreamArgs,
  signal?: AbortSignal,
): Promise<AsyncGenerator<MappedEvent>> {
  const init: RequestInit = {
    method: "POST",
    headers: getAuthHeaders({
      accept: "text/event-stream",
      contentType: "application/json",
    }),
    body: buildBody(args),
    credentials: "include",
  };
  if (signal !== undefined) init.signal = signal;
  const resp = await fetch("/api/v1/chat", init);
  if (!resp.ok) throw new Error(`Chat request failed: ${resp.status}`);
  return toLangGraphIter(parseSseStream(resp));
}

export function useChatRuntime({
  chatId,
  getCheckpointId,
  onCustomEvent,
  onCheckpoint,
}: {
  chatId: string;
  getCheckpointId?: (threadId: string, parentMessages: LangChainMessage[]) => Promise<string | null>;
  onCustomEvent?: (kind: string, data: unknown) => void;
  onCheckpoint?: (checkpoint: unknown) => void;
}) {
  return useLangGraphRuntime({
    stream: async (messages, opts) => {
      const args: ChatStreamArgs = {
        chatId,
        messages,
      };
      if (opts.checkpointId !== undefined) {
        args.parentCheckpointId = opts.checkpointId;
      }
      return fetchAndStream(args, opts.abortSignal);
    },
    ...(getCheckpointId !== undefined && { getCheckpointId }),
    eventHandlers: {
      onCustomEvent: (type: string, data: unknown) => {
        if (type === "checkpoint") {
          onCheckpoint?.(data);
          return;
        }
        onCustomEvent?.(type, data);
      },
    },
  });
}

// Test entry point: exercises the fetch + parse path without the assistant-ui
// provider tree.
export async function runStreamForTest(
  args: ChatStreamArgs,
): Promise<AsyncGenerator<MappedEvent>> {
  return fetchAndStream(args);
}
