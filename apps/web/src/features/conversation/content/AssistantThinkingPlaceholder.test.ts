import { describe, expect, it } from "vitest";

import { selectStatusLabel } from "./AssistantThinkingPlaceholder";

/**
 * A turn that waits for a worker sends no chunks of its own, so the running
 * message says only "Thinking..." while nothing is happening yet. The
 * dispatcher stamps the waiting turn with `data-turn-status {label: "Queued"}`
 * and this selector is what puts that word on screen.
 */

function running(...labels: (string | null)[]) {
  return {
    status: { type: "running" },
    content: labels.map((label) =>
      label === null
        ? { type: "text", text: "hello" }
        : { type: "data-turn-status", data: { label } },
    ),
  };
}

describe("selectStatusLabel", () => {
  it("says Queued while the turn waits for a worker", () => {
    expect(selectStatusLabel(running("Queued"))).toBe("Queued");
  });

  it("moves on to the label the worker sends when it starts the turn", () => {
    expect(selectStatusLabel(running("Queued", "Preparing context"))).toBe(
      "Preparing context",
    );
  });

  it("keeps the last label a turn reported", () => {
    expect(
      selectStatusLabel(running("Queued", "Preparing context", "Thinking...")),
    ).toBe("Thinking...");
  });

  it("falls back to Thinking... when the turn reported no status", () => {
    expect(selectStatusLabel(running(null))).toBe("Thinking...");
  });

  it("ignores an empty label", () => {
    expect(selectStatusLabel(running("Queued", ""))).toBe("Queued");
  });

  it("also accepts the generic data part shape", () => {
    expect(
      selectStatusLabel({
        status: { type: "running" },
        content: [{ type: "data", name: "turn-status", data: { label: "Queued" } }],
      }),
    ).toBe("Queued");
  });

  it("says nothing for a message that is no longer running", () => {
    expect(
      selectStatusLabel({ ...running("Queued"), status: { type: "complete" } }),
    ).toBe(null);
    expect(selectStatusLabel(undefined)).toBe(null);
  });
});

/**
 * `build_strategy` runs no sub-agent, so it sends no status label of its own.
 * The label follows the dispatch cards instead, which is what the trace draws.
 */
describe("selectStatusLabel follows the phase the trace shows", () => {
  function dispatch(toolCallId: string, phase: string, state: string) {
    return { type: "data-sub-agent-call", data: { toolCallId, phase, state } };
  }

  it("says Building while the build dispatch is open, not the last frame label", () => {
    expect(
      selectStatusLabel({
        status: { type: "running" },
        content: [
          { type: "data-turn-status", data: { label: "Framing the strategy..." } },
          dispatch("c1", "frame", "started"),
          dispatch("c1", "frame", "completed"),
          dispatch("c2", "build", "started"),
        ],
      }),
    ).toBe("Building...");
  });

  it("returns to the reported label once every dispatch closed", () => {
    expect(
      selectStatusLabel({
        status: { type: "running" },
        content: [
          { type: "data-turn-status", data: { label: "Thinking..." } },
          dispatch("c2", "build", "started"),
          dispatch("c2", "build", "completed"),
        ],
      }),
    ).toBe("Thinking...");
  });
});
