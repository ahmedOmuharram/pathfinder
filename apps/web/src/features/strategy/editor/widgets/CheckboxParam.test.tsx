// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { FormProvider, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { CheckboxParam } from "./CheckboxParam";
import type { ParamSpec } from "@pathfinder/shared";

afterEach(cleanup);

const sampleOptions = [
  { label: "Alpha", value: "a" },
  { label: "Beta", value: "b" },
  { label: "Gamma", value: "c" },
  { label: "Delta", value: "d" },
];

function makeSpec(overrides: Partial<ParamSpec> = {}): ParamSpec {
  return {
    name: "test_param",
    type: "string",
    displayName: "Test",
    displayType: "",
    allowEmptyValue: true,
    isVisible: true,
    isNumber: false,
    countOnlyLeaves: false,
    ...overrides,
  } as ParamSpec;
}

/** Test wrapper that creates a form and renders a CheckboxParam inside it. */
function TestForm({
  spec,
  schema,
  defaultValue,
}: {
  spec: ParamSpec;
  schema: z.ZodObject<Record<string, z.ZodTypeAny>>;
  defaultValue?: string | string[];
}) {
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: { [spec.name]: defaultValue ?? "" },
    mode: "onBlur",
  });
  return (
    <FormProvider {...form}>
      <CheckboxParam
        spec={spec}
        name={spec.name}
        options={sampleOptions}
        vocabTree={null}
      />
    </FormProvider>
  );
}

/** Variant that accepts custom options. */
function TestFormWithOptions({
  spec,
  schema,
  defaultValue,
  options,
}: {
  spec: ParamSpec;
  schema: z.ZodObject<Record<string, z.ZodTypeAny>>;
  defaultValue?: string | string[];
  options: { label: string; value: string }[];
}) {
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: { [spec.name]: defaultValue ?? "" },
    mode: "onBlur",
  });
  return (
    <FormProvider {...form}>
      <CheckboxParam
        spec={spec}
        name={spec.name}
        options={options}
        vocabTree={null}
      />
    </FormProvider>
  );
}

describe("CheckboxParam — single-pick (radios)", () => {
  it("renders radio buttons for each option", () => {
    const spec = makeSpec();
    render(
      <TestForm spec={spec} schema={z.object({ test_param: z.string() })} />,
    );
    const radios = screen.getAllByRole("radio");
    expect(radios.length).toBe(4);
  });

  it("checks the radio matching the current form value", () => {
    const spec = makeSpec();
    render(
      <TestForm
        spec={spec}
        schema={z.object({ test_param: z.string() })}
        defaultValue="b"
      />,
    );
    const radios = screen.getAllByRole("radio");
    expect((radios[0] as HTMLInputElement).checked).toBe(false);
    expect((radios[1] as HTMLInputElement).checked).toBe(true);
    expect((radios[2] as HTMLInputElement).checked).toBe(false);
    expect((radios[3] as HTMLInputElement).checked).toBe(false);
  });

  it("updates form value when a radio is clicked", () => {
    const spec = makeSpec();
    render(
      <TestForm spec={spec} schema={z.object({ test_param: z.string() })} />,
    );
    fireEvent.click(screen.getByText("Gamma"));
    const radios = screen.getAllByRole("radio");
    expect((radios[2] as HTMLInputElement).checked).toBe(true);
  });

  it("shows error for required field on blur", async () => {
    const spec = makeSpec({ allowEmptyValue: false });
    const schema = z.object({
      test_param: z.string().min(1, { message: "Required" }),
    });
    render(<TestForm spec={spec} schema={schema} defaultValue="" />);
    const radios = screen.getAllByRole("radio");
    fireEvent.focus(radios[0]!);
    fireEvent.blur(radios[0]!);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeTruthy();
      expect(screen.getByRole("alert").textContent).toBe("Required");
    });
  });

  it("sets aria-invalid on container when error exists", async () => {
    const spec = makeSpec({ allowEmptyValue: false });
    const schema = z.object({
      test_param: z.string().min(1, { message: "Required" }),
    });
    render(<TestForm spec={spec} schema={schema} defaultValue="" />);
    const radios = screen.getAllByRole("radio");
    fireEvent.focus(radios[0]!);
    fireEvent.blur(radios[0]!);
    await waitFor(() => {
      expect(screen.getByRole("radiogroup").getAttribute("aria-invalid")).toBe(
        "true",
      );
    });
  });
});

