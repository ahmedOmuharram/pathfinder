import { buildUrl, getAuthHeaders } from "./api/http";
import { AppError } from "@/lib/errors/AppError";
import { parseSSEChunk, type RawSSEEvent } from "./sseParser";

export type { RawSSEEvent } from "./sseParser";

type StreamSSEArgs = {
  method?: "GET" | "POST";
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
};

type StreamSSEOptions = {
  onEvent: (event: RawSSEEvent) => void;
  onError?: (error: Error) => void;
  onComplete?: () => void;
  maxRetries?: number;
  retryDelay?: number;
  /** Max milliseconds to wait between SSE chunks before treating the
   *  connection as hung and aborting.  Defaults to 900 000 (15 minutes). */
  readTimeoutMs?: number;
};

function sleep(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms));
}

async function runOnce(
  path: string,
  args: StreamSSEArgs,
  options: StreamSSEOptions,
): Promise<void> {
  const url = buildUrl(path);
  const hasBody = args.body !== undefined;

  const headers: Record<string, string> = {
    ...getAuthHeaders({
      accept: "text/event-stream",
      contentType: hasBody ? "application/json" : undefined,
    }),
    ...(args.headers ?? {}),
  };

  const resp = await fetch(url, {
    method: args.method ?? "POST",
    headers,
    body: hasBody ? JSON.stringify(args.body) : undefined,
    signal: args.signal,
    credentials: "include",
  });

  if (!resp.ok) {
    throw new AppError(
      `SSE request failed: HTTP ${resp.status} ${resp.statusText}`,
      "UNKNOWN",
    );
  }
  if (!resp.body) {
    throw new AppError("SSE response has no body.", "INVARIANT_VIOLATION");
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const readTimeout = options.readTimeoutMs ?? 900_000;

  while (true) {
    // Race the reader against a timeout so we detect hung connections
    // (e.g. model process died but the TCP socket stays open).
    // Use a clearable timeout to avoid leaking handles when the reader wins.
    let timeoutId: ReturnType<typeof setTimeout>;
    const timeoutPromise = new Promise<{
      done: false;
      value: undefined;
      timedOut: true;
    }>((resolve) => {
      timeoutId = setTimeout(
        () => resolve({ done: false, value: undefined, timedOut: true }),
        readTimeout,
      );
    });

    const result = await Promise.race([reader.read(), timeoutPromise]);
    clearTimeout(timeoutId!);

    if ("timedOut" in result && result.timedOut) {
      // Reader.cancel() can throw if the stream is already closed/errored — benign.
      reader.cancel().catch((err) => console.debug("[sse] reader.cancel()", err));
      throw new AppError(
        `No data received for ${Math.round(readTimeout / 1000)}s — connection appears hung.`,
        "TIMEOUT",
      );
    }

    const { done, value } = result as ReadableStreamReadResult<Uint8Array>;
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSSEChunk(buffer);
    buffer = parsed.rest;
    for (const evt of parsed.events) {
      options.onEvent(evt);
    }
  }
}

function isAbortError(err: unknown): boolean {
  if (err instanceof DOMException && err.name === "AbortError") return true;
  if (err instanceof Error) {
    const msg = err.message.toLowerCase();
    if (msg.includes("aborted") || msg.includes("abort") || err.name === "AbortError")
      return true;
  }
  return false;
}

export async function streamSSE(
  path: string,
  args: StreamSSEArgs,
  options: StreamSSEOptions,
): Promise<void> {
  const maxRetries = options.maxRetries ?? 0;
  const retryDelay = options.retryDelay ?? 500;

  for (let attempt = 0; ; attempt++) {
    try {
      await runOnce(path, args, options);
      options.onComplete?.();
      return;
    } catch (e) {
      if (isAbortError(e)) {
        options.onComplete?.();
        return;
      }
      const err = e instanceof Error ? e : new Error(String(e));
      options.onError?.(err);
      if (attempt >= maxRetries) throw err;
      await sleep(retryDelay);
    }
  }
}

/**
 * Convenience wrapper around {@link streamSSE} that automatically parses
 * each event's data as JSON before invoking the callback.
 *
 * Use this for SSE streams where every `data:` payload is valid JSON
 * (e.g. experiment progress events).
 */
export async function streamSSEParsed<T = unknown>(
  path: string,
  args: StreamSSEArgs,
  options: Omit<StreamSSEOptions, "onEvent"> & {
    onFrame: (frame: { event: string; data: T }) => void;
  },
): Promise<void> {
  const { onFrame, ...rest } = options;
  return streamSSE(path, args, {
    ...rest,
    onEvent: (raw) => {
      try {
        onFrame({ event: raw.type, data: JSON.parse(raw.data) as T });
      } catch (e) {
        console.warn("[SSE] Failed to parse event data:", raw.type, raw.data, e);
      }
    },
  });
}
