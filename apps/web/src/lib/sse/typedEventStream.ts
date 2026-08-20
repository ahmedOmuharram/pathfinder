/**
 * Shared helper for consuming simple typed-event SSE streams.
 *
 * Used by experiment/sweep/seed/task routes, not by chat. Chat goes through
 * `DurableChatTransport` and the AI SDK UI message stream protocol.
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

import {
  extractErrorMessage,
  getAuthHeaders,
  parseResponseBody,
} from "@/lib/api/http";

export interface TypedEventStreamOptions {
  /** Abort signal forwarded to `fetch` and the body reader. */
  signal?: AbortSignal;
  /** HTTP method. Defaults to `"GET"`. */
  method?: "GET" | "POST";
  /**
   * Optional request body. When set, it is JSON-stringified and the
   * `Content-Type: application/json` header is added automatically.
   */
  body?: unknown;
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
  const { signal, method = "GET", body } = options;
  const hasBody = body !== undefined;

  const init: RequestInit = {
    method,
    credentials: "include",
    headers: getAuthHeaders({
      accept: "text/event-stream",
      ...(hasBody ? { contentType: "application/json" } : {}),
    }),
  };
  if (hasBody) init.body = JSON.stringify(body);
  if (signal !== undefined) init.signal = signal;

  const resp = await fetch(url, init);

  if (!resp.ok) {
    const detail = extractErrorMessage(await parseResponseBody(resp));
    const reason = detail === null ? "" : `: ${detail}`;
    throw new Error(`stream failed: ${resp.status}${reason}`);
  }
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
        // Malformed frame. Skipped.
      }
      boundary = buffer.indexOf("\n\n");
    }
  }
}
