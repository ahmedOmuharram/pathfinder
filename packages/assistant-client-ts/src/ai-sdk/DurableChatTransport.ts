import {
  DefaultChatTransport,
  type HttpChatTransportInitOptions,
  type UIMessage,
  type UIMessageChunk,
} from "ai";

import { isKnownChunkKind, parseChunk } from "../core/chunks.ts";
import {
  type CursorStore,
  recordFrameCursor,
  tailUrl,
  webStorageCursorStore,
} from "../core/cursor.ts";
import { HANDLED_ENVELOPE_KINDS } from "../core/snapshot.ts";
import { isComment, isDone, readFrames } from "../core/sse.ts";

export interface DurableChatTransportOptions<
  UI_MESSAGE extends UIMessage,
> extends HttpChatTransportInitOptions<UI_MESSAGE> {
  conversationId: string;
  eventsUrlFor: (conversationId: string) => string;
  cursors?: CursorStore;
  /** Called with a chunk this client cannot place, which section 5 says to ignore. */
  onUnhandledChunk?: (chunk: unknown) => void;
}

/**
 * A chat transport over the durable event log. It resumes from the cursor it
 * holds, reads the frames section 3 defines, and drops what a client of this
 * protocol version must ignore before the SDK's chunk schema sees it.
 */
export class DurableChatTransport<
  UI_MESSAGE extends UIMessage,
> extends DefaultChatTransport<UI_MESSAGE> {
  private readonly conversationId: string;
  private readonly cursors: CursorStore;
  private readonly onUnhandledChunk: ((chunk: unknown) => void) | undefined;

  constructor(options: DurableChatTransportOptions<UI_MESSAGE>) {
    const { conversationId, eventsUrlFor, cursors, onUnhandledChunk, ...base } =
      options;
    const store = cursors ?? webStorageCursorStore();
    super({
      ...base,
      prepareReconnectToStreamRequest: ({ headers, credentials }) => {
        const request: {
          api: string;
          headers?: HeadersInit;
          credentials?: RequestCredentials;
        } = {
          api: tailUrl(eventsUrlFor(conversationId), store.read(conversationId)),
        };
        if (headers !== undefined) request.headers = headers;
        if (credentials !== undefined) request.credentials = credentials;
        return request;
      },
    });
    this.conversationId = conversationId;
    this.cursors = store;
    this.onUnhandledChunk = onUnhandledChunk;
  }

  /** Re-frame the payloads this client accepted, for the SDK's own reader. */
  private acceptedPayloads(
    stream: ReadableStream<Uint8Array<ArrayBufferLike>>,
  ): ReadableStream<Uint8Array> {
    const frames = readFrames(stream, { allowTruncatedTail: true });
    const conversationId = this.conversationId;
    const cursors = this.cursors;
    const report = this.onUnhandledChunk;
    const encoder = new TextEncoder();
    return new ReadableStream<Uint8Array>({
      async start(controller) {
        try {
          for await (const frame of frames) {
            recordFrameCursor(cursors, conversationId, frame);
            if (isComment(frame) || isDone(frame) || frame.data === undefined) continue;
            const chunk = parseChunk(frame.data);
            if (chunk === undefined || HANDLED_ENVELOPE_KINDS.has(chunk.type)) continue;
            if (!isKnownChunkKind(chunk.type)) {
              report?.(chunk);
              continue;
            }
            controller.enqueue(encoder.encode(`data: ${frame.data}\n\n`));
          }
          controller.close();
        } catch (err) {
          controller.error(err);
        }
      },
    });
  }

  protected override processResponseStream(
    stream: ReadableStream<Uint8Array<ArrayBufferLike>>,
  ): ReadableStream<UIMessageChunk> {
    return super.processResponseStream(this.acceptedPayloads(stream));
  }
}
