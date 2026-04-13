/**
 * Shared helper for consuming simple typed-event SSE streams.
 *
 * Used by experiment/sweep/seed routes — NOT for chat.  Chat goes through
 * `@ai-sdk/react` and the Vercel AI SDK wire format.
 *
 * The async generator fetches the given URL, parses `event:` / `data:`
 * frames out of the response body, and yields each `data:` payload as
 * `T` (after `JSON.parse`).  The stream ends when:
 *
 * - the server emits `data: [DONE]`, or
 * - the response body's reader signals EOF.
 *
 * Malformed frames (non-JSON payloads) are silently skipped.
 */

export interface TypedEventStreamOptions {
  /** Abort signal forwarded to `fetch` and the body reader. */
  signal?: AbortSignal;
  /** Override for `fetch`'s `credentials`. Defaults to `"include"`. */
  credentials?: RequestCredentials;
  /** HTTP method — defaults to `"GET"`. */
  method?: "GET" | "POST";
  /**
   * Optional request body. When set, it is JSON-stringified and the
   * `content-type: application/json` header is added automatically.
   */
  body?: unknown;
  /** Additional headers merged on top of `accept` and `content-type`. */
  headers?: HeadersInit;
}

function extractDataLine(frame: string): string | null {
  let dataLine: string | null = null;
  for (const line of frame.split("\n")) {
    if (line.startsWith("data: ")) dataLine = line.slice(6);
  }
  return dataLine;
}

export async function* streamTypedEvents<T>(
  url: string,
  options: TypedEventStreamOptions = {},
): AsyncGenerator<T> {
  const { signal, credentials = "include", method = "GET", body, headers } = options;
  const hasBody = body !== undefined;

  const init: RequestInit = {
    method,
    credentials,
    headers: {
      accept: "text/event-stream",
      ...(hasBody ? { "content-type": "application/json" } : {}),
      ...(headers ?? {}),
    },
  };
  if (hasBody) init.body = JSON.stringify(body);
  if (signal !== undefined) init.signal = signal;

  const resp = await fetch(url, init);

  if (!resp.ok) throw new Error(`stream failed: ${resp.status}`);
  const respBody = resp.body;
  if (respBody === null) throw new Error("no response body");

  const reader = respBody.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      const dataLine = extractDataLine(frame);
      if (dataLine === null) {
        boundary = buffer.indexOf("\n\n");
        continue;
      }
      if (dataLine === "[DONE]") return;
      try {
        yield JSON.parse(dataLine) as T;
      } catch {
        // Malformed frame — skip silently.
      }
      boundary = buffer.indexOf("\n\n");
    }
  }
}
