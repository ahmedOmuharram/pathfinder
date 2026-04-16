import type { StreamEvent } from "@pathfinder/shared";

const DECODER = new TextDecoder();

// Yields only frames whose SSE `event:` name is `"stream"`; heartbeats and
// other event names are dropped.
export async function* parseSseStream(
  resp: Response,
): AsyncIterable<StreamEvent> {
  if (!resp.body) return;
  const reader = resp.body.getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += DECODER.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const evName = frame.match(/^event:\s*(\S+)/m)?.[1];
      if (evName !== "stream") continue;
      const dataLine = frame.match(/^data:\s*(.*)$/m)?.[1];
      if (dataLine === undefined || dataLine === "") continue;
      yield JSON.parse(dataLine) as StreamEvent;
    }
  }
}
