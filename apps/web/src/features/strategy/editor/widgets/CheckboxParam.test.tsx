// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { CheckboxParam } from "./CheckboxParam";
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
    spec: { name: "test-param" },
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

describe("CheckboxParam — single-pick (radios)", () => {
  it("renders radio buttons for each option", () => {
    render(<CheckboxParam {...makeProps()} />);
    const radios = screen.getAllByRole("radio");
    expect(radios.length).toBe(4);
  });

  it("checks the radio matching the current value", () => {
    render(<CheckboxParam {...makeProps({ value: "b" })} />);
    const radios = screen.getAllByRole("radio") as HTMLInputElement[];
    expect(radios[0].checked).toBe(false); // Alpha
    expect(radios[1].checked).toBe(true); // Beta
    expect(radios[2].checked).toBe(false); // Gamma
    expect(radios[3].checked).toBe(false); // Delta
  });

  it("calls onChangeSingle when a radio is clicked", () => {
    const onChangeSingle = vi.fn();
    render(<CheckboxParam {...makeProps({ onChangeSingle })} />);
    fireEvent.click(screen.getByText("Gamma"));
    expect(onChangeSingle).toHaveBeenCalledWith("c");
  });

  it("applies fieldBorderClass", () => {
    const { container } = render(
      <CheckboxParam {...makeProps({ fieldBorderClass: "border-red-500" })} />,
    );
    expect(container.firstElementChild?.className).toContain("border-red-500");
  });

  it("uses default border class when fieldBorderClass is not provided", () => {
    const { container } = render(<CheckboxParam {...makeProps()} />);
    expect(container.firstElementChild?.className).toContain("border-border");
  });
});

describe("CheckboxParam — multi-pick (checkboxes)", () => {
  it("renders checkboxes instead of radios", () => {
    render(<CheckboxParam {...makeProps({ multi: true, multiValue: [] })} />);
    expect(screen.queryByRole("radio")).toBeNull();
    const checkboxes = screen.getAllByRole("checkbox");
    // 4 option checkboxes + 1 "Select all" (since options.length > 3)
    expect(checkboxes.length).toBe(5);
  });

  it("shows 'Select all' toggle when options > 3", () => {
    render(<CheckboxParam {...makeProps({ multi: true, multiValue: [] })} />);
    expect(screen.getByText(/Select all/)).toBeTruthy();
  });

  it("does not show 'Select all' when options <= 3", () => {
    const fewOptions = sampleOptions.slice(0, 3);
    render(
      <CheckboxParam
        {...makeProps({ multi: true, multiValue: [], options: fewOptions })}
      />,
    );
    expect(screen.queryByText(/Select all/)).toBeNull();
  });

  it("checks selected values", () => {
    render(<CheckboxParam {...makeProps({ multi: true, multiValue: ["a", "d"] })} />);
    const checkboxes = screen.getAllByRole("checkbox") as HTMLInputElement[];
    // [selectAll, a, b, c, d]
    expect(checkboxes[1].checked).toBe(true); // Alpha
    expect(checkboxes[2].checked).toBe(false); // Beta
    expect(checkboxes[3].checked).toBe(false); // Gamma
    expect(checkboxes[4].checked).toBe(true); // Delta
  });

  it("toggles individual checkbox on", () => {
    const onChangeMulti = vi.fn();
    render(
      <CheckboxParam
        {...makeProps({ multi: true, multiValue: ["a"], onChangeMulti })}
      />,
    );
    fireEvent.click(screen.getByText("Beta"));
    expect(onChangeMulti).toHaveBeenCalledWith(["a", "b"]);
  });

  it("toggles individual checkbox off", () => {
    const onChangeMulti = vi.fn();
    render(
      <CheckboxParam
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
      <CheckboxParam {...makeProps({ multi: true, multiValue: [], onChangeMulti })} />,
    );
    fireEvent.click(screen.getByText(/Select all/));
    expect(onChangeMulti).toHaveBeenCalledWith(["a", "b", "c", "d"]);
  });

  it("'Select all' deselects all when all are selected", () => {
    const onChangeMulti = vi.fn();
    render(
      <CheckboxParam
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
});
