/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { DataBackgroundTaskStarted } from "./DataBackgroundTaskStarted";

describe("DataBackgroundTaskStarted", () => {
  it("renders tool name and estimated duration", () => {
    render(
      <DataBackgroundTaskStarted
        data={{
          taskId: "t1",
          toolName: "run_control_tests_on_step",
          estimatedDurationSeconds: 120,
        }}
      />,
    );
    expect(screen.getByTestId("data-background-task-started")).toBeInTheDocument();
    expect(screen.getByText("run_control_tests_on_step")).toBeInTheDocument();
    expect(screen.getByText("~2 min")).toBeInTheDocument();
  });
});
