// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { SelectParam } from "./SelectParam";
import type { ParamWidgetProps } from "./types";

afterEach(cleanup);

const sampleOptions = [
  { label: "Alpha", value: "a" },
  { label: "Beta", value: "b" },
  { label: "Gamma", value: "c" },
  { label: "Delta", value: "d" },
];

function makeProps(overrides: Partial<ParamWidgetProps> = {}): ParamWidgetProps {
  return {
    spec: {},
    value: undefined,
    multi: false,
    multiValue: [],
    options: sampleOptions,
    vocabTree: null,
    onChangeSingle: vi.fn(),
    onChangeMulti: vi.fn(),
    ...overrides,
  };
}

describe("SelectParam — single-pick", () => {
  it("renders a native <select> element", () => {
    render(<SelectParam {...makeProps()} />);
    const select = screen.getByRole("combobox");
    expect(select).toBeTruthy();
    expect(select.tagName).toBe("SELECT");
  });

  it("renders all options plus the placeholder", () => {
    render(<SelectParam {...makeProps()} />);
    const options = screen.getAllByRole("option");
    // 1 placeholder + 4 options
    expect(options.length).toBe(5);
    expect(options[0].textContent).toBe("-- Select --");
  });

  it("omits placeholder when allowEmptyValue is false", () => {
    render(<SelectParam {...makeProps({ spec: { allowEmptyValue: false } })} />);
    const options = screen.getAllByRole("option");
    expect(options.length).toBe(4);
    expect(options[0].textContent).toBe("Alpha");
  });

  it("selects the current value", () => {
    render(<SelectParam {...makeProps({ value: "b" })} />);
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    expect(select.value).toBe("b");
  });

  it("calls onChangeSingle when selection changes", () => {
    const onChangeSingle = vi.fn();
    render(<SelectParam {...makeProps({ onChangeSingle })} />);
    const select = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: "c" } });
    expect(onChangeSingle).toHaveBeenCalledWith("c");
  });

  it("applies fieldBorderClass", () => {
    render(<SelectParam {...makeProps({ fieldBorderClass: "border-red-500" })} />);
    const select = screen.getByRole("combobox");
    expect(select.className).toContain("border-red-500");
  });
});

describe("SelectParam — multi-pick", () => {
  it("renders checkboxes instead of a select", () => {
    render(<SelectParam {...makeProps({ multi: true, multiValue: [] })} />);
    expect(screen.queryByRole("combobox")).toBeNull();
    const checkboxes = screen.getAllByRole("checkbox");
    // 4 option checkboxes + 1 "Select all" (since options.length > 3)
    expect(checkboxes.length).toBe(5);
  });

  it("shows 'Select all' toggle when options > 3", () => {
    render(<SelectParam {...makeProps({ multi: true, multiValue: [] })} />);
    expect(screen.getByText(/Select all/)).toBeTruthy();
  });

  it("does not show 'Select all' when options <= 3", () => {
    const fewOptions = sampleOptions.slice(0, 3);
    render(
      <SelectParam
        {...makeProps({ multi: true, multiValue: [], options: fewOptions })}
      />,
    );
    expect(screen.queryByText(/Select all/)).toBeNull();
  });

  it("checks selected values", () => {
    render(<SelectParam {...makeProps({ multi: true, multiValue: ["a", "c"] })} />);
    const checkboxes = screen.getAllByRole("checkbox");
    // "Select all" is first, then a, b, c, d
    const [selectAll, a, b, c, d] = checkboxes;
    expect((a as HTMLInputElement).checked).toBe(true);
    expect((b as HTMLInputElement).checked).toBe(false);
    expect((c as HTMLInputElement).checked).toBe(true);
    expect((d as HTMLInputElement).checked).toBe(false);
    expect((selectAll as HTMLInputElement).checked).toBe(false);
  });

  it("toggles individual checkbox", () => {
    const onChangeMulti = vi.fn();
    render(
      <SelectParam {...makeProps({ multi: true, multiValue: ["a"], onChangeMulti })} />,
    );
    // Click "Beta" checkbox
    fireEvent.click(screen.getByText("Beta"));
    expect(onChangeMulti).toHaveBeenCalledWith(["a", "b"]);
  });

  it("removes value when unchecking", () => {
    const onChangeMulti = vi.fn();
    render(
      <SelectParam
        {...makeProps({
          multi: true,
          multiValue: ["a", "b"],
          onChangeMulti,
        })}
      />,
    );
    fireEvent.click(screen.getByText("Alpha"));
    expect(onChangeMulti).toHaveBeenCalledWith(["b"]);
  });

  it("'Select all' selects all values", () => {
    const onChangeMulti = vi.fn();
    render(
      <SelectParam {...makeProps({ multi: true, multiValue: [], onChangeMulti })} />,
    );
    fireEvent.click(screen.getByText(/Select all/));
    expect(onChangeMulti).toHaveBeenCalledWith(["a", "b", "c", "d"]);
  });

  it("'Select all' deselects when all are already selected", () => {
    const onChangeMulti = vi.fn();
    render(
      <SelectParam
        {...makeProps({
          multi: true,
          multiValue: ["a", "b", "c", "d"],
          onChangeMulti,
        })}
      />,
    );
    fireEvent.click(screen.getByText(/Select all/));
    expect(onChangeMulti).toHaveBeenCalledWith([]);
  });

  it("renders empty panel when no options", () => {
    render(
      <SelectParam {...makeProps({ multi: true, multiValue: [], options: [] })} />,
    );
    expect(screen.queryByRole("checkbox")).toBeNull();
  });
});
