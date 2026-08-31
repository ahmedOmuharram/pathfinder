import { describe, expect, it } from "vitest";

import { messageAnchorId, taskResultHref } from "./taskResult";

const FIGURES: ReadonlySet<string> = new Set([
  "data-enrichment-results",
  "data-eda.viz",
]);

function completed(taskId: string) {
  return { type: "data-task-completed", data: { taskId, status: "success" } };
}

describe("the link from a task to what it produced", () => {
  it("names nothing while the task is still running", () => {
    const messages = [
      {
        id: "m1",
        parts: [{ type: "data-background-task-started", data: { taskId: "t1" } }],
      },
    ];
    expect(taskResultHref(messages, "t1", FIGURES)).toBe(null);
  });

  it("points at the turn that carries the figure the task produced", () => {
    const messages = [
      {
        id: "m1",
        parts: [
          { type: "data-background-task-started", data: { taskId: "t1" } },
          completed("t1"),
        ],
      },
      { id: "m2", parts: [{ type: "data-enrichment-results", data: {} }] },
    ];
    expect(taskResultHref(messages, "t1", FIGURES)).toBe(`#${messageAnchorId("m2")}`);
  });

  it("points at the prose turn when the result drew no figure", () => {
    const messages = [
      { id: "m1", parts: [completed("t1")] },
      { id: "m2", parts: [{ type: "text", text: "The comparison finished." }] },
    ];
    expect(taskResultHref(messages, "t1", FIGURES)).toBe(`#${messageAnchorId("m2")}`);
  });

  it("points at the completion's own turn when it carries the figure", () => {
    const messages = [
      {
        id: "m1",
        parts: [completed("t1"), { type: "data-eda.viz", data: {} }],
      },
    ];
    expect(taskResultHref(messages, "t1", FIGURES)).toBe(`#${messageAnchorId("m1")}`);
  });

  it("ignores another task's completion", () => {
    const messages = [
      { id: "m1", parts: [completed("t2")] },
      { id: "m2", parts: [{ type: "text", text: "done" }] },
    ];
    expect(taskResultHref(messages, "t1", FIGURES)).toBe(null);
  });

  it("names nothing when the completion turn produced nothing to read", () => {
    const messages = [{ id: "m1", parts: [completed("t1")] }];
    expect(taskResultHref(messages, "t1", FIGURES)).toBe(null);
  });
});
