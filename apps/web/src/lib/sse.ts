import { buildUrl, getAuthHeaders } from "./api/http";
import { AppError } from "@/shared/errors/AppError";

export type RawSSEEvent = { type: string; data: string };

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

function parseSSEChunk(buffer: string): { events: RawSSEEvent[]; rest: string } {
  const events: RawSSEEvent[] = [];
  // SSE messages are separated by a blank line.
  const parts = buffer.split(/\r?\n\r?\n/);
  const rest = parts.pop() ?? "";

  for (const part of parts) {
    const lines = part.split(/\r?\n/);
    let type = "message";
    const dataLines: string[] = [];

    for (const line of lines) {
      if (line.startsWith("event:")) {
        type = line.slice("event:".length).trim() || type;
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice("data:".length).trimStart());
      }
    }

    // Ignore keep-alives that have no data.
    if (dataLines.length === 0) continue;
    events.push({ type, data: dataLines.join("\n") });
  }

  return { events, rest };
}

async function runOnce(
  path: string,
  args: StreamSSEArgs,
  options: StreamSSEOptions,
): Promise<void> {
  const url = buildUrl(path);
  const hasBody = args.body !== undefined;

  const headers: Record<string, string> = {
    ...getAuthHeaders(undefined, {
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
    const result = await Promise.race([
      reader.read(),
      sleep(readTimeout).then(
        () => ({ done: false, value: undefined, timedOut: true }) as const,
      ),
    ]);

    if ("timedOut" in result && result.timedOut) {
      reader.cancel().catch(() => {});
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
      const err = e instanceof Error ? e : new Error(String(e));
      options.onError?.(err);
      if (attempt >= maxRetries) throw err;
      await sleep(retryDelay);
    }
  }
}