describe("CheckboxParam — multi-pick (checkboxes)", () => {
  it("renders checkboxes instead of radios", () => {
    const spec = makeSpec({ multiPick: true });
    render(
      <TestForm
        spec={spec}
        schema={z.object({ test_param: z.array(z.string()) })}
        defaultValue={[]}
      />,
    );
    expect(screen.queryByRole("radio")).toBeNull();
    const checkboxes = screen.getAllByRole("checkbox");
    // 4 option checkboxes + 1 "Select all" (since options.length > 3)
    expect(checkboxes.length).toBe(5);
  });

  it("shows 'Select all' toggle when options > 3", () => {
    const spec = makeSpec({ multiPick: true });
    render(
      <TestForm
        spec={spec}
        schema={z.object({ test_param: z.array(z.string()) })}
        defaultValue={[]}
      />,
    );
    expect(screen.getByText(/Select all/)).toBeTruthy();
  });

  it("does not show 'Select all' when options <= 3", () => {
    const spec = makeSpec({ multiPick: true });
    const fewOptions = sampleOptions.slice(0, 3);
    render(
      <TestFormWithOptions
        spec={spec}
        schema={z.object({ test_param: z.array(z.string()) })}
        defaultValue={[]}
        options={fewOptions}
      />,
    );
    expect(screen.queryByText(/Select all/)).toBeNull();
  });

  it("checks selected values from form default", () => {
    const spec = makeSpec({ multiPick: true });
    render(
      <TestForm
        spec={spec}
        schema={z.object({ test_param: z.array(z.string()) })}
        defaultValue={["a", "d"]}
      />,
    );
    const checkboxes = screen.getAllByRole("checkbox");
    // [selectAll, a, b, c, d]
    expect((checkboxes[1] as HTMLInputElement).checked).toBe(true);
    expect((checkboxes[2] as HTMLInputElement).checked).toBe(false);
    expect((checkboxes[3] as HTMLInputElement).checked).toBe(false);
    expect((checkboxes[4] as HTMLInputElement).checked).toBe(true);
  });

  it("toggles individual checkbox on", () => {
    const spec = makeSpec({ multiPick: true });
    render(
      <TestForm
        spec={spec}
        schema={z.object({ test_param: z.array(z.string()) })}
        defaultValue={["a"]}
      />,
    );
    fireEvent.click(screen.getByText("Beta"));
    const checkboxes = screen.getAllByRole("checkbox");
    expect((checkboxes[1] as HTMLInputElement).checked).toBe(true); // Alpha
    expect((checkboxes[2] as HTMLInputElement).checked).toBe(true); // Beta
  });

  it("toggles individual checkbox off", () => {
    const spec = makeSpec({ multiPick: true });
    render(
      <TestForm
        spec={spec}
        schema={z.object({ test_param: z.array(z.string()) })}
        defaultValue={["a", "b"]}
      />,
    );
    fireEvent.click(screen.getByText("Alpha"));
    const checkboxes = screen.getAllByRole("checkbox");
    expect((checkboxes[1] as HTMLInputElement).checked).toBe(false); // Alpha
    expect((checkboxes[2] as HTMLInputElement).checked).toBe(true); // Beta
  });

  it("'Select all' selects all values", () => {
    const spec = makeSpec({ multiPick: true });
    render(
      <TestForm
        spec={spec}
        schema={z.object({ test_param: z.array(z.string()) })}
        defaultValue={[]}
      />,
    );
    fireEvent.click(screen.getByText(/Select all/));
    const checkboxes = screen.getAllByRole("checkbox");
    expect((checkboxes[1] as HTMLInputElement).checked).toBe(true);
    expect((checkboxes[2] as HTMLInputElement).checked).toBe(true);
    expect((checkboxes[3] as HTMLInputElement).checked).toBe(true);
    expect((checkboxes[4] as HTMLInputElement).checked).toBe(true);
  });

  it("'Select all' deselects all when all are selected", () => {
    const spec = makeSpec({ multiPick: true });
    render(
      <TestForm
        spec={spec}
        schema={z.object({ test_param: z.array(z.string()) })}
        defaultValue={["a", "b", "c", "d"]}
      />,
    );
    fireEvent.click(screen.getByText(/Select all/));
    const checkboxes = screen.getAllByRole("checkbox");
    expect((checkboxes[1] as HTMLInputElement).checked).toBe(false);
    expect((checkboxes[2] as HTMLInputElement).checked).toBe(false);
    expect((checkboxes[3] as HTMLInputElement).checked).toBe(false);
    expect((checkboxes[4] as HTMLInputElement).checked).toBe(false);
  });

  it("shows error for required multi field on blur", async () => {
    const spec = makeSpec({ multiPick: true, allowEmptyValue: false });
    const schema = z.object({
      test_param: z.array(z.string()).min(1, { message: "Select at least one" }),
    });
    render(<TestForm spec={spec} schema={schema} defaultValue={[]} />);
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.focus(checkboxes[1]!);
    fireEvent.blur(checkboxes[1]!);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeTruthy();
      expect(screen.getByRole("alert").textContent).toBe("Select at least one");
    });
  });

  it("sets aria-invalid on container when error exists", async () => {
    const spec = makeSpec({ multiPick: true, allowEmptyValue: false });
    const schema = z.object({
      test_param: z.array(z.string()).min(1, { message: "Select at least one" }),
    });
    render(<TestForm spec={spec} schema={schema} defaultValue={[]} />);
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.focus(checkboxes[1]!);
    fireEvent.blur(checkboxes[1]!);
    await waitFor(() => {
      expect(screen.getByRole("group").getAttribute("aria-invalid")).toBe(
        "true",
      );
    });
  });
});
