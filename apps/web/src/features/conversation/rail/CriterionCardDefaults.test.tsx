/**
 * @vitest-environment jsdom
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { LedgerCriterionPayload } from "@pathfinder/shared";
import { FrameDetail } from "./LedgerPanelDetail";

function frameWith(crit: Partial<LedgerCriterionPayload>) {
  return {
    spec: {
      goal: "g",
      interpretedGoal: "g",
      recordType: "transcript",
      organismScope: null,
      title: "t",
      criteria: [
        {
          id: "c1",
          text: "trophozoite expression",
          searchName: "GenesByMicroarray",
          role: "filter",
          resolvedParams: { min_expression_percentile: "90", any_or_all: "any" },
          openParams: [],
          confidence: 1,
          ...crit,
        },
      ],
      dropped: [],
    },
  } as never;
}

describe("a value the search chose, not the request", () => {
  it("marks an assumed parameter", () => {
    // A default is a safe choice and a silent one. The researcher has to be
    // able to see which values they never asked for.
    render(<FrameDetail frame={frameWith({ defaultedParams: ["any_or_all"] })} />);

    expect(screen.getByTitle(/assumed/i)).toBeInTheDocument();
  });

  it("leaves a stated parameter unmarked", () => {
    render(<FrameDetail frame={frameWith({ defaultedParams: ["any_or_all"] })} />);

    expect(screen.queryAllByTitle(/assumed/i)).toHaveLength(1);
  });

  it("marks nothing when the request stated everything", () => {
    render(<FrameDetail frame={frameWith({ defaultedParams: [] })} />);

    expect(screen.queryByTitle(/assumed/i)).not.toBeInTheDocument();
  });

  it("still shows the value itself", () => {
    render(<FrameDetail frame={frameWith({ defaultedParams: ["any_or_all"] })} />);

    expect(screen.getByText(/any_or_all/)).toBeInTheDocument();
  });
});
