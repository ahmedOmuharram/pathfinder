import { describe, expect, it } from "vitest";

import { runningPhase } from "./runningPhase";

function dispatch(toolCallId: string, phase: string, state: string) {
  return { type: "data-sub-agent-call", data: { toolCallId, phase, state } };
}

describe("the phase a turn is running", () => {
  it("names nothing before the first dispatch", () => {
    expect(runningPhase([{ type: "text" }])).toBe(null);
  });

  it("names the phase whose dispatch is still open", () => {
    expect(runningPhase([dispatch("c1", "frame", "started")])).toBe("frame");
  });

  it("names the newer phase once the first one closed", () => {
    expect(
      runningPhase([
        dispatch("c1", "frame", "started"),
        dispatch("c1", "frame", "completed"),
        dispatch("c2", "build", "started"),
      ]),
    ).toBe("build");
  });

  it("names nothing once every dispatch closed", () => {
    expect(
      runningPhase([
        dispatch("c1", "frame", "started"),
        dispatch("c1", "frame", "completed"),
      ]),
    ).toBe(null);
  });

  it("reads the generic data-part shape the runtime also emits", () => {
    expect(
      runningPhase([
        {
          type: "data",
          name: "sub-agent-call",
          data: { toolCallId: "c1", phase: "verification", state: "started" },
        },
      ]),
    ).toBe("verification");
  });

  it("ignores a payload with no phase", () => {
    expect(
      runningPhase([{ type: "data-sub-agent-call", data: { toolCallId: "c1" } }]),
    ).toBe(null);
  });
});
