// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { FormProvider, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { StringParam } from "./StringParam";
import type { ParamSpec } from "@pathfinder/shared";

afterEach(cleanup);

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

/** Test wrapper that creates a form and renders a StringParam inside it. */
function TestForm({
  spec,
  schema,
  defaultValue,
}: {
  spec: ParamSpec;
  schema: z.ZodObject<Record<string, z.ZodType>>;
  defaultValue?: string;
}) {
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: { [spec.name]: defaultValue ?? "" },
    mode: "onBlur",
  });
  return (
    <FormProvider {...form}>
      <StringParam spec={spec} name={spec.name} options={[]} vocabTree={null} />
    </FormProvider>
  );
}

describe("StringParam (form-aware)", () => {
  it("renders a text input by default", () => {
    const spec = makeSpec();
    render(<TestForm spec={spec} schema={z.object({ test_param: z.string() })} />);
    expect(screen.getByRole("textbox")).toBeTruthy();
  });

  it("renders with default value from form", () => {
    const spec = makeSpec();
    render(
      <TestForm spec={spec} schema={z.object({ test_param: z.string() })} defaultValue="hello" />,
    );
    const input: HTMLInputElement = screen.getByRole("textbox");
    expect(input.value).toBe("hello");
  });

  it("renders number input for numeric params", () => {
    const spec = makeSpec({ isNumber: true });
    render(<TestForm spec={spec} schema={z.object({ test_param: z.string() })} />);
    const input = screen.getByRole("spinbutton");
    expect(input.getAttribute("type")).toBe("number");
  });

  it("updates form value on change", () => {
    const spec = makeSpec();
    render(<TestForm spec={spec} schema={z.object({ test_param: z.string() })} />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "abc" } });
    const input: HTMLInputElement = screen.getByRole("textbox");
    expect(input.value).toBe("abc");
  });

  it("shows validation error for required field on blur", async () => {
    const spec = makeSpec({ allowEmptyValue: false });
    const schema = z.object({ test_param: z.string().min(1, { message: "Required" }) });
    render(<TestForm spec={spec} schema={schema} defaultValue="" />);
    const input = screen.getByRole("textbox");
    fireEvent.blur(input);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeTruthy();
      expect(screen.getByRole("alert").textContent).toBe("Required");
    });
  });

  it("sets aria-invalid when field has error", async () => {
    const spec = makeSpec({ allowEmptyValue: false });
    const schema = z.object({ test_param: z.string().min(1, { message: "Required" }) });
    render(<TestForm spec={spec} schema={schema} defaultValue="" />);
    fireEvent.blur(screen.getByRole("textbox"));
    await waitFor(() => {
      expect(screen.getByRole("textbox").getAttribute("aria-invalid")).toBe("true");
    });
  });

  it("sets aria-required for non-empty params", () => {
    const spec = makeSpec({ allowEmptyValue: false });
    render(<TestForm spec={spec} schema={z.object({ test_param: z.string() })} />);
    expect(screen.getByRole("textbox").getAttribute("aria-required")).toBe("true");
  });

  it("does not set aria-required for optional params", () => {
    const spec = makeSpec({ allowEmptyValue: true });
    render(<TestForm spec={spec} schema={z.object({ test_param: z.string() })} />);
    expect(screen.getByRole("textbox").getAttribute("aria-required")).toBeNull();
  });

  it("renders with min/max/step for numeric params", () => {
    const spec = makeSpec({ isNumber: true, min: 0, max: 100, increment: 5 });
    render(<TestForm spec={spec} schema={z.object({ test_param: z.string() })} />);
    const input = screen.getByRole("spinbutton");
    expect(input.getAttribute("min")).toBe("0");
    expect(input.getAttribute("max")).toBe("100");
    expect(input.getAttribute("step")).toBe("5");
  });
});
