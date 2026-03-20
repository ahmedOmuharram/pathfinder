// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import type { ParamSpec } from "@pathfinder/shared";

// Mock useParamSpecs
const mockParamSpecs: ParamSpec[] = [];
let mockLoading = false;

vi.mock("@/lib/hooks/useParamSpecs", () => ({
  useParamSpecs: () => ({ paramSpecs: mockParamSpecs, isLoading: mockLoading }),
}));

import { ParamNameSelect } from "./ParamNameSelect";

afterEach(() => {
  cleanup();
  mockLoading = false;
  mockParamSpecs.length = 0;
});

describe("ParamNameSelect", () => {
  it("shows loading state while param specs load", () => {
    mockLoading = true;
    render(
      <ParamNameSelect
        siteId="PlasmoDB"
        recordType="gene"
        searchName="GenesByTaxon"
        value={null}
        onChange={() => {}}
      />,
    );
    expect(screen.getByText(/loading/i)).toBeTruthy();
  });

  it("renders param names as select options", () => {
    mockParamSpecs.push(
      {
        name: "organism",
        displayName: "Organism",
        type: "multi-pick-vocabulary",
      } as ParamSpec,
      {
        name: "min_molecular_weight",
        displayName: "Min Molecular Weight",
        type: "number",
      } as ParamSpec,
    );
    render(
      <ParamNameSelect
        siteId="PlasmoDB"
        recordType="gene"
        searchName="GenesByTaxon"
        value={null}
        onChange={() => {}}
      />,
    );
    const select = screen.getByRole("combobox");
    expect(select).toBeTruthy();
  });

  it("calls onChange when a param is selected", () => {
    mockParamSpecs.push({
      name: "organism",
      displayName: "Organism",
      type: "multi-pick-vocabulary",
    } as ParamSpec);
    const onChange = vi.fn();
    render(
      <ParamNameSelect
        siteId="PlasmoDB"
        recordType="gene"
        searchName="GenesByTaxon"
        value={null}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "organism" },
    });
    expect(onChange).toHaveBeenCalledWith("organism");
  });

  it("shows placeholder when no value selected", () => {
    mockParamSpecs.push({
      name: "organism",
      displayName: "Organism",
      type: "multi-pick-vocabulary",
    } as ParamSpec);
    render(
      <ParamNameSelect
        siteId="PlasmoDB"
        recordType="gene"
        searchName="GenesByTaxon"
        value={null}
        onChange={() => {}}
        placeholder="Choose parameter"
      />,
    );
    const select = screen.getByRole<HTMLSelectElement>("combobox");
    expect(select.value).toBe("");
  });

  it("shows empty state when no param specs available", () => {
    render(
      <ParamNameSelect
        siteId="PlasmoDB"
        recordType="gene"
        searchName="GenesByTaxon"
        value={null}
        onChange={() => {}}
      />,
    );
    expect(screen.getByText(/no parameters/i)).toBeTruthy();
  });
});
