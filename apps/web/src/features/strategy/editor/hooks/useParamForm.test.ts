// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";
import type { ParamSpec } from "@pathfinder/shared";
import { useParamForm } from "./useParamForm";

function makeSpecs(): ParamSpec[] {
  return [
    {
      name: "organism",
      type: "string",
      displayName: "Organism",
      displayType: "select",
      allowEmptyValue: false,
      isVisible: true,
      isNumber: false,
      countOnlyLeaves: false,
      initialDisplayValue: "P. falciparum 3D7",
    },
    {
      name: "min_weight",
      type: "number",
      displayName: "Min Weight",
      displayType: "",
      allowEmptyValue: true,
      isVisible: true,
      isNumber: true,
      countOnlyLeaves: false,
      initialDisplayValue: "0",
    },
  ] as ParamSpec[];
}

describe("useParamForm", () => {
  it("initializes with WDK default values", () => {
    const specs = makeSpecs();
    const { result } = renderHook(() => useParamForm(specs));
    const values = result.current.state.values;
    expect(values["organism"]).toBe("P. falciparum 3D7");
    expect(values["min_weight"]).toBe("0");
  });

  it("isDirty is false on mount", () => {
    const specs = makeSpecs();
    const { result } = renderHook(() => useParamForm(specs));
    expect(result.current.state.isDirty).toBe(false);
  });

  it("handles multi-pick defaults from JSON array string", () => {
    const specs = [
      {
        name: "go_terms",
        type: "string",
        displayName: "GO Terms",
        displayType: "checkbox",
        allowEmptyValue: true,
        allowMultipleValues: true,
        isVisible: true,
        isNumber: false,
        countOnlyLeaves: false,
        initialDisplayValue: '["GO:0006915","GO:0006916"]',
      },
    ] as ParamSpec[];
    const { result } = renderHook(() => useParamForm(specs));
    expect(result.current.state.values["go_terms"]).toEqual(["GO:0006915", "GO:0006916"]);
  });

  it("handles multi-pick defaults from plain string", () => {
    const specs = [
      {
        name: "organisms",
        type: "string",
        displayName: "Organisms",
        displayType: "checkbox",
        allowEmptyValue: true,
        allowMultipleValues: true,
        isVisible: true,
        isNumber: false,
        countOnlyLeaves: false,
        initialDisplayValue: "P. falciparum",
      },
    ] as ParamSpec[];
    const { result } = renderHook(() => useParamForm(specs));
    expect(result.current.state.values["organisms"]).toEqual(["P. falciparum"]);
  });

  it("handles empty multi-pick defaults", () => {
    const specs = [
      {
        name: "organisms",
        type: "string",
        displayName: "Organisms",
        displayType: "checkbox",
        allowEmptyValue: true,
        allowMultipleValues: true,
        isVisible: true,
        isNumber: false,
        countOnlyLeaves: false,
        initialDisplayValue: "",
      },
    ] as ParamSpec[];
    const { result } = renderHook(() => useParamForm(specs));
    expect(result.current.state.values["organisms"]).toEqual([]);
  });

  it("skips hidden params in defaults", () => {
    const specs = [
      ...makeSpecs(),
      {
        name: "hidden_param",
        type: "string",
        displayName: "Hidden",
        displayType: "",
        allowEmptyValue: true,
        isVisible: false,
        isNumber: false,
        countOnlyLeaves: false,
        initialDisplayValue: "secret",
      } as ParamSpec,
    ];
    const { result } = renderHook(() => useParamForm(specs));
    expect(result.current.state.values["hidden_param"]).toBeUndefined();
  });
});
