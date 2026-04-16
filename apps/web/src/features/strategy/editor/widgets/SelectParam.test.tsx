// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SelectParam } from "./SelectParam";
import type { ParamSpec } from "@pathfinder/shared";
import type { VocabOption } from "@/lib/utils/vocab";
import { WidgetTestForm, WidgetTestFormWithValidation } from "./testUtils";

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

describe("SelectParam -- single-pick", () => {
  it("renders a native <select> element", () => {
    const spec = makeSpec();
    render(
      <WidgetTestForm name="test_param" defaultValue="">
        {(field) => <SelectParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    const select = screen.getByRole("combobox");
    expect(select).toBeTruthy();
    expect(select.tagName).toBe("SELECT");
  });

  it("renders all options plus the placeholder", () => {
    const spec = makeSpec();
    render(
      <WidgetTestForm name="test_param" defaultValue="">
        {(field) => <SelectParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    const options = screen.getAllByRole("option");
    expect(options.length).toBe(5);
    expect(options[0]!.textContent).toBe("-- Select --");
  });

  it("omits placeholder when allowEmptyValue is false", () => {
    const spec = makeSpec({ allowEmptyValue: false });
    render(
      <WidgetTestForm name="test_param" defaultValue="">
        {(field) => <SelectParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    const options = screen.getAllByRole("option");
    expect(options.length).toBe(4);
    expect(options[0]!.textContent).toBe("Alpha");
  });

  it("selects the current value from form default", () => {
    const spec = makeSpec();
    render(
      <WidgetTestForm name="test_param" defaultValue="b">
        {(field) => <SelectParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    const select: HTMLSelectElement = screen.getByRole("combobox");
    expect(select.value).toBe("b");
  });

  it("updates form value when selection changes", () => {
    const spec = makeSpec();
    render(
      <WidgetTestForm name="test_param" defaultValue="">
        {(field) => <SelectParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    const select: HTMLSelectElement = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: "c" } });
    expect(select.value).toBe("c");
  });

  it("shows validation error for required field on blur", async () => {
    const spec = makeSpec({ allowEmptyValue: false });
    render(
      <WidgetTestFormWithValidation
        name="test_param"
        defaultValue=""
        validator={(v) => (v === "" ? "Required" : undefined)}
      >
        {(field) => <SelectParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestFormWithValidation>,
    );
    fireEvent.blur(screen.getByRole("combobox"));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeTruthy();
      expect(screen.getByRole("alert").textContent).toBe("Required");
    });
  });

  it("sets aria-invalid when field has error", async () => {
    const spec = makeSpec({ allowEmptyValue: false });
    render(
      <WidgetTestFormWithValidation
        name="test_param"
        defaultValue=""
        validator={(v) => (v === "" ? "Required" : undefined)}
      >
        {(field) => <SelectParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestFormWithValidation>,
    );
    fireEvent.blur(screen.getByRole("combobox"));
    await waitFor(() => {
      expect(screen.getByRole("combobox").getAttribute("aria-invalid")).toBe("true");
    });
  });
});

describe("SelectParam -- multi-pick", () => {
  const multiSpec = makeSpec({ multiPick: true });

  it("renders checkboxes instead of a select", () => {
    render(
      <WidgetTestForm name="test_param" defaultValue={[]}>
        {(field) => <SelectParam spec={multiSpec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    expect(screen.queryByRole("combobox")).toBeNull();
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes.length).toBe(5);
  });

  it("shows 'Select all' toggle when options > 3", () => {
    render(
      <WidgetTestForm name="test_param" defaultValue={[]}>
        {(field) => <SelectParam spec={multiSpec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    expect(screen.getByText(/Select all/)).toBeTruthy();
  });

  it("does not show 'Select all' when options <= 3", () => {
    const fewOptions = sampleOptions.slice(0, 3);
    render(
      <WidgetTestForm name="test_param" defaultValue={[]}>
        {(field) => <SelectParam spec={multiSpec} name="test_param" options={fewOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    expect(screen.queryByText(/Select all/)).toBeNull();
  });

  it("checks selected values from form default", () => {
    render(
      <WidgetTestForm name="test_param" defaultValue={["a", "c"]}>
        {(field) => <SelectParam spec={multiSpec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    const checkboxes = screen.getAllByRole("checkbox");
    const [selectAll, a, b, c, d] = checkboxes;
    expect((a as HTMLInputElement).checked).toBe(true);
    expect((b as HTMLInputElement).checked).toBe(false);
    expect((c as HTMLInputElement).checked).toBe(true);
    expect((d as HTMLInputElement).checked).toBe(false);
    expect((selectAll as HTMLInputElement).checked).toBe(false);
  });

  it("toggles individual checkbox and updates form", () => {
    render(
      <WidgetTestForm name="test_param" defaultValue={["a"]}>
        {(field) => <SelectParam spec={multiSpec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    fireEvent.click(screen.getByText("Beta"));
    const checkboxes = screen.getAllByRole("checkbox");
    const [, a, b] = checkboxes;
    expect((a as HTMLInputElement).checked).toBe(true);
    expect((b as HTMLInputElement).checked).toBe(true);
  });

  it("removes value when unchecking", () => {
    render(
      <WidgetTestForm name="test_param" defaultValue={["a", "b"]}>
        {(field) => <SelectParam spec={multiSpec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    fireEvent.click(screen.getByText("Alpha"));
    const checkboxes = screen.getAllByRole("checkbox");
    const [, a, b] = checkboxes;
    expect((a as HTMLInputElement).checked).toBe(false);
    expect((b as HTMLInputElement).checked).toBe(true);
  });

  it("'Select all' selects all values", () => {
    render(
      <WidgetTestForm name="test_param" defaultValue={[]}>
        {(field) => <SelectParam spec={multiSpec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    fireEvent.click(screen.getByText(/Select all/));
    const checkboxes = screen.getAllByRole("checkbox");
    for (const cb of checkboxes) {
      expect((cb as HTMLInputElement).checked).toBe(true);
    }
  });

  it("'Select all' deselects when all are already selected", () => {
    render(
      <WidgetTestForm name="test_param" defaultValue={["a", "b", "c", "d"]}>
        {(field) => <SelectParam spec={multiSpec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    fireEvent.click(screen.getByText(/Select all/));
    const checkboxes = screen.getAllByRole("checkbox");
    for (const cb of checkboxes) {
      expect((cb as HTMLInputElement).checked).toBe(false);
    }
  });

  it("renders empty panel when no options", () => {
    render(
      <WidgetTestForm name="test_param" defaultValue={[]}>
        {(field) => <SelectParam spec={multiSpec} name="test_param" options={[]} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    expect(screen.queryByRole("checkbox")).toBeNull();
  });
});
