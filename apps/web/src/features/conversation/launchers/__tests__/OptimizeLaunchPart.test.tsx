/**
 * @vitest-environment jsdom
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { OptimizeLaunchPart } from "../OptimizeLaunchPart";

describe("OptimizeLaunchPart", () => {
  it("renders the launch config card", () => {
    render(
      <OptimizeLaunchPart
        data={{
          stepId: 42,
          paramKeys: ["min_score", "max_evalue"],
          criterion: "match the gold gene set",
          budget: 25,
          modelId: "anthropic/claude-sonnet-4",
        }}
      />,
    );
    expect(screen.getByTestId("data-optimize-launch")).toBeInTheDocument();
    expect(screen.getByText(/Optimize launch/i)).toBeInTheDocument();
    expect(screen.getByText(/match the gold gene set/)).toBeInTheDocument();
    expect(screen.getByText(/min_score/)).toBeInTheDocument();
    expect(screen.getByText(/max_evalue/)).toBeInTheDocument();
    expect(screen.getByText(/25/)).toBeInTheDocument();
  });

  it("omits the model row when modelId is null", () => {
    render(
      <OptimizeLaunchPart
        data={{
          stepId: 7,
          paramKeys: ["x"],
          criterion: "c",
          budget: 10,
          modelId: null,
        }}
      />,
    );
    expect(screen.queryByText(/Model:/)).not.toBeInTheDocument();
  });
});
