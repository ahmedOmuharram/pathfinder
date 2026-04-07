// @vitest-environment jsdom
/** RHF-23: Edge-case tests for the strategy editor react-hook-form migration. */

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { FormProvider, useForm, useWatch, type UseFormReturn } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { ParamSpec } from "@pathfinder/shared";
import { buildParamSchema } from "../schema/paramSchema";
import { useParamForm } from "../hooks/useParamForm";
import { SelectParam } from "../widgets/SelectParam";
import { makeSpec, molecularWeightSpecs, textSearchSpecs, organismOptions } from "./fixtures";

afterEach(cleanup);

vi.mock("@/lib/api/sites", () => ({
  refreshDependentParams: vi.fn().mockResolvedValue([]),
}));

function ParamFormWrapper({
  specs, onFormReady, children,
}: {
  specs: ParamSpec[];
  onFormReady?: (form: UseFormReturn) => void;
  children?: (form: UseFormReturn) => React.ReactNode;
}) {
  const form = useParamForm(specs);
  if (onFormReady) onFormReady(form);
  return (
    <FormProvider {...form}>{children ? children(form) : null}</FormProvider>
  );
}

function FormVal({ name }: { name: string }) {
  const value = useWatch({ name });
  const display = Array.isArray(value) ? JSON.stringify(value) : String(value ?? "");
  return <output data-testid={`fv-${name}`}>{display}</output>;
}

function WidgetTestForm({
  spec, schema, defaultValue, children,
}: {
  spec: ParamSpec;
  schema: ReturnType<typeof buildParamSchema>;
  defaultValue: string | string[];
  children?: React.ReactNode;
}) {
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: { [spec.name]: defaultValue },
    mode: "onBlur",
  });
  return <FormProvider {...form}>{children}</FormProvider>;
}

// -- Empty param specs ---------------------------------------------------------

describe("RHF-23: empty param specs", () => {
  it("buildParamSchema([]) produces valid empty schema", () => {
    const schema = buildParamSchema([]);
    expect(schema.safeParse({}).success).toBe(true);
    expect(schema.safeParse({}).data).toEqual({});
  });

  it("useParamForm with empty specs produces empty defaults", () => {
    let formRef: UseFormReturn | null = null;
    render(<ParamFormWrapper specs={[]} onFormReady={(f) => { formRef = f; }} />);
    expect(formRef!.getValues()).toEqual({});
  });
});

// -- All defaults unchanged ----------------------------------------------------

describe("RHF-23: all defaults unchanged", () => {
  it("isDirty is false and dirtyFields empty when nothing is changed", () => {
    let formRef: UseFormReturn | null = null;
    render(
      <ParamFormWrapper specs={molecularWeightSpecs()} onFormReady={(f) => { formRef = f; }}>
        {(form) => {
          void form.formState.isDirty;
          void form.formState.dirtyFields;
          return null;
        }}
      </ParamFormWrapper>,
    );
    expect(formRef!.formState.isDirty).toBe(false);
    expect(formRef!.formState.dirtyFields).toEqual({});
  });
});

// -- Numeric validation edge cases ---------------------------------------------

describe("RHF-23: numeric validation edge cases", () => {
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

// -- Form reset on spec change (search switch) ---------------------------------

describe("RHF-23: form reset on spec change (search switch)", () => {
  function SpecSwappableForm({
    specs, onFormReady,
  }: {
    specs: ParamSpec[];
    onFormReady?: (form: UseFormReturn) => void;
  }) {
    const form = useParamForm(specs);
    if (onFormReady) onFormReady(form);
    return (
      <FormProvider {...form}>
        {specs.map((spec) => <FormVal key={spec.name} name={spec.name} />)}
      </FormProvider>
    );
  }

  it("resets form values when specs change (simulating search switch)", () => {
    let formRef: UseFormReturn | null = null;
    const { rerender } = render(
      <SpecSwappableForm specs={molecularWeightSpecs()} onFormReady={(f) => { formRef = f; }} />,
    );
    expect(formRef!.getValues()["organism"]).toBe("Plasmodium falciparum 3D7");
    void formRef!.formState.isDirty;

    rerender(
      <SpecSwappableForm specs={textSearchSpecs()} onFormReady={(f) => { formRef = f; }} />,
    );
    const values = formRef!.getValues();
    expect(values["organism"]).toBeUndefined();
    expect(values["text_expression"]).toBe("");
    expect(values["text_fields"]).toEqual(["Gene ID", "Product Description"]);
    expect(formRef!.formState.isDirty).toBe(false);
  });
});

// -- Hidden and empty-name params ----------------------------------------------

describe("RHF-23: hidden and empty-name params are excluded", () => {
  it("hidden params are not included in form defaults", () => {
    const specs = [
      makeSpec({ name: "visible_param", isVisible: true, initialDisplayValue: "hello" }),
      makeSpec({ name: "hidden_param", isVisible: false, initialDisplayValue: "secret" }),
    ];
    let formRef: UseFormReturn | null = null;
    render(<ParamFormWrapper specs={specs} onFormReady={(f) => { formRef = f; }} />);
    expect(formRef!.getValues()["visible_param"]).toBe("hello");
    expect(formRef!.getValues()["hidden_param"]).toBeUndefined();
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

// -- Multi-pick required -------------------------------------------------------

describe("RHF-23: multi-pick required rejects empty array", () => {
  it("rejects [] and accepts non-empty array", () => {
    const schema = buildParamSchema([
      makeSpec({ name: "orgs", allowMultipleValues: true, allowEmptyValue: false }),
    ]);
    expect(schema.safeParse({ orgs: [] }).success).toBe(false);
    expect(schema.safeParse({ orgs: ["P. falciparum"] }).success).toBe(true);
  });
});

// -- Select param required validation ------------------------------------------

describe("RHF-23: select param with required validation", () => {
  it("renders without blank option when allowEmptyValue is false", () => {
    const specs = [makeSpec({
      name: "organism", displayName: "Organism", displayType: "select",
      allowEmptyValue: false, initialDisplayValue: "Plasmodium falciparum 3D7",
    })];
    render(
      <WidgetTestForm spec={specs[0]!} schema={buildParamSchema(specs)} defaultValue="Plasmodium falciparum 3D7">
        <SelectParam spec={specs[0]!} name="organism" options={organismOptions} vocabTree={null} />
      </WidgetTestForm>,
    );
    expect(screen.getByRole("combobox")).toBeTruthy();
    expect(screen.queryByText("-- Select --")).toBeNull();
  });
});

// -- Mixed param type schema ---------------------------------------------------

describe("RHF-23: schema for mixed param types", () => {
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
