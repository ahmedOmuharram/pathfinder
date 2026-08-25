/**
 * Protocol-conformant SSE frames for route-mocked chat responses.
 *
 * PROTOCOL.md section 3: an event frame is exactly `id: <cursor>` +
 * `data: <payload>` + blank line, and a client MUST reject any other shape.
 * The terminal `[DONE]` payload rides an event frame too. The cursor counter
 * is global and starts far above any real event id, so a mocked tail always
 * sorts after the conversation's snapshot cursor. The client persists the
 * `[DONE]` cursor per thread, so a spec must not read a real tail on a
 * thread it already answered with a mocked one.
 */

let cursor = 1_000_000_000_000;

export function sseFrame(obj: unknown): string {
  cursor += 1;
  return `id: ${cursor}\ndata: ${JSON.stringify(obj)}\n\n`;
}

export function sseDone(): string {
  cursor += 1;
  return `id: ${cursor}\ndata: [DONE]\n\n`;
}

export function uiMessageStreamHeaders(): Record<string, string> {
  return {
    "content-type": "text/event-stream",
    "cache-control": "no-cache",
    "x-vercel-ai-ui-message-stream": "v1",
  };
}
