// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { Strategy } from "@pathfinder/shared";

vi.mock("@/state/strategy/useStepSnapshot", () => ({
  useStepSnapshot: () => ({
    step: null,
    lifecycleState: "idle",
    estimatedSize: 42,
    validationErrors: null,
    lastError: null,
    isBusy: false,
    isInvalid: false,
    isFailed: false,
  }),
}));

import { CompactStrategyView } from "./CompactStrategyView";

const SIMPLE_STRATEGY: Strategy = {
  id: "s1",
  name: "Simple",
  siteId: "plasmodb",
  recordType: "gene",
  steps: [
    {
      id: "step_a",
      kind: "search",
      displayName: "Genes by taxon",
      searchName: "GenesByTaxon",
      recordType: "gene",
      parameters: {},
      isBuilt: true,
      isFiltered: false,
    },
  ],
  rootStepId: "step_a",
  isSaved: false,
  createdAt: "2026-01-01T00:00:00.000Z",
  updatedAt: "2026-01-01T00:00:00.000Z",
};

const COMBINE_STRATEGY: Strategy = {
  id: "s2",
  name: "Combine",
  siteId: "plasmodb",
  recordType: "gene",
  steps: [
    {
      id: "step_a",
      kind: "search",
      displayName: "Search A",
      searchName: "GenesByTaxon",
      recordType: "gene",
      parameters: {},
      isBuilt: true,
      isFiltered: false,
    },
    {
      id: "step_b",
      kind: "search",
      displayName: "Search B",
      searchName: "GenesByGoTerm",
      recordType: "gene",
      parameters: {},
      isBuilt: true,
      isFiltered: false,
    },
    {
      id: "step_c",
      kind: "combine",
      displayName: "Intersect",
      searchName: "",
      recordType: "gene",
      parameters: {},
      operator: "INTERSECT",
      primaryInputStepId: "step_a",
      secondaryInputStepId: "step_b",
      isBuilt: true,
      isFiltered: false,
    },
  ],
  rootStepId: "step_c",
  isSaved: false,
  createdAt: "2026-01-01T00:00:00.000Z",
  updatedAt: "2026-01-01T00:00:00.000Z",
};

describe("CompactStrategyView (vertical layout)", () => {
  afterEach(() => cleanup());

  it("renders nothing when strategy is null", () => {
    const { container } = render(<CompactStrategyView strategy={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders a vertical step list for a single search", () => {
    render(<CompactStrategyView strategy={SIMPLE_STRATEGY} />);
    const list = screen.getByTestId("compact-strategy-view");
    expect(list.tagName).toBe("OL");
    expect(screen.getByText("Genes by taxon")).toBeTruthy();
  });

  it("renders combine label between secondary input and result rows", () => {
    render(<CompactStrategyView strategy={COMBINE_STRATEGY} />);
    expect(screen.getByText(/Combine \(A ∩ B\)/i)).toBeTruthy();
  });

  it("clicking a row fires onStepClick with the step id", () => {
    const onClick = vi.fn();
    render(
      <CompactStrategyView strategy={SIMPLE_STRATEGY} onStepClick={onClick} />,
    );
    fireEvent.click(screen.getByTestId("compact-step-row-step_a"));
    expect(onClick).toHaveBeenCalledWith("step_a");
  });
});
