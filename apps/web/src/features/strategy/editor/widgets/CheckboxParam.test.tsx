// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CheckboxParam } from "./CheckboxParam";
import type { ParamSpec } from "@pathfinder/shared";
import { WidgetTestForm, WidgetTestFormWithValidation } from "./testUtils";

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

describe("CheckboxParam -- single-pick (radios)", () => {
  it("renders radio buttons for each option", () => {
    const spec = makeSpec();
    render(
      <WidgetTestForm name="test_param" defaultValue="">
        {(field) => <CheckboxParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    const radios = screen.getAllByRole("radio");
    expect(radios.length).toBe(4);
  });

  it("checks the radio matching the current form value", () => {
    const spec = makeSpec();
    render(
      <WidgetTestForm name="test_param" defaultValue="b">
        {(field) => <CheckboxParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
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
      <WidgetTestForm name="test_param" defaultValue="">
        {(field) => <CheckboxParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    fireEvent.click(screen.getByText("Gamma"));
    const radios = screen.getAllByRole("radio");
    expect((radios[2] as HTMLInputElement).checked).toBe(true);
  });

  it("shows error for required field on blur", async () => {
    const spec = makeSpec({ allowEmptyValue: false });
    render(
      <WidgetTestFormWithValidation
        name="test_param"
        defaultValue=""
        validator={(v) => (v === "" ? "Required" : undefined)}
      >
        {(field) => <CheckboxParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestFormWithValidation>,
    );
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
    render(
      <WidgetTestFormWithValidation
        name="test_param"
        defaultValue=""
        validator={(v) => (v === "" ? "Required" : undefined)}
      >
        {(field) => <CheckboxParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestFormWithValidation>,
    );
    const radios = screen.getAllByRole("radio");
    fireEvent.focus(radios[0]!);
    fireEvent.blur(radios[0]!);
    await waitFor(() => {
      expect(screen.getByRole("radiogroup").getAttribute("aria-invalid")).toBe("true");
    });
  });
});

describe("CheckboxParam -- multi-pick (checkboxes)", () => {
  it("renders checkboxes instead of radios", () => {
    const spec = makeSpec({ multiPick: true });
    render(
      <WidgetTestForm name="test_param" defaultValue={[]}>
        {(field) => <CheckboxParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    expect(screen.queryByRole("radio")).toBeNull();
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes.length).toBe(5);
  });

  it("shows 'Select all' toggle when options > 3", () => {
    const spec = makeSpec({ multiPick: true });
    render(
      <WidgetTestForm name="test_param" defaultValue={[]}>
        {(field) => <CheckboxParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    expect(screen.getByText(/Select all/)).toBeTruthy();
  });

  it("checks selected values from form default", () => {
    const spec = makeSpec({ multiPick: true });
    render(
      <WidgetTestForm name="test_param" defaultValue={["a", "d"]}>
        {(field) => <CheckboxParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    const checkboxes = screen.getAllByRole("checkbox");
    expect((checkboxes[1] as HTMLInputElement).checked).toBe(true);
    expect((checkboxes[2] as HTMLInputElement).checked).toBe(false);
    expect((checkboxes[3] as HTMLInputElement).checked).toBe(false);
    expect((checkboxes[4] as HTMLInputElement).checked).toBe(true);
  });

  it("toggles individual checkbox on", () => {
    const spec = makeSpec({ multiPick: true });
    render(
      <WidgetTestForm name="test_param" defaultValue={["a"]}>
        {(field) => <CheckboxParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    fireEvent.click(screen.getByText("Beta"));
    const checkboxes = screen.getAllByRole("checkbox");
    expect((checkboxes[1] as HTMLInputElement).checked).toBe(true);
    expect((checkboxes[2] as HTMLInputElement).checked).toBe(true);
  });

  it("'Select all' selects all values", () => {
    const spec = makeSpec({ multiPick: true });
    render(
      <WidgetTestForm name="test_param" defaultValue={[]}>
        {(field) => <CheckboxParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
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
      <WidgetTestForm name="test_param" defaultValue={["a", "b", "c", "d"]}>
        {(field) => <CheckboxParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
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
    render(
      <WidgetTestFormWithValidation
        name="test_param"
        defaultValue={[]}
        validator={(v) => (Array.isArray(v) && v.length === 0 ? "Select at least one" : undefined)}
      >
        {(field) => <CheckboxParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestFormWithValidation>,
    );
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
    render(
      <WidgetTestFormWithValidation
        name="test_param"
        defaultValue={[]}
        validator={(v) => (Array.isArray(v) && v.length === 0 ? "Select at least one" : undefined)}
      >
        {(field) => <CheckboxParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestFormWithValidation>,
    );
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.focus(checkboxes[1]!);
    fireEvent.blur(checkboxes[1]!);
    await waitFor(() => {
      expect(screen.getByRole("group").getAttribute("aria-invalid")).toBe("true");
    });
  });
});
