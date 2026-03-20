// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent, act } from "@testing-library/react";
import { TypeAheadParam } from "./TypeAheadParam";
import type { ParamWidgetProps } from "./types";

afterEach(cleanup);

// Generate many options for testing the max-50 cap
const manyOptions = Array.from({ length: 80 }, (_, i) => ({
  label: `Option ${String(i + 1).padStart(3, "0")}`,
  value: `opt-${i + 1}`,
}));

const sampleOptions = [
  { label: "Plasmodium falciparum", value: "pf" },
  { label: "Plasmodium vivax", value: "pv" },
  { label: "Plasmodium knowlesi", value: "pk" },
  { label: "Toxoplasma gondii", value: "tg" },
  { label: "Cryptosporidium parvum", value: "cp" },
];

function makeProps(overrides: Partial<ParamWidgetProps> = {}): ParamWidgetProps {
  return {
    spec: { name: "test-typeahead" },
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

describe("TypeAheadParam — rendering", () => {
  it("renders a text input", () => {
    render(<TypeAheadParam {...makeProps()} />);
    const input = screen.getByRole("textbox");
    expect(input).toBeTruthy();
  });

  it("shows placeholder text", () => {
    render(<TypeAheadParam {...makeProps()} />);
    const input = screen.getByPlaceholderText("Type to search...");
    expect(input).toBeTruthy();
  });
});

describe("TypeAheadParam — single-pick", () => {
  it("shows dropdown with matching options when typing", async () => {
    vi.useFakeTimers();
    render(<TypeAheadParam {...makeProps()} />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "Plasmo" } });
    act(() => {
      vi.advanceTimersByTime(250);
    });

    // Should show matching options
    expect(screen.getByText("Plasmodium falciparum")).toBeTruthy();
    expect(screen.getByText("Plasmodium vivax")).toBeTruthy();
    expect(screen.getByText("Plasmodium knowlesi")).toBeTruthy();
    // Non-matching should be absent
    expect(screen.queryByText("Toxoplasma gondii")).toBeNull();
    expect(screen.queryByText("Cryptosporidium parvum")).toBeNull();

    vi.useRealTimers();
  });

  it("selects a value when clicking an option", async () => {
    vi.useFakeTimers();
    const onChangeSingle = vi.fn();
    render(<TypeAheadParam {...makeProps({ onChangeSingle })} />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "vivax" } });
    act(() => {
      vi.advanceTimersByTime(250);
    });

    fireEvent.click(screen.getByText("Plasmodium vivax"));
    expect(onChangeSingle).toHaveBeenCalledWith("pv");

    vi.useRealTimers();
  });

  it("closes dropdown after selecting a value", async () => {
    vi.useFakeTimers();
    const onChangeSingle = vi.fn();
    render(<TypeAheadParam {...makeProps({ onChangeSingle })} />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "vivax" } });
    act(() => {
      vi.advanceTimersByTime(250);
    });

    fireEvent.click(screen.getByText("Plasmodium vivax"));

    // Dropdown should be closed — no matching items visible
    expect(screen.queryByText("Plasmodium vivax")).toBeNull();

    vi.useRealTimers();
  });

  it("displays current value label in input", () => {
    render(<TypeAheadParam {...makeProps({ value: "pf" })} />);
    const input: HTMLInputElement = screen.getByRole("textbox");
    expect(input.value).toBe("Plasmodium falciparum");
  });

  it("closes dropdown on Escape key", async () => {
    vi.useFakeTimers();
    render(<TypeAheadParam {...makeProps()} />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "Plasmo" } });
    act(() => {
      vi.advanceTimersByTime(250);
    });
    expect(screen.getByText("Plasmodium falciparum")).toBeTruthy();

    fireEvent.keyDown(input, { key: "Escape" });
    expect(screen.queryByText("Plasmodium falciparum")).toBeNull();

    vi.useRealTimers();
  });
});

describe("TypeAheadParam — multi-pick", () => {
  it("renders chips for selected values", () => {
    render(
      <TypeAheadParam {...makeProps({ multi: true, multiValue: ["pf", "tg"] })} />,
    );
    expect(screen.getByText("Plasmodium falciparum")).toBeTruthy();
    expect(screen.getByText("Toxoplasma gondii")).toBeTruthy();
  });

  it("removes a chip when the remove button is clicked", () => {
    const onChangeMulti = vi.fn();
    render(
      <TypeAheadParam
        {...makeProps({
          multi: true,
          multiValue: ["pf", "tg"],
          onChangeMulti,
        })}
      />,
    );
    // Find remove buttons (the x character)
    const removeButtons = screen.getAllByRole("button");
    // First remove button corresponds to "pf"
    fireEvent.click(removeButtons[0]!);
    expect(onChangeMulti).toHaveBeenCalledWith(["tg"]);
  });

  it("adds a value to multiValue when clicking a dropdown option", async () => {
    vi.useFakeTimers();
    const onChangeMulti = vi.fn();
    render(
      <TypeAheadParam
        {...makeProps({
          multi: true,
          multiValue: ["pf"],
          onChangeMulti,
        })}
      />,
    );
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "vivax" } });
    act(() => {
      vi.advanceTimersByTime(250);
    });

    fireEvent.click(screen.getByText("Plasmodium vivax"));
    expect(onChangeMulti).toHaveBeenCalledWith(["pf", "pv"]);

    vi.useRealTimers();
  });

  it("keeps input active after selecting in multi mode", async () => {
    vi.useFakeTimers();
    const onChangeMulti = vi.fn();
    render(
      <TypeAheadParam
        {...makeProps({
          multi: true,
          multiValue: [],
          onChangeMulti,
        })}
      />,
    );
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "Plasmo" } });
    act(() => {
      vi.advanceTimersByTime(250);
    });
    fireEvent.click(screen.getByText("Plasmodium falciparum"));

    // Input should still be present and clear for next search
    expect(screen.getByRole("textbox")).toBeTruthy();

    vi.useRealTimers();
  });
});

describe("TypeAheadParam — max results cap", () => {
  it("shows at most 50 matches with 'N more...' indicator", async () => {
    vi.useFakeTimers();
    render(<TypeAheadParam {...makeProps({ options: manyOptions })} />);
    const input = screen.getByRole("textbox");

    // "Option" matches all 80
    fireEvent.change(input, { target: { value: "Option" } });
    act(() => {
      vi.advanceTimersByTime(250);
    });

    // Count visible option items (li elements in the dropdown)
    const items = screen.getAllByRole("option");
    expect(items.length).toBe(50);

    // Should show "30 more..." indicator
    expect(screen.getByText("30 more...")).toBeTruthy();

    vi.useRealTimers();
  });
});

describe("TypeAheadParam — no matches", () => {
  it("shows 'No matches' when search yields no results", async () => {
    vi.useFakeTimers();
    render(<TypeAheadParam {...makeProps()} />);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "zzzzzzz" } });
    act(() => {
      vi.advanceTimersByTime(250);
    });

    expect(screen.getByText("No matches")).toBeTruthy();

    vi.useRealTimers();
  });
});
