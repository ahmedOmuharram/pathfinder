/**
 * @vitest-environment jsdom
 */
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { SessionBlock } from "../SessionBlock";

const enteredAt = "2026-04-26T15:30:00Z";
const exitedAt = "2026-04-26T15:38:00Z";

describe("SessionBlock", () => {
  it("renders header with entered time and 'running' when no exit", () => {
    render(
      <SessionBlock kind="validate" enteredAt={enteredAt} exitedAt={null}>
        inner content
      </SessionBlock>,
    );
    const header = screen.getByTestId("specialist-session-toggle");
    expect(header.textContent).toMatch(/Validate session/);
    expect(header.textContent).toMatch(/running/);
    expect(screen.getByTestId("specialist-session-body")).toBeInTheDocument();
  });

  it("auto-collapses on first render after exit and shows exited time in header", () => {
    render(
      <SessionBlock
        kind="research"
        enteredAt={enteredAt}
        exitedAt={exitedAt}
        collapsedSummary="Found PfEMP1 references"
      >
        body
      </SessionBlock>,
    );
    expect(screen.queryByTestId("specialist-session-body")).not.toBeInTheDocument();
    const header = screen.getByTestId("specialist-session-toggle");
    expect(header.textContent).toMatch(/Research session/);
    expect(header.textContent).toMatch(/exited/);
    expect(header.textContent).toMatch(/Found PfEMP1 references/);
  });

  it("re-expands when the user clicks the toggle", () => {
    render(
      <SessionBlock kind="validate" enteredAt={enteredAt} exitedAt={exitedAt}>
        body
      </SessionBlock>,
    );
    expect(screen.queryByTestId("specialist-session-body")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("specialist-session-toggle"));
    expect(screen.getByTestId("specialist-session-body")).toBeInTheDocument();
  });

  it("starts expanded when no exit yet, then user can collapse manually", () => {
    render(
      <SessionBlock kind="validate" enteredAt={enteredAt} exitedAt={null}>
        body
      </SessionBlock>,
    );
    expect(screen.getByTestId("specialist-session-body")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("specialist-session-toggle"));
    expect(screen.queryByTestId("specialist-session-body")).not.toBeInTheDocument();
  });
});
