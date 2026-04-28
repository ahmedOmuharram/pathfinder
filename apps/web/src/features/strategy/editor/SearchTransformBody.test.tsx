// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { SearchTransformBody } from "./SearchTransformBody";
import type { StepEditorState } from "./useStepEditorState";
import type { Step } from "@pathfinder/shared";

afterEach(cleanup);

const noop = (): void => {};

const STEP: Step = {
  id: "step-1",
  kind: "search",
  searchName: "GenesByTaxon",
  recordType: "transcript",
  displayName: "Genes by taxon",
  isBuilt: false,
  isFiltered: false,
};

function makeState(overrides: Partial<StepEditorState>): StepEditorState {
  const base = {
    paramSpecs: [],
    paramSpecsError: null,
    stepValidationError: null,
    selectedSearch: null,
    searchOptions: [],
    form: {
      getFieldMeta: () => undefined,
    },
  } as unknown as StepEditorState;
  return { ...base, ...overrides };
}

describe("SearchTransformBody — paramSpecsError surfacing", () => {
  it("renders the failure banner when paramSpecsError is set", () => {
    const state = makeState({
      paramSpecsError: new Error("validation failed: organism is not a leaf"),
    });

    render(
      <SearchTransformBody
        state={state}
        step={STEP}
        onSearchChange={noop}
        onFieldChanged={noop}
        onFieldBlurred={noop}
      />,
    );

    const alert = screen.getByTestId("param-specs-error");
    expect(alert).toHaveTextContent("Failed to load parameters for this search.");
    expect(alert).toHaveTextContent("validation failed: organism is not a leaf");
    expect(
      screen.queryByText("No parameter options available for this search."),
    ).toBeNull();
  });

  it("does NOT render the failure banner when paramSpecsError is null", () => {
    const state = makeState({ paramSpecsError: null });

    render(
      <SearchTransformBody
        state={state}
        step={STEP}
        onSearchChange={noop}
        onFieldChanged={noop}
        onFieldBlurred={noop}
      />,
    );

    expect(screen.queryByTestId("param-specs-error")).toBeNull();
    expect(
      screen.getByText("No parameter options available for this search."),
    ).toBeInTheDocument();
  });
});
