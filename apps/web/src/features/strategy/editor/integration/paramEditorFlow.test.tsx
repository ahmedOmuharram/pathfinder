// @vitest-environment jsdom
/** RHF-22: Integration tests for the strategy editor react-hook-form migration. */

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { FormProvider, useWatch, type UseFormReturn } from "react-hook-form";
import type { ParamSpec } from "@pathfinder/shared";
import { useParamForm } from "../hooks/useParamForm";
import { StringParam } from "../widgets/StringParam";
import { CheckboxParam } from "../widgets/CheckboxParam";
import { makeSpec, molecularWeightSpecs, multiPickSpecs, goOptions } from "./fixtures";

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

// -- Full form lifecycle -------------------------------------------------------

describe("RHF-22: full form lifecycle with realistic WDK specs", () => {
  it("initializes form with WDK defaults from initialDisplayValue", () => {
    render(
      <ParamFormWrapper specs={molecularWeightSpecs()}>
        {() => (
          <>
            <FormVal name="organism" />
            <FormVal name="min_molecular_weight" />
            <FormVal name="max_molecular_weight" />
          </>
        )}
      </ParamFormWrapper>,
    );
    expect(screen.getByTestId("fv-organism").textContent).toBe("Plasmodium falciparum 3D7");
    expect(screen.getByTestId("fv-min_molecular_weight").textContent).toBe("0");
    expect(screen.getByTestId("fv-max_molecular_weight").textContent).toBe("1000000");
  });

  it("editing one param marks only that field dirty", () => {
    const specs = molecularWeightSpecs();
    let formRef: UseFormReturn | null = null;
    render(
      <ParamFormWrapper specs={specs} onFormReady={(f) => { formRef = f; }}>
        {(form) => {
          void form.formState.dirtyFields;
          return (
            <>
              <StringParam spec={specs[1]!} name="min_molecular_weight" options={[]} vocabTree={null} />
              <FormVal name="min_molecular_weight" />
            </>
          );
        }}
      </ParamFormWrapper>,
    );
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "50000" } });
    expect(screen.getByTestId("fv-min_molecular_weight").textContent).toBe("50000");
    expect(formRef!.formState.dirtyFields["min_molecular_weight"]).toBe(true);
    expect(formRef!.formState.dirtyFields["organism"]).toBeUndefined();
    expect(formRef!.formState.dirtyFields["max_molecular_weight"]).toBeUndefined();
  });

  it("getValues() produces Record<string, string> matching SearchConfig.parameters", () => {
    let formRef: UseFormReturn | null = null;
    render(<ParamFormWrapper specs={molecularWeightSpecs()} onFormReady={(f) => { formRef = f; }} />);
    const values = formRef!.getValues();
    expect(typeof values["organism"]).toBe("string");
    expect(typeof values["min_molecular_weight"]).toBe("string");
    expect(typeof values["max_molecular_weight"]).toBe("string");
    expect(Object.keys(values).sort()).toEqual([
      "max_molecular_weight", "min_molecular_weight", "organism",
    ]);
  });
});

// -- Validation error flow -----------------------------------------------------

describe("RHF-22: validation error flow", () => {
  it("shows error when required field cleared, clears on valid input", async () => {
    const specs = [makeSpec({
      name: "gene_id", displayName: "Gene ID",
      allowEmptyValue: false, initialDisplayValue: "PF3D7_0100100",
    })];
    render(
      <ParamFormWrapper specs={specs}>
        {() => <StringParam spec={specs[0]!} name="gene_id" options={[]} vocabTree={null} />}
      </ParamFormWrapper>,
    );
    const input = screen.getByRole("textbox");
    expect(screen.queryByRole("alert")).toBeNull();

    fireEvent.change(input, { target: { value: "" } });
    fireEvent.blur(input);
    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain("Gene ID");
    });
    expect(input.getAttribute("aria-invalid")).toBe("true");

    fireEvent.change(input, { target: { value: "PF3D7_0100200" } });
    fireEvent.blur(input);
    await waitFor(() => { expect(screen.queryByRole("alert")).toBeNull(); });
    expect(input.getAttribute("aria-invalid")).toBeNull();
  });

  it("shows error when required numeric input is cleared", async () => {
    const specs = [makeSpec({
      name: "min_weight", displayName: "Min Weight",
      isNumber: true, allowEmptyValue: false, initialDisplayValue: "100",
    })];
    render(
      <ParamFormWrapper specs={specs}>
        {() => <StringParam spec={specs[0]!} name="min_weight" options={[]} vocabTree={null} />}
      </ParamFormWrapper>,
    );
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "" } });
    fireEvent.blur(screen.getByRole("spinbutton"));
    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain("Min Weight");
    });
  });
});

