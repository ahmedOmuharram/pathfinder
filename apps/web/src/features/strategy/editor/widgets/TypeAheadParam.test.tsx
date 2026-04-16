// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { TypeAheadParam } from "./TypeAheadParam";
import type { ParamSpec } from "@pathfinder/shared";
import type { VocabOption } from "@/lib/utils/vocab";
import { WidgetTestForm, WidgetTestFormWithValidation } from "./testUtils";

afterEach(cleanup);

const sampleOptions: VocabOption[] = [
  { label: "Plasmodium falciparum", value: "pf" },
  { label: "Plasmodium vivax", value: "pv" },
  { label: "Plasmodium knowlesi", value: "pk" },
  { label: "Toxoplasma gondii", value: "tg" },
  { label: "Cryptosporidium parvum", value: "cp" },
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

describe("TypeAheadParam -- single-pick", () => {
  it("renders a text input with placeholder", () => {
    const spec = makeSpec();
    render(
      <WidgetTestForm name="test_param" defaultValue="">
        {(field) => <TypeAheadParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    const input = screen.getByPlaceholderText("Type to search...");
    expect(input).toBeTruthy();
  });

  it("type to filter and select option updates form value", async () => {
    vi.useFakeTimers();
    const spec = makeSpec();
    render(
      <WidgetTestForm name="test_param" defaultValue="">
        {(field) => <TypeAheadParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "vivax" } });
    act(() => { vi.advanceTimersByTime(250); });
    expect(screen.getByText("Plasmodium vivax")).toBeTruthy();
    expect(screen.queryByText("Toxoplasma gondii")).toBeNull();
    fireEvent.click(screen.getByText("Plasmodium vivax"));
    expect((input as HTMLInputElement).value).toBe("Plasmodium vivax");
    vi.useRealTimers();
  });

  it("displays label for current form value", () => {
    const spec = makeSpec();
    render(
      <WidgetTestForm name="test_param" defaultValue="pf">
        {(field) => <TypeAheadParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    const input: HTMLInputElement = screen.getByRole("textbox");
    expect(input.value).toBe("Plasmodium falciparum");
  });

  it("shows filtered results matching search term", async () => {
    vi.useFakeTimers();
    const spec = makeSpec();
    render(
      <WidgetTestForm name="test_param" defaultValue="">
        {(field) => <TypeAheadParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "Plasmo" } });
    act(() => { vi.advanceTimersByTime(250); });
    expect(screen.getByText("Plasmodium falciparum")).toBeTruthy();
    expect(screen.getByText("Plasmodium vivax")).toBeTruthy();
    expect(screen.getByText("Plasmodium knowlesi")).toBeTruthy();
    expect(screen.queryByText("Toxoplasma gondii")).toBeNull();
    vi.useRealTimers();
  });

  it("closes dropdown on Escape key", async () => {
    vi.useFakeTimers();
    const spec = makeSpec();
    render(
      <WidgetTestForm name="test_param" defaultValue="">
        {(field) => <TypeAheadParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "Plasmo" } });
    act(() => { vi.advanceTimersByTime(250); });
    expect(screen.getByText("Plasmodium falciparum")).toBeTruthy();
    fireEvent.keyDown(input, { key: "Escape" });
    expect(screen.queryByText("Plasmodium falciparum")).toBeNull();
    vi.useRealTimers();
  });

  it("shows validation error for required field on blur", async () => {
    const spec = makeSpec({ allowEmptyValue: false });
    render(
      <WidgetTestFormWithValidation
        name="test_param"
        defaultValue=""
        validator={(v) => (v === "" ? "Required" : undefined)}
      >
        {(field) => <TypeAheadParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestFormWithValidation>,
    );
    fireEvent.blur(screen.getByRole("textbox"));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeTruthy();
      expect(screen.getByRole("alert").textContent).toBe("Required");
    });
  });

  it("sets aria-invalid on input when field has error", async () => {
    const spec = makeSpec({ allowEmptyValue: false });
    render(
      <WidgetTestFormWithValidation
        name="test_param"
        defaultValue=""
        validator={(v) => (v === "" ? "Required" : undefined)}
      >
        {(field) => <TypeAheadParam spec={spec} name="test_param" options={sampleOptions} vocabTree={null} field={field} />}
      </WidgetTestFormWithValidation>,
    );
    fireEvent.blur(screen.getByRole("textbox"));
    await waitFor(() => {
      expect(screen.getByRole("textbox").getAttribute("aria-invalid")).toBe("true");
    });
  });
});
