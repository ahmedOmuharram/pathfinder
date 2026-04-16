// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { useStore } from "@tanstack/react-form";
import type { ParamSpec } from "@pathfinder/shared";
import { buildParamSchema, buildFieldSchemaMap } from "../schema/paramSchema";
import { useParamForm, type ParamForm } from "../hooks/useParamForm";
import { SelectParam } from "../widgets/SelectParam";
import { makeSpec, molecularWeightSpecs, textSearchSpecs, organismOptions } from "./fixtures";
import { WidgetTestForm } from "../widgets/testUtils";

afterEach(cleanup);

vi.mock("@/lib/api/sites", () => ({
  refreshDependentParams: vi.fn().mockResolvedValue([]),
}));

function ParamFormWrapper({
  specs,
  onFormReady,
  children,
}: {
  specs: ParamSpec[];
  onFormReady?: (form: ParamForm) => void;
  children?: (form: ParamForm) => React.ReactNode;
}) {
  const form = useParamForm(specs);
  if (onFormReady) onFormReady(form);
  return <>{children ? children(form) : null}</>;
}

function FormVal({ form, name }: { form: ParamForm; name: string }) {
  const value = useStore(form.store, (s) => s.values[name]);
  const display = Array.isArray(value) ? JSON.stringify(value) : String(value ?? "");
  return <output data-testid={`fv-${name}`}>{display}</output>;
}

describe("TF: empty param specs", () => {
  it("buildParamSchema([]) produces valid empty schema", () => {
    const schema = buildParamSchema([]);
    expect(schema.safeParse({}).success).toBe(true);
    expect(schema.safeParse({}).data).toEqual({});
  });

  it("buildFieldSchemaMap([]) produces empty map", () => {
    const map = buildFieldSchemaMap([]);
    expect(map.size).toBe(0);
  });

  it("useParamForm with empty specs produces empty defaults", () => {
    let formRef: ParamForm | null = null;
    render(<ParamFormWrapper specs={[]} onFormReady={(f) => { formRef = f; }} />);
    expect(formRef!.state.values).toEqual({});
  });
});

describe("TF: all defaults unchanged", () => {
  it("isDirty is false when nothing is changed", () => {
    let formRef: ParamForm | null = null;
    render(<ParamFormWrapper specs={molecularWeightSpecs()} onFormReady={(f) => { formRef = f; }} />);
    expect(formRef!.state.isDirty).toBe(false);
  });
});

describe("TF: numeric validation edge cases", () => {
  it("rejects non-numeric string for numeric param", () => {
    const schema = buildParamSchema([makeSpec({ name: "w", isNumber: true, allowEmptyValue: false })]);
    expect(schema.safeParse({ w: "abc" }).success).toBe(false);
    expect(schema.safeParse({ w: "" }).success).toBe(false);
    expect(schema.safeParse({ w: "42" }).success).toBe(true);
  });

  it("accepts empty string for optional numeric param", () => {
    const schema = buildParamSchema([makeSpec({ name: "w", isNumber: true, allowEmptyValue: true })]);
    expect(schema.safeParse({ w: "" }).success).toBe(true);
  });

  it("rejects empty string for required numeric param", () => {
    const schema = buildParamSchema([makeSpec({ name: "w", isNumber: true, allowEmptyValue: false })]);
    expect(schema.safeParse({ w: "" }).success).toBe(false);
  });

  it("accepts decimal and negative numbers as strings", () => {
    const schema = buildParamSchema([makeSpec({ name: "w", isNumber: true, allowEmptyValue: false })]);
    expect(schema.safeParse({ w: "3.14" }).success).toBe(true);
    expect(schema.safeParse({ w: "-100" }).success).toBe(true);
    expect(schema.safeParse({ w: "0" }).success).toBe(true);
  });

  it("rejects mixed alpha-numeric for numeric param", () => {
    const schema = buildParamSchema([makeSpec({ name: "w", isNumber: true, allowEmptyValue: true })]);
    expect(schema.safeParse({ w: "12abc" }).success).toBe(false);
    expect(schema.safeParse({ w: "e10" }).success).toBe(false);
  });
});