// -- Multi-pick param interaction ----------------------------------------------

describe("RHF-22: multi-pick param interaction", () => {
  it("tracks multiple selections in form value array", () => {
    const specs = multiPickSpecs();
    render(
      <ParamFormWrapper specs={specs}>
        {() => (
          <>
            <CheckboxParam spec={specs[0]!} name="go_terms" options={goOptions} vocabTree={null} />
            <FormVal name="go_terms" />
          </>
        )}
      </ParamFormWrapper>,
    );
    fireEvent.click(screen.getByText("apoptotic process"));
    fireEvent.click(screen.getByText("cell cycle"));
    const parsed: string[] = JSON.parse(screen.getByTestId("fv-go_terms").textContent);
    expect(parsed).toContain("GO:0006915");
    expect(parsed).toContain("GO:0007049");
    expect(parsed).toHaveLength(2);
  });

  it("select-all includes all options, deselecting one removes it", () => {
    const specs = multiPickSpecs();
    render(
      <ParamFormWrapper specs={specs}>
        {() => (
          <>
            <CheckboxParam spec={specs[0]!} name="go_terms" options={goOptions} vocabTree={null} />
            <FormVal name="go_terms" />
          </>
        )}
      </ParamFormWrapper>,
    );
    const selectAllCb = screen.getByText(/Select all/).parentElement?.querySelector(
      'input[type="checkbox"]',
    ) as HTMLInputElement;
    fireEvent.click(selectAllCb);
    let parsed: string[] = JSON.parse(screen.getByTestId("fv-go_terms").textContent);
    expect(parsed).toHaveLength(5);

    fireEvent.click(screen.getByText("response to stress"));
    parsed = JSON.parse(screen.getByTestId("fv-go_terms").textContent);
    expect(parsed).toHaveLength(4);
    expect(parsed).not.toContain("GO:0006950");
  });
});

// -- Accessibility verification ------------------------------------------------

describe("RHF-22: accessibility verification", () => {
  it("aria-required set only on required param inputs", () => {
    const specs = [
      makeSpec({ name: "gene_id", allowEmptyValue: false, initialDisplayValue: "PF3D7_0100100" }),
      makeSpec({ name: "description", allowEmptyValue: true, initialDisplayValue: "" }),
    ];
    render(
      <ParamFormWrapper specs={specs}>
        {() => (
          <>
            <StringParam spec={specs[0]!} name="gene_id" options={[]} vocabTree={null} />
            <StringParam spec={specs[1]!} name="description" options={[]} vocabTree={null} />
          </>
        )}
      </ParamFormWrapper>,
    );
    const required = screen.getAllByRole("textbox").filter(
      (el) => el.getAttribute("aria-required") === "true",
    );
    expect(required).toHaveLength(1);
  });

  it("aria-describedby connects input to error message", async () => {
    const specs = [makeSpec({
      name: "gene_id", displayName: "Gene ID",
      allowEmptyValue: false, initialDisplayValue: "PF3D7_0100100",
    })];
    render(
      <ParamFormWrapper specs={specs}>
        {() => <StringParam spec={specs[0]!} name="gene_id" options={[]} vocabTree={null} />}
      </ParamFormWrapper>,
    );
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "" } });
    fireEvent.blur(input);
    await waitFor(() => {
      expect(screen.getByRole("alert").id).toBe("gene_id-error");
      expect(input.getAttribute("aria-describedby")).toBe("gene_id-error");
    });
  });

  it("role=alert count matches number of validation errors", async () => {
    const specs = [
      makeSpec({ name: "field_a", displayName: "Field A", allowEmptyValue: false, initialDisplayValue: "val" }),
      makeSpec({ name: "field_b", displayName: "Field B", allowEmptyValue: false, initialDisplayValue: "val" }),
    ];
    render(
      <ParamFormWrapper specs={specs}>
        {() => (
          <>
            <StringParam spec={specs[0]!} name="field_a" options={[]} vocabTree={null} />
            <StringParam spec={specs[1]!} name="field_b" options={[]} vocabTree={null} />
          </>
        )}
      </ParamFormWrapper>,
    );
    for (const input of screen.getAllByRole("textbox")) {
      fireEvent.change(input, { target: { value: "" } });
      fireEvent.blur(input);
    }
    await waitFor(() => {
      expect(screen.getAllByRole("alert")).toHaveLength(2);
    });
  });
});
