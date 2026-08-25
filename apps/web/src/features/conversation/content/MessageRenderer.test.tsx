/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { DataPartRenderer } from "./DataPartRenderer";
import { dataPartRenderers } from "./dataPartRegistry";
import { selectAssistantErrorDetail, toolUIState } from "./MessageRenderer";
import { USER_QUESTION_ANSWERS_PART_TYPE } from "../rail/consultActions";

// Test the DataPartRenderer dispatch directly since MessageRenderer
// requires the full assistant-ui runtime provider tree which is
// integration-tested via ChatThread.test.tsx.

describe("toolUIState", () => {
  it("marks a tool waiting on the user as approval-requested, not running", () => {
    expect(toolUIState("requires-action", undefined)).toBe("approval-requested");
  });

  it("maps the remaining assistant-ui statuses to tool card states", () => {
    expect(toolUIState("running", undefined)).toBe("input-available");
    expect(toolUIState("incomplete", undefined)).toBe("output-error");
    expect(toolUIState("complete", undefined)).toBe("input-streaming");
    expect(toolUIState("complete", { ok: true })).toBe("output-available");
  });
});

describe("selectAssistantErrorDetail", () => {
  const failed = { type: "incomplete", reason: "error", error: "boom" };

  it("reads the live error off a message that carries no failure part", () => {
    expect(
      selectAssistantErrorDetail({ status: failed, content: [{ type: "text" }] }),
    ).toBe("boom");
  });

  it("says nothing once the turn carries its own failure part", () => {
    // The part is durable and says the same thing, so the live card would be
    // a second copy of one failure.
    expect(
      selectAssistantErrorDetail({
        status: failed,
        content: [{ type: "text" }, { type: "data-turn-failed" }],
      }),
    ).toBeNull();
  });

  it("also recognises the generic data part shape", () => {
    expect(
      selectAssistantErrorDetail({
        status: failed,
        content: [{ type: "data", name: "turn-failed" }],
      }),
    ).toBeNull();
  });

  it("says nothing for a turn the user stopped", () => {
    expect(
      selectAssistantErrorDetail({
        status: { type: "incomplete", reason: "cancelled" },
        content: [],
      }),
    ).toBeNull();
  });

  it("says nothing for a turn that finished", () => {
    expect(
      selectAssistantErrorDetail({ status: { type: "complete" }, content: [] }),
    ).toBeNull();
  });
});

describe("dataPartRenderers", () => {
  it("registers the answers part the consult carousel posts back", () => {
    const shortName = USER_QUESTION_ANSWERS_PART_TYPE.replace(/^data-/, "");
    expect(Object.hasOwn(dataPartRenderers, shortName)).toBe(true);
  });

  it("keeps strategy-revision registered for SupersededBadge", () => {
    expect(Object.hasOwn(dataPartRenderers, "strategy-revision")).toBe(true);
  });

  it("has no entry for kinds nothing emits", () => {
    expect(Object.hasOwn(dataPartRenderers, "plan-slot-answers")).toBe(false);
    expect(Object.hasOwn(dataPartRenderers, "decision-answers")).toBe(false);
    expect(Object.hasOwn(dataPartRenderers, "tool-approval-request")).toBe(false);
    expect(Object.hasOwn(dataPartRenderers, "tool-approval-result")).toBe(false);
  });
});

describe("DataPartRenderer dispatch", () => {
  it("dispatches data-sub-agent-call to the correct component", () => {
    render(
      <DataPartRenderer
        kind="data-sub-agent-call"
        data={{
          subAgent: "frame_problem",
          phase: "frame",
          state: "started",
          summary: "Framing the problem",
          succeeded: null,
        }}
      />,
    );
    expect(screen.getByTestId("data-sub-agent-call")).toBeInTheDocument();
  });

  it("dispatches data-memory-retrieved to the correct component", () => {
    render(
      <DataPartRenderer
        kind="data-memory-retrieved"
        data={{
          memories: [{ key: "k1", kind: "gene_set", name: "Kinases", score: 1 }],
        }}
      />,
    );
    expect(screen.getByTestId("data-memory-retrieved")).toBeInTheDocument();
  });

  it("renders nothing for a task part the started card owns", () => {
    const { container } = render(
      <DataPartRenderer
        kind="data-task-completed"
        data={{ taskId: "t1", status: "success" }}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("dispatches data-strategy-link to the correct component", () => {
    render(
      <DataPartRenderer
        kind="data-strategy-link"
        data={{
          strategyId: "s1",
          url: "https://plasmodb.org/s1",
          title: "Test",
        }}
      />,
    );
    expect(screen.getByTestId("data-strategy-link")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Test" })).toBeInTheDocument();
  });

  it("dispatches data-gene-set to the correct component", () => {
    render(
      <DataPartRenderer
        kind="data-gene-set"
        data={{
          geneSetId: "gs1",
          name: "Test Set",
          geneCount: 42,
          siteId: "plasmodb",
        }}
      />,
    );
    expect(screen.getByTestId("data-gene-set")).toBeInTheDocument();
  });
});
