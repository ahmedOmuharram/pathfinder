/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { DataToolApprovalRequest } from "./DataToolApprovalRequest";

describe("DataToolApprovalRequest", () => {
  it("renders approval request with tool name", () => {
    render(
      <DataToolApprovalRequest
        data={{
          toolCallId: "tc1",
          toolName: "delete_step",
          args: { stepId: "s1" },
        }}
      />,
    );
    expect(screen.getByTestId("data-tool-approval-request")).toBeInTheDocument();
    expect(screen.getByText("delete_step")).toBeInTheDocument();
    expect(screen.getByText("Approval required")).toBeInTheDocument();
  });
});
