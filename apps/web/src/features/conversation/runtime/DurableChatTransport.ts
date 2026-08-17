import {
  HttpChatTransport,
  type HttpChatTransportInitOptions,
  type UIMessage,
  type UIMessageChunk,
  uiMessageChunkSchema,
  parseJsonEventStream,
} from "ai";
import { type ParseResult } from "@ai-sdk/provider-utils";
import { EventSourceParserStream } from "eventsource-parser/stream";

import { readCursor, writeCursor } from "./eventCursor";
import { isTransportChunk } from "./replayChunks";

interface DurableChatTransportOptions<
  UI_MESSAGE extends UIMessage,
> extends HttpChatTransportInitOptions<UI_MESSAGE> {
  conversationId: string;
  eventsUrlFor: (conversationId: string) => string;
}

export class DurableChatTransport<
  UI_MESSAGE extends UIMessage,
> extends HttpChatTransport<UI_MESSAGE> {
  private readonly conversationId: string;

  constructor(options: DurableChatTransportOptions<UI_MESSAGE>) {
    const { conversationId, eventsUrlFor, ...base } = options;
    super({
      ...base,
      prepareReconnectToStreamRequest: ({ headers, credentials }) => {
        const result: {
          api: string;
          headers?: HeadersInit;
          credentials?: RequestCredentials;
        } = {
          api: `${eventsUrlFor(conversationId)}?after=${readCursor(conversationId)}`,
        };
        if (headers !== undefined) result.headers = headers;
        if (credentials !== undefined) result.credentials = credentials;
        return result;
      },
    });
    this.conversationId = conversationId;
  }

  protected processResponseStream(
    stream: ReadableStream<Uint8Array<ArrayBufferLike>>,
  ): ReadableStream<UIMessageChunk> {
    const conversationId = this.conversationId;

    const decoder = new TextDecoder();
    const sseEvents = stream
      .pipeThrough(
        new TransformStream<Uint8Array<ArrayBufferLike>, string>({
          transform(chunk, controller) {
            controller.enqueue(decoder.decode(chunk, { stream: true }));
          },
          flush(controller) {
            controller.enqueue(decoder.decode());
          },
        }),
      )
      .pipeThrough(new EventSourceParserStream());

    const dataOnly = sseEvents.pipeThrough(
      new TransformStream<{ id?: string; event?: string; data: string }, string>({
        transform(event, controller) {
          // Cursor only advances at turn boundaries; mid-turn chunks are
          // unresumable without their StartChunk.
          if (event.data === "[DONE]" && event.id !== undefined && event.id !== "") {
            const parsed = Number.parseInt(event.id, 10);
            if (Number.isFinite(parsed)) writeCursor(conversationId, parsed);
          }
          if (!isTransportChunk(event.data)) return;
          controller.enqueue(event.data);
        },
      }),
    );

    const reframed = new ReadableStream<Uint8Array>({
      async start(controller) {
        const reader = dataOnly.getReader();
        const encoder = new TextEncoder();
        try {
          let next = await reader.read();
          while (!next.done) {
            controller.enqueue(encoder.encode(`data: ${next.value}\n\n`));
            next = await reader.read();
          }
          controller.close();
        } catch (err) {
          controller.error(err);
        }
      },
    });

    return parseJsonEventStream({
      stream: reframed,
      schema: uiMessageChunkSchema,
    }).pipeThrough(
      new TransformStream<ParseResult<UIMessageChunk>, UIMessageChunk>({
        transform(result, controller) {
          if (result.success) controller.enqueue(result.value);
          else controller.error(result.error);
        },
      }),
    );
  }
}
