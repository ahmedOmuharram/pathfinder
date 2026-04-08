// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { FormProvider, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { SelectParam } from "./SelectParam";
import type { ParamSpec } from "@pathfinder/shared";
import type { VocabOption } from "@/lib/utils/vocab";

afterEach(cleanup);

const sampleOptions: VocabOption[] = [
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

/** Test wrapper that creates a form and renders a SelectParam inside it. */
function TestForm({
  spec,
  schema,
  defaultValue,
  options = sampleOptions,
}: {
  spec: ParamSpec;
  schema: z.ZodObject<Record<string, z.ZodType>>;
  defaultValue?: string | string[];
  options?: VocabOption[];
}) {
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: { [spec.name]: defaultValue ?? "" },
    mode: "onBlur",
  });
  return (
    <FormProvider {...form}>
      <SelectParam spec={spec} name={spec.name} options={options} vocabTree={null} />
    </FormProvider>
  );
}

describe("SelectParam — single-pick", () => {
  it("renders a native <select> element", () => {
    const spec = makeSpec();
    render(<TestForm spec={spec} schema={z.object({ test_param: z.string() })} />);
    const select = screen.getByRole("combobox");
    expect(select).toBeTruthy();
    expect(select.tagName).toBe("SELECT");
  });

  it("renders all options plus the placeholder", () => {
    const spec = makeSpec();
    render(<TestForm spec={spec} schema={z.object({ test_param: z.string() })} />);
    const options = screen.getAllByRole("option");
    // 1 placeholder + 4 options
    expect(options.length).toBe(5);
    expect(options[0]!.textContent).toBe("-- Select --");
  });

  it("omits placeholder when allowEmptyValue is false", () => {
    const spec = makeSpec({ allowEmptyValue: false });
    render(<TestForm spec={spec} schema={z.object({ test_param: z.string() })} />);
    const options = screen.getAllByRole("option");
    expect(options.length).toBe(4);
    expect(options[0]!.textContent).toBe("Alpha");
  });

  it("selects the current value from form default", () => {
    const spec = makeSpec();
    render(
      <TestForm spec={spec} schema={z.object({ test_param: z.string() })} defaultValue="b" />,
    );
    const select: HTMLSelectElement = screen.getByRole("combobox");
    expect(select.value).toBe("b");
  });

  it("updates form value when selection changes", () => {
    const spec = makeSpec();
    render(<TestForm spec={spec} schema={z.object({ test_param: z.string() })} />);
    const select: HTMLSelectElement = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: "c" } });
    expect(select.value).toBe("c");
  });

  it("shows validation error for required field on blur", async () => {
    const spec = makeSpec({ allowEmptyValue: false });
    const schema = z.object({ test_param: z.string().min(1, { message: "Required" }) });
    render(<TestForm spec={spec} schema={schema} defaultValue="" />);
    fireEvent.blur(screen.getByRole("combobox"));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeTruthy();
      expect(screen.getByRole("alert").textContent).toBe("Required");
    });
  });

  it("sets aria-invalid when field has error", async () => {
    const spec = makeSpec({ allowEmptyValue: false });
    const schema = z.object({ test_param: z.string().min(1, { message: "Required" }) });
    render(<TestForm spec={spec} schema={schema} defaultValue="" />);
    fireEvent.blur(screen.getByRole("combobox"));
    await waitFor(() => {
      expect(screen.getByRole("combobox").getAttribute("aria-invalid")).toBe("true");
    });
  });
});

describe("SelectParam — multi-pick", () => {
  const multiSpec = makeSpec({ multiPick: true });

  it("renders checkboxes instead of a select", () => {
    render(
      <TestForm
        spec={multiSpec}
        schema={z.object({ test_param: z.array(z.string()) })}
        defaultValue={[]}
      />,
    );
    expect(screen.queryByRole("combobox")).toBeNull();
    const checkboxes = screen.getAllByRole("checkbox");
    // 4 option checkboxes + 1 "Select all" (since options.length > 3)
    expect(checkboxes.length).toBe(5);
  });

  it("shows 'Select all' toggle when options > 3", () => {
    render(
      <TestForm
        spec={multiSpec}
        schema={z.object({ test_param: z.array(z.string()) })}
        defaultValue={[]}
      />,
    );
    expect(screen.getByText(/Select all/)).toBeTruthy();
  });

  it("does not show 'Select all' when options <= 3", () => {
    const fewOptions = sampleOptions.slice(0, 3);
    render(
      <TestForm
        spec={multiSpec}
        schema={z.object({ test_param: z.array(z.string()) })}
        defaultValue={[]}
        options={fewOptions}
      />,
    );
    expect(screen.queryByText(/Select all/)).toBeNull();
  });

  it("checks selected values from form default", () => {
    render(
      <TestForm
        spec={multiSpec}
        schema={z.object({ test_param: z.array(z.string()) })}
        defaultValue={["a", "c"]}
      />,
    );
    const checkboxes = screen.getAllByRole("checkbox");
    // "Select all" is first, then a, b, c, d
    const [selectAll, a, b, c, d] = checkboxes;
    expect((a as HTMLInputElement).checked).toBe(true);
    expect((b as HTMLInputElement).checked).toBe(false);
    expect((c as HTMLInputElement).checked).toBe(true);
    expect((d as HTMLInputElement).checked).toBe(false);
    expect((selectAll as HTMLInputElement).checked).toBe(false);
  });

  it("toggles individual checkbox and updates form", () => {
    render(
      <TestForm
        spec={multiSpec}
        schema={z.object({ test_param: z.array(z.string()) })}
        defaultValue={["a"]}
      />,
    );
    fireEvent.click(screen.getByText("Beta"));
    const checkboxes = screen.getAllByRole("checkbox");
    // After toggle: a and b should be checked
    const [, a, b] = checkboxes;
    expect((a as HTMLInputElement).checked).toBe(true);
    expect((b as HTMLInputElement).checked).toBe(true);
  });

  it("removes value when unchecking", () => {
    render(
      <TestForm
        spec={multiSpec}
        schema={z.object({ test_param: z.array(z.string()) })}
        defaultValue={["a", "b"]}
      />,
    );
    fireEvent.click(screen.getByText("Alpha"));
    const checkboxes = screen.getAllByRole("checkbox");
    const [, a, b] = checkboxes;
    expect((a as HTMLInputElement).checked).toBe(false);
    expect((b as HTMLInputElement).checked).toBe(true);
  });

  it("'Select all' selects all values", () => {
    render(
      <TestForm
        spec={multiSpec}
        schema={z.object({ test_param: z.array(z.string()) })}
        defaultValue={[]}
      />,
    );
    fireEvent.click(screen.getByText(/Select all/));
    const checkboxes = screen.getAllByRole("checkbox");
    for (const cb of checkboxes) {
      expect((cb as HTMLInputElement).checked).toBe(true);
    }
  });

  it("'Select all' deselects when all are already selected", () => {
    render(
      <TestForm
        spec={multiSpec}
        schema={z.object({ test_param: z.array(z.string()) })}
        defaultValue={["a", "b", "c", "d"]}
      />,
    );
    fireEvent.click(screen.getByText(/Select all/));
    const checkboxes = screen.getAllByRole("checkbox");
    for (const cb of checkboxes) {
      expect((cb as HTMLInputElement).checked).toBe(false);
    }
  });

  it("renders empty panel when no options", () => {
    render(
      <TestForm
        spec={multiSpec}
        schema={z.object({ test_param: z.array(z.string()) })}
        defaultValue={[]}
        options={[]}
      />,
    );
    expect(screen.queryByRole("checkbox")).toBeNull();
  });
});
