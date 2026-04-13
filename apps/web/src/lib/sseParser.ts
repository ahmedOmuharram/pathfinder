/**
 * Shared SSE (Server-Sent Events) chunk parser.
 *
 * Used by both `streamSSE` (fire-and-forget streams) and
 * `subscribeToOperation` (reconnectable subscription streams).
 */

export type RawSSEEvent = { type: string; data: string; id?: string };

function parseSSEFrame(part: string): RawSSEEvent | null {
  if (!part.trim()) return null;
  const lines = part.split(/\r?\n/);
  let type = "message";
  let id: string | undefined;
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith(":")) {
      continue;
    } else if (line.startsWith("event:")) {
      type = line.slice("event:".length).trim() || type;
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    } else if (line.startsWith("id:")) {
      id = line.slice("id:".length).trim();
    }
  }

  if (dataLines.length === 0) return null;
  const event: RawSSEEvent = { type, data: dataLines.join("\n") };
  if (id != null) event.id = id;
  return event;
}

/**
 * Parse a text buffer containing one or more SSE frames.
 *
 * SSE messages are separated by blank lines (`\n\n`).  Each message can
 * contain `event:`, `data:`, and `id:` fields.  Comment lines (`:`)
 * and keep-alive frames with no data are silently dropped.
 *
 * @returns The parsed events and any leftover buffer text that hasn't
 *   been terminated by a blank line yet.
 */
export function parseSSEChunk(
  buffer: string,
  options?: { flushTrailingFrame?: boolean },
): {
  events: RawSSEEvent[];
  rest: string;
} {
  const events: RawSSEEvent[] = [];
  const parts = buffer.split(/\r?\n\r?\n/);
  const rest = parts.pop() ?? "";

  for (const part of parts) {
    const event = parseSSEFrame(part);
    if (event != null) {
      events.push(event);
    }
  }

  if (options?.flushTrailingFrame === true) {
    const trailingEvent = parseSSEFrame(rest);
    if (trailingEvent != null) {
      events.push(trailingEvent);
      return { events, rest: "" };
    }
  }

  return { events, rest };
}
