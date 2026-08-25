/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { DataTaskProgress } from "./DataTaskProgress";

describe("DataTaskProgress", () => {
  it("renders progress message and percentage", () => {
    render(
      <DataTaskProgress
        data={{
          taskId: "t1",
          percent: 0.65,
          message: "Running trial 13/20",
        }}
      />,
    );
    expect(screen.getByTestId("data-task-progress")).toBeInTheDocument();
    expect(screen.getByText("Running trial 13/20")).toBeInTheDocument();
    expect(screen.getByText("65%")).toBeInTheDocument();
  });

  it("progress bar width reflects percent", () => {
    render(
      <DataTaskProgress
        data={{
          taskId: "t1",
          percent: 0.42,
          message: "Almost halfway",
        }}
      />,
    );
    const bar = screen
      .getByTestId("data-task-progress")
      .querySelector("[data-testid='progress-bar-fill']");
    expect(bar).toHaveStyle({ width: "42%" });
  });

  it("renders one bar for a fan-out update, which the log reconciles to one part", () => {
    render(
      <DataTaskProgress
        data={{
          taskId: "t1",
          percent: 0.3,
          message: "Running variant v1",
          toolSpecific: { variantId: "v1" },
        }}
      />,
    );
    expect(screen.getAllByTestId("progress-bar-fill")).toHaveLength(1);
    expect(screen.getByText("Running variant v1")).toBeInTheDocument();
  });
});
