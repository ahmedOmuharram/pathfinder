// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";
import type { ParamSpec } from "@pathfinder/shared";
import { extractDefaults, useParamForm } from "./useParamForm";

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
    const values = result.current.form.state.values;
    expect(values["organism"]).toBe("P. falciparum 3D7");
    expect(values["min_weight"]).toBe("0");
  });

  it("isDirty is false on mount", () => {
    const specs = makeSpecs();
    const { result } = renderHook(() => useParamForm(specs));
    expect(result.current.form.state.isDirty).toBe(false);
  });

  it("hydrated is true on mount when specs are non-empty", () => {
    const specs = makeSpecs();
    const { result } = renderHook(() => useParamForm(specs));
    expect(result.current.hydrated).toBe(true);
  });

  it("hydrated is false on mount when specs are empty", () => {
    const { result } = renderHook(() => useParamForm([]));
    expect(result.current.hydrated).toBe(false);
  });

  it("hydrated becomes true after specs arrive", () => {
    const { result, rerender } = renderHook(
      ({ specs }: { specs: ParamSpec[] }) => useParamForm(specs),
      { initialProps: { specs: [] as ParamSpec[] } },
    );
    expect(result.current.hydrated).toBe(false);
    rerender({ specs: makeSpecs() });
    expect(result.current.hydrated).toBe(true);
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
    expect(result.current.form.state.values["go_terms"]).toEqual([
      "GO:0006915",
      "GO:0006916",
    ]);
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
    expect(result.current.form.state.values["organisms"]).toEqual(["P. falciparum"]);
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
    expect(result.current.form.state.values["organisms"]).toEqual([]);
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
    expect(result.current.form.state.values["hidden_param"]).toBeUndefined();
  });
});

describe("extractDefaults override", () => {
  it("uses override value when present (multi-pick array)", () => {
    const specs = [
      {
        name: "organism",
        type: "string",
        displayName: "Organism",
        displayType: "treeBox",
        allowEmptyValue: true,
        allowMultipleValues: true,
        isVisible: true,
        isNumber: false,
        countOnlyLeaves: false,
        initialDisplayValue: "[]",
      },
    ] as ParamSpec[];
    const result = extractDefaults(specs, { organism: ["Pf3D7"] });
    expect(result["organism"]).toEqual(["Pf3D7"]);
  });

  it("falls back to spec initialDisplayValue when override key missing", () => {
    const specs = [
      {
        name: "organism",
        type: "string",
        displayName: "Organism",
        displayType: "treeBox",
        allowEmptyValue: true,
        allowMultipleValues: true,
        isVisible: true,
        isNumber: false,
        countOnlyLeaves: false,
        initialDisplayValue: '["PvP01"]',
      },
    ] as ParamSpec[];
    const result = extractDefaults(specs, { other: "x" });
    expect(result["organism"]).toEqual(["PvP01"]);
  });

  it("uses override string for single-pick param", () => {
    const specs = [
      {
        name: "name",
        type: "string",
        displayName: "Name",
        displayType: "select",
        allowEmptyValue: true,
        isVisible: true,
        isNumber: false,
        countOnlyLeaves: false,
        initialDisplayValue: "X",
      },
    ] as ParamSpec[];
    const result = extractDefaults(specs, { name: "Y" });
    expect(result["name"]).toBe("Y");
  });

  it("wraps override string into array for multi-pick param", () => {
    const specs = [
      {
        name: "organism",
        type: "string",
        displayName: "Organism",
        displayType: "checkbox",
        allowEmptyValue: true,
        allowMultipleValues: true,
        isVisible: true,
        isNumber: false,
        countOnlyLeaves: false,
        initialDisplayValue: "[]",
      },
    ] as ParamSpec[];
    const result = extractDefaults(specs, { organism: "Pf3D7" });
    expect(result["organism"]).toEqual(["Pf3D7"]);
  });
});

describe("useParamForm — resets when override changes", () => {
  it("resets form values when override identity changes", () => {
    const specs = [
      {
        name: "organism",
        type: "string",
        displayName: "Organism",
        displayType: "select",
        allowEmptyValue: false,
        isVisible: true,
        isNumber: false,
        countOnlyLeaves: false,
        initialDisplayValue: "default",
      },
    ] as ParamSpec[];
    const overrideA = { organism: "A" };
    const overrideB = { organism: "B" };
    const { result, rerender } = renderHook(
      ({ override }: { override: Record<string, unknown> }) =>
        useParamForm(specs, override),
      { initialProps: { override: overrideA } },
    );
    expect(result.current.form.state.values["organism"]).toBe("A");
    rerender({ override: overrideB });
    expect(result.current.form.state.values["organism"]).toBe("B");
  });
});
