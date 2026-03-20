// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { StringParam } from "./StringParam";
import type { ParamWidgetProps } from "./types";

afterEach(cleanup);

function makeProps(overrides: Partial<ParamWidgetProps> = {}): ParamWidgetProps {
  return {
    spec: {},
    value: undefined,
    multi: false,
    multiValue: [],
    options: [],
    vocabTree: null,
    onChangeSingle: vi.fn(),
    onChangeMulti: vi.fn(),
    ...overrides,
  };
}

describe("StringParam", () => {
  it("renders a text input by default", () => {
    render(<StringParam {...makeProps()} />);
    const input = screen.getByRole("textbox");
    expect(input).toBeTruthy();
    expect(input.getAttribute("type")).toBe("text");
  });

  it("renders with the provided value", () => {
    render(<StringParam {...makeProps({ value: "hello" })} />);
    const input: HTMLInputElement = screen.getByRole("textbox");
    expect(input.value).toBe("hello");
  });

  it("renders empty string when value is undefined", () => {
    render(<StringParam {...makeProps({ value: undefined })} />);
    const input: HTMLInputElement = screen.getByRole("textbox");
    expect(input.value).toBe("");
  });

  it("calls onChangeSingle when typing", () => {
    const onChangeSingle = vi.fn();
    render(<StringParam {...makeProps({ onChangeSingle })} />);
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "abc" } });
    expect(onChangeSingle).toHaveBeenCalledWith("abc");
  });

  it("renders a number input when spec.isNumber is true", () => {
    render(<StringParam {...makeProps({ spec: { isNumber: true } })} />);
    const input = screen.getByRole("spinbutton");
    expect(input).toBeTruthy();
    expect(input.getAttribute("type")).toBe("number");
  });

  it("renders a number input when spec.type contains 'number'", () => {
    render(<StringParam {...makeProps({ spec: { type: "number" } })} />);
    const input = screen.getByRole("spinbutton");
    expect(input.getAttribute("type")).toBe("number");
  });

  it("renders a number input when spec.type is 'integer'", () => {
    render(<StringParam {...makeProps({ spec: { type: "integer" } })} />);
    const input = screen.getByRole("spinbutton");
    expect(input.getAttribute("type")).toBe("number");
  });

  it("renders a number input when spec.type is 'float'", () => {
    render(<StringParam {...makeProps({ spec: { type: "Float" } })} />);
    const input = screen.getByRole("spinbutton");
    expect(input.getAttribute("type")).toBe("number");
  });

  it("sets min, max, step from spec for numeric inputs", () => {
    render(
      <StringParam
        {...makeProps({
          spec: { isNumber: true, min: 0, max: 100, increment: 5 },
        })}
      />,
    );
    const input = screen.getByRole("spinbutton");
    expect(input.getAttribute("min")).toBe("0");
    expect(input.getAttribute("max")).toBe("100");
    expect(input.getAttribute("step")).toBe("5");
  });

  it("does not set min/max/step when they are null", () => {
    render(
      <StringParam
        {...makeProps({
          spec: { isNumber: true, min: null, max: null, increment: null },
        })}
      />,
    );
    const input = screen.getByRole("spinbutton");
    expect(input.getAttribute("min")).toBeNull();
    expect(input.getAttribute("max")).toBeNull();
    expect(input.getAttribute("step")).toBeNull();
  });

  it("marks input as required when allowEmptyValue is false", () => {
    render(<StringParam {...makeProps({ spec: { allowEmptyValue: false } })} />);
    const input = screen.getByRole("textbox");
    expect((input as HTMLInputElement).required).toBe(true);
  });

  it("does not mark input as required when allowEmptyValue is true", () => {
    render(<StringParam {...makeProps({ spec: { allowEmptyValue: true } })} />);
    const input = screen.getByRole("textbox");
    expect((input as HTMLInputElement).required).toBe(false);
  });

  it("applies fieldBorderClass to the input", () => {
    render(<StringParam {...makeProps({ fieldBorderClass: "border-red-500" })} />);
    const input = screen.getByRole("textbox");
    expect(input.className).toContain("border-red-500");
  });

  it("uses default border class when fieldBorderClass is not provided", () => {
    render(<StringParam {...makeProps()} />);
    const input = screen.getByRole("textbox");
    expect(input.className).toContain("border-border");
  });
});
