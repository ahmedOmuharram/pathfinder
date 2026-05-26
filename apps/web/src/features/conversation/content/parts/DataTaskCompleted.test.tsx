/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { DataTaskCompleted } from "./DataTaskCompleted";

describe("DataTaskCompleted", () => {
  it("renders success state", () => {
    render(
      <DataTaskCompleted data={{ taskId: "t1", status: "success" }} />,
    );
    expect(screen.getByTestId("data-task-completed")).toBeInTheDocument();
    expect(screen.getByText("Task completed")).toBeInTheDocument();
  });

  it("renders failure state with error", () => {
    render(
      <DataTaskCompleted
        data={{ taskId: "t1", status: "failed", error: "Timeout exceeded" }}
      />,
    );
    expect(screen.getByText("Task failed")).toBeInTheDocument();
    expect(screen.getByText("Timeout exceeded")).toBeInTheDocument();
  });
});
