/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { IntentSection } from "./LedgerPanelSections";

describe("IntentSection", () => {
  it("renders the classification, goal, and differential sides", () => {
    render(
      <IntentSection
        intent={{
          classification: "NEW_STRATEGY",
          inferredGoal: "Find kinase drug targets",
          isDifferential: true,
          differentialSides: ["expressed", "not expressed"],
        }}
      />,
    );
    expect(screen.getByText("NEW_STRATEGY")).toBeInTheDocument();
    expect(screen.getByText("Find kinase drug targets")).toBeInTheDocument();
    expect(screen.getByText("expressed")).toBeInTheDocument();
  });

  it("shows 'Not classified yet' for null", () => {
    render(<IntentSection intent={null} />);
    expect(screen.getByText(/not classified yet/i)).toBeInTheDocument();
  });

  it("shows 'Not classified yet' for undefined (the exclude_none wire gap) — does not crash", () => {
    render(<IntentSection intent={undefined} />);
    expect(screen.getByText(/not classified yet/i)).toBeInTheDocument();
  });
});
