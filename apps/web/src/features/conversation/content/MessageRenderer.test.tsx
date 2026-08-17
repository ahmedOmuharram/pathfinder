/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { DataPartRenderer } from "./DataPartRenderer";
import { dataPartRenderers } from "./dataPartRegistry";
import { toolUIState } from "./MessageRenderer";
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

  it("dispatches data-task-completed to the correct component", () => {
    render(
      <DataPartRenderer
        kind="data-task-completed"
        data={{ taskId: "t1", status: "success" }}
      />,
    );
    expect(screen.getByTestId("data-task-completed")).toBeInTheDocument();
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
