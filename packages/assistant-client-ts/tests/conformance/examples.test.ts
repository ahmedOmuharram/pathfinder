import { describe, expect, it } from "vitest";

import captured from "../../src/protocol/captured.json" with { type: "json" };
import { type ProtocolChunk, parseChunk } from "../../src/core/chunks.ts";
import { DONE_PAYLOAD, frameText, isDone, parseFrame } from "../../src/core/sse.ts";
import { reduceTurn } from "../../src/core/reduce.ts";

interface Example {
  kind: string;
  json: string;
}

const examples: Example[] = captured.examples;

function wireForm(example: Example): string {
  return JSON.stringify(JSON.parse(example.json));
}

function byKind(kind: string): Example {
  const example = examples.find((candidate) => candidate.kind === kind);
  if (example === undefined) throw new Error(`PROTOCOL.md captures no ${kind}`);
  return example;
}

function chunkFor(kind: string): ProtocolChunk {
  const chunk = parseChunk(wireForm(byKind(kind)));
  if (chunk === undefined) throw new Error(`${kind} is not a chunk object`);
  return chunk;
}

describe("section 8, every captured example", () => {
  it.each(examples.map((example) => [example.kind, example] as const))(
    "%s frames and parses back to the bytes it was",
    (_kind, example) => {
      const payload = wireForm(example);
      const frame = parseFrame(frameText(1, payload));

      expect(frame.data).toBe(payload);
      expect(frame.eventId).toBe(1);
    },
  );

  it.each(examples.map((example) => [example.kind, example] as const))(
    "%s carries no embedded newline on the wire",
    (_kind, example) => {
      expect(wireForm(example)).not.toContain("\n");
    },
  );

  it.each(
    examples
      .filter((example) => example.kind !== "done")
      .map((example) => [example.kind, example] as const),
  )("%s discriminates on the type the document files it under", (kind, example) => {
    const chunk = parseChunk(wireForm(example));

    expect(chunk?.type).toBe(kind);
  });

  it("files the terminator as the literal payload, not as an object", () => {
    const done = byKind("done");

    expect(JSON.parse(done.json)).toBe(DONE_PAYLOAD);
    expect(isDone(parseFrame(frameText(9, DONE_PAYLOAD)))).toBe(true);
    expect(parseChunk(wireForm(done))).toBeUndefined();
  });
});

describe("section 9, a captured turn reduces to one message", () => {
  const turn: ProtocolChunk[] = [
    chunkFor("data-turn-status"),
    chunkFor("start"),
    chunkFor("start-step"),
    chunkFor("text-start"),
    chunkFor("text-delta"),
    chunkFor("text-end"),
    chunkFor("tool-input-start"),
    chunkFor("tool-input-delta"),
    chunkFor("tool-input-available"),
    chunkFor("tool-output-available"),
    chunkFor("data-turn-usage"),
    chunkFor("message-metadata"),
    chunkFor("finish-step"),
    chunkFor("finish"),
  ];

  it("builds the parts the document's rules describe", () => {
    const message = reduceTurn(turn);

    expect(message).toEqual({
      id: "00000000-0000-0000-0000-000000000000",
      role: "assistant",
      errors: [],
      aborted: false,
      finishReason: "stop",
      metadata: { pydantic_ai: { timestamp: "2026-01-01T00:00:00Z" } },
      parts: [
        {
          type: "data-turn-status",
          data: { label: "Preparing context", waitingOnLlm: false },
        },
        { type: "step-start" },
        {
          type: "text",
          text: "You said: which sites do you serve",
          state: "done",
        },
        {
          type: "tool-add",
          toolCallId: "call_add",
          state: "output-available",
          input: { a: 2, b: 3 },
          output: 5,
        },
      ],
    });
  });

  it("keeps the transient usage part out of the history it builds", () => {
    const message = reduceTurn(turn);

    expect(message.parts.some((part) => part.type === "data-turn-usage")).toBe(false);
  });

  it("reports the error chunk without calling the turn failed", () => {
    const message = reduceTurn([
      chunkFor("start"),
      chunkFor("error"),
      chunkFor("finish"),
    ]);

    expect(message.finishReason).toBe("stop");
    expect(message.errors).toHaveLength(1);
    expect(message.errors[0]).toContain("DeferredToolRequests");
  });

  it("keeps a stopped turn stopped across a reload", () => {
    const message = reduceTurn([
      chunkFor("start"),
      chunkFor("data-turn-stopped"),
      chunkFor("finish"),
    ]);

    expect(message.parts).toEqual([{ type: "data-turn-stopped", data: {} }]);
  });

  it("records a tool that failed", () => {
    const message = reduceTurn([
      chunkFor("start"),
      { type: "tool-input-start", toolCallId: "call_wipe", toolName: "wipe" },
      chunkFor("tool-output-error"),
    ]);

    expect(message.parts).toEqual([
      {
        type: "tool-wipe",
        toolCallId: "call_wipe",
        state: "output-error",
        input: undefined,
        errorText: "Tool execution was interrupted by an error.",
      },
    ]);
  });
});
