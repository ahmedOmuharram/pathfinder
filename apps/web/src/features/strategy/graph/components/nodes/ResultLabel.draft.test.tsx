// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Step } from "@pathfinder/shared";
import { ResultLabel } from "./ResultLabel";
import type { StepSnapshot } from "@/state/strategy/useStepSnapshot";

/**
 * An unfinished step and a step whose count has not arrived both rendered as
 * "? transcripts", so the canvas could not tell the researcher which one they
 * were looking at. The backend now derives `status` in one place; this is the
 * canvas finally saying it.
 */

function step(overrides: Partial<Step> = {}): Step {
  return {
    id: "s1",
    searchName: "GenesByTaxon",
    displayName: "Taxon",
    recordType: "transcript",
    parameters: {},
    primaryInputStepId: null,
    secondaryInputStepId: null,
    operator: null,
    isFiltered: false,
    status: "built",
    ...overrides,
  };
}

function snapshot(overrides: Partial<StepSnapshot> = {}): StepSnapshot {
  return {
    step: step(),
    lifecycleState: "idle",
    estimatedSize: null,
    validationErrors: null,
    lastError: null,
    isBusy: false,
    isInvalid: false,
    isFailed: false,
    isDraft: false,
    wdkPushError: null,
    ...overrides,
  };
}

describe("ResultLabel draft state", () => {
  it("says Draft for a step that is not finished", () => {
    render(
      <ResultLabel step={step({ status: "draft" })} snapshot={snapshot({ isDraft: true })} />,
    );

    expect(screen.getByTestId("step-draft-label").textContent).toBe("Draft");
  });

  it("does not say Draft merely because the count has not arrived", () => {
    render(<ResultLabel step={step()} snapshot={snapshot({ estimatedSize: null })} />);

    expect(screen.queryByTestId("step-draft-label")).toBeNull();
  });

  it("still shows a count once the step is built", () => {
    render(<ResultLabel step={step()} snapshot={snapshot({ estimatedSize: 412 })} />);

    expect(screen.getByText(/412/)).toBeTruthy();
  });

  it("a draft never shows a stale count", () => {
    // The count belongs to whatever the step was before it was edited back
    // into an unfinished state; showing it would assert a number for a step
    // WDK has not run.
    render(
      <ResultLabel
        step={step({ status: "draft" })}
        snapshot={snapshot({ isDraft: true, estimatedSize: 999 })}
      />,
    );

    expect(screen.queryByText(/999/)).toBeNull();
    expect(screen.getByTestId("step-draft-label")).toBeTruthy();
  });
});
