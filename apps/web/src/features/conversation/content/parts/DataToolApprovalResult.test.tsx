/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { DataToolApprovalResult } from "./DataToolApprovalResult";

describe("DataToolApprovalResult", () => {
  it("renders approved state", () => {
    render(
      <DataToolApprovalResult
        data={{ toolCallId: "tc1", approved: true }}
      />,
    );
    expect(
      screen.getByTestId("data-tool-approval-result"),
    ).toBeInTheDocument();
    expect(screen.getByText("Approved")).toBeInTheDocument();
  });

  it("renders rejected state with reason", () => {
    render(
      <DataToolApprovalResult
        data={{
          toolCallId: "tc1",
          approved: false,
          reason: "Too destructive",
        }}
      />,
    );
    expect(screen.getByText("Rejected")).toBeInTheDocument();
    expect(screen.getByText(/Too destructive/)).toBeInTheDocument();
  });
});
