// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Step } from "@pathfinder/shared";
import { ValidationBanner } from "./ValidationBanner";
import type { StepSnapshot } from "@/state/strategy/useStepSnapshot";

/**
 * A step WDK rejected used to abort the whole commit, so the canvas rolled
 * back its optimistic state and said "Operation failed" - while the server had
 * in fact kept the edit. Now the operation succeeds and the rejection travels
 * on the step, which only helps if the canvas actually shows it.
 *
 * The lifecycle machine never transitions for this: the push failed on the
 * server, so nothing local goes "invalid".
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

describe("ValidationBanner surfaces a WDK rejection", () => {
  it("shows the rejection even though the lifecycle is idle", () => {
    render(
      <ValidationBanner
        step={step()}
        snapshot={snapshot({ wdkPushError: "WDK rejected this step" })}
      />,
    );

    expect(screen.getByTestId("validation-message").textContent).toBe(
      "WDK rejected this step",
    );
  });

  it("prefers the WDK reason over a generic validation message", () => {
    render(
      <ValidationBanner
        step={step()}
        snapshot={snapshot({
          isInvalid: true,
          wdkPushError: "organism is not a valid value",
          validationErrors: { general: ["Validation error"], byKey: {} },
        })}
      />,
    );

    expect(screen.getByTestId("validation-message").textContent).toBe(
      "organism is not a valid value",
    );
  });

  it("stays silent for a healthy step", () => {
    render(<ValidationBanner step={step()} snapshot={snapshot()} />);

    expect(screen.queryByTestId("validation-message")).toBeNull();
  });
});