describe("TF: form reset on spec change (search switch)", () => {
  function SpecSwappableForm({
    specs,
    onFormReady,
  }: {
    specs: ParamSpec[];
    onFormReady?: (form: ParamForm) => void;
  }) {
    const form = useParamForm(specs);
    if (onFormReady) onFormReady(form);
    return (
      <>
        {specs.map((spec) => <FormVal key={spec.name} form={form} name={spec.name} />)}
      </>
    );
  }

  it("resets form values when specs change (simulating search switch)", () => {
    let formRef: ParamForm | null = null;
    const { rerender } = render(
      <SpecSwappableForm specs={molecularWeightSpecs()} onFormReady={(f) => { formRef = f; }} />,
    );
    expect(formRef!.state.values["organism"]).toBe("Plasmodium falciparum 3D7");

    rerender(
      <SpecSwappableForm specs={textSearchSpecs()} onFormReady={(f) => { formRef = f; }} />,
    );
    const values = formRef!.state.values;
    expect(values["text_expression"]).toBe("");
    expect(values["text_fields"]).toEqual(["Gene ID", "Product Description"]);
  });
});

describe("TF: hidden and empty-name params are excluded", () => {
  it("hidden params are not included in form defaults", () => {
    const specs = [
      makeSpec({ name: "visible_param", isVisible: true, initialDisplayValue: "hello" }),
      makeSpec({ name: "hidden_param", isVisible: false, initialDisplayValue: "secret" }),
    ];
    let formRef: ParamForm | null = null;
    render(<ParamFormWrapper specs={specs} onFormReady={(f) => { formRef = f; }} />);
    expect(formRef!.state.values["visible_param"]).toBe("hello");
    expect(formRef!.state.values["hidden_param"]).toBeUndefined();
  });

  it("empty-name params are excluded from schema", () => {
    const schema = buildParamSchema([
      makeSpec({ name: "", displayName: "NoName", initialDisplayValue: "x" }),
      makeSpec({ name: "real_param", initialDisplayValue: "y" }),
    ]);
    expect(schema.safeParse({ real_param: "y" }).success).toBe(true);
    expect(schema.shape[""]).toBeUndefined();
  });
});

describe("TF: multi-pick required rejects empty array", () => {
  it("rejects [] and accepts non-empty array", () => {
    const schema = buildParamSchema([
      makeSpec({ name: "orgs", allowMultipleValues: true, allowEmptyValue: false }),
    ]);
    expect(schema.safeParse({ orgs: [] }).success).toBe(false);
    expect(schema.safeParse({ orgs: ["P. falciparum"] }).success).toBe(true);
  });
});

describe("TF: select param with required validation", () => {
  it("renders without blank option when allowEmptyValue is false", () => {
    const specs = [makeSpec({
      name: "organism", displayName: "Organism", displayType: "select",
      allowEmptyValue: false, initialDisplayValue: "Plasmodium falciparum 3D7",
    })];
    render(
      <WidgetTestForm name="organism" defaultValue="Plasmodium falciparum 3D7">
        {(field) => <SelectParam spec={specs[0]!} name="organism" options={organismOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    expect(screen.getByRole("combobox")).toBeTruthy();
    expect(screen.queryByText("-- Select --")).toBeNull();
  });
});

describe("TF: schema for mixed param types", () => {
  it("validates string, number, and multi-pick params together", () => {
    const schema = buildParamSchema([
      makeSpec({ name: "organism", type: "string", allowEmptyValue: false }),
      makeSpec({ name: "min_weight", type: "number", isNumber: true, allowEmptyValue: true }),
      makeSpec({ name: "go_terms", allowMultipleValues: true, allowEmptyValue: false }),
    ]);
    expect(schema.safeParse({
      organism: "P. falciparum", min_weight: "50000", go_terms: ["GO:0006915"],
    }).success).toBe(true);
    expect(schema.safeParse({
      organism: "", min_weight: "50000", go_terms: ["GO:0006915"],
    }).success).toBe(false);
    expect(schema.safeParse({
      organism: "P. falciparum", min_weight: "abc", go_terms: ["GO:0006915"],
    }).success).toBe(false);
    expect(schema.safeParse({
      organism: "P. falciparum", min_weight: "", go_terms: [],
    }).success).toBe(false);
  });
});
