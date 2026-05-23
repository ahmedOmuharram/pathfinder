/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { DataPartRenderer } from "./DataPartRenderer";

// Test the DataPartRenderer dispatch directly since MessageRenderer
// requires the full assistant-ui runtime provider tree which is
// integration-tested via ChatThread.test.tsx.

describe("DataPartRenderer dispatch", () => {
  it("dispatches data-sub-agent-call to the correct component", () => {
    render(
      <DataPartRenderer
        kind="data-sub-agent-call"
        data={{
          subAgent: "scope_problem",
          phase: "scoping",
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
