// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { TreeBoxParam } from "./TreeBoxParam";
import type { ParamWidgetProps } from "./types";
import type { VocabNode } from "@/lib/utils/vocab";

afterEach(cleanup);

const sampleTree: VocabNode[] = [
  {
    value: "root",
    label: "Root",
    children: [
      {
        value: "branch-a",
        label: "Branch A",
        children: [
          { value: "leaf-1", label: "Leaf 1" },
          { value: "leaf-2", label: "Leaf 2" },
        ],
      },
      {
        value: "branch-b",
        label: "Branch B",
        children: [
          { value: "leaf-3", label: "Leaf 3" },
          { value: "leaf-4", label: "Leaf 4" },
        ],
      },
    ],
  },
];

const flatOptions = [
  { label: "Leaf 1", value: "leaf-1" },
  { label: "Leaf 2", value: "leaf-2" },
  { label: "Leaf 3", value: "leaf-3" },
  { label: "Leaf 4", value: "leaf-4" },
];

function makeProps(overrides: Partial<ParamWidgetProps> = {}): ParamWidgetProps {
  return {
    spec: { name: "test-tree" },
    value: undefined,
    multi: true,
    multiValue: [],
    options: flatOptions,
    vocabTree: sampleTree,
    onChangeSingle: vi.fn(),
    onChangeMulti: vi.fn(),
    ...overrides,
  };
}

describe("TreeBoxParam — tree rendering", () => {
  it("renders the tree with root and branches visible (top 2 levels expanded by default)", () => {
    render(<TreeBoxParam {...makeProps()} />);
    expect(screen.getByText("Root")).toBeTruthy();
    expect(screen.getByText("Branch A")).toBeTruthy();
    expect(screen.getByText("Branch B")).toBeTruthy();
  });

  it("shows leaves when branches are expanded by default (depth < 2)", () => {
    render(<TreeBoxParam {...makeProps()} />);
    // Leaves should be visible since their parent branches are at depth 1 (< 2)
    expect(screen.getByText("Leaf 1")).toBeTruthy();
    expect(screen.getByText("Leaf 2")).toBeTruthy();
    expect(screen.getByText("Leaf 3")).toBeTruthy();
    expect(screen.getByText("Leaf 4")).toBeTruthy();
  });

  it("shows selection count footer", () => {
    render(<TreeBoxParam {...makeProps({ multiValue: ["leaf-1", "leaf-3"] })} />);
    expect(screen.getByText("2 of 4 selected")).toBeTruthy();
  });

  it("shows '0 of N selected' when none selected", () => {
    render(<TreeBoxParam {...makeProps({ multiValue: [] })} />);
    expect(screen.getByText("0 of 4 selected")).toBeTruthy();
  });

  it("shows 'N of N selected' when all selected", () => {
    render(
      <TreeBoxParam
        {...makeProps({
          multiValue: ["leaf-1", "leaf-2", "leaf-3", "leaf-4"],
        })}
      />,
    );
    expect(screen.getByText("4 of 4 selected")).toBeTruthy();
  });
});

describe("TreeBoxParam — expand/collapse", () => {
  it("collapses a branch when its chevron is clicked", () => {
    render(<TreeBoxParam {...makeProps()} />);
    // Leaves are visible initially
    expect(screen.getByText("Leaf 1")).toBeTruthy();

    // Find the toggle button for "Branch A"
    const branchALabel = screen.getByText("Branch A");
    const branchARow = branchALabel.closest("[data-node-row]");
    const toggleBtn = branchARow?.querySelector("button");
    expect(toggleBtn).toBeTruthy();
    fireEvent.click(toggleBtn!);

    // Leaf 1 and Leaf 2 should now be hidden
    expect(screen.queryByText("Leaf 1")).toBeNull();
    expect(screen.queryByText("Leaf 2")).toBeNull();
    // Branch B leaves should still be visible
    expect(screen.getByText("Leaf 3")).toBeTruthy();
  });

  it("re-expands a collapsed branch when chevron is clicked again", () => {
    render(<TreeBoxParam {...makeProps()} />);
    const branchALabel = screen.getByText("Branch A");
    const branchARow = branchALabel.closest("[data-node-row]");
    const toggleBtn = branchARow?.querySelector("button");

    // Collapse
    fireEvent.click(toggleBtn!);
    expect(screen.queryByText("Leaf 1")).toBeNull();

    // Re-expand
    fireEvent.click(toggleBtn!);
    expect(screen.getByText("Leaf 1")).toBeTruthy();
  });
});

describe("TreeBoxParam — multi-pick checkboxes", () => {
  it("renders checkboxes for all nodes", () => {
    render(<TreeBoxParam {...makeProps()} />);
    const checkboxes = screen.getAllByRole("checkbox");
    // root + branch-a + leaf-1 + leaf-2 + branch-b + leaf-3 + leaf-4 = 7
    expect(checkboxes.length).toBe(7);
  });

  it("checks a leaf checkbox when its value is in multiValue", () => {
    render(<TreeBoxParam {...makeProps({ multiValue: ["leaf-1"] })} />);
    const leaf1Label = screen.getByText("Leaf 1");
    const checkbox = leaf1Label.parentElement?.querySelector(
      'input[type="checkbox"]',
    ) as HTMLInputElement;
    expect(checkbox.checked).toBe(true);
  });

  it("clicking a leaf calls onChangeMulti with that leaf added", () => {
    const onChangeMulti = vi.fn();
    render(<TreeBoxParam {...makeProps({ multiValue: [], onChangeMulti })} />);
    fireEvent.click(screen.getByText("Leaf 1"));
    expect(onChangeMulti).toHaveBeenCalledWith(["leaf-1"]);
  });

  it("clicking a checked leaf removes it", () => {
    const onChangeMulti = vi.fn();
    render(
      <TreeBoxParam
        {...makeProps({ multiValue: ["leaf-1", "leaf-2"], onChangeMulti })}
      />,
    );
    fireEvent.click(screen.getByText("Leaf 1"));
    expect(onChangeMulti).toHaveBeenCalledWith(["leaf-2"]);
  });

  it("clicking a branch selects all its leaf descendants", () => {
    const onChangeMulti = vi.fn();
    render(<TreeBoxParam {...makeProps({ multiValue: [], onChangeMulti })} />);
    fireEvent.click(screen.getByText("Branch A"));
    expect(onChangeMulti).toHaveBeenCalledWith(["leaf-1", "leaf-2"]);
  });

  it("clicking a fully-selected branch deselects all its leaf descendants", () => {
    const onChangeMulti = vi.fn();
    render(
      <TreeBoxParam
        {...makeProps({
          multiValue: ["leaf-1", "leaf-2"],
          onChangeMulti,
        })}
      />,
    );
    fireEvent.click(screen.getByText("Branch A"));
    expect(onChangeMulti).toHaveBeenCalledWith([]);
  });

  it("branch checkbox is indeterminate when some children selected", () => {
    render(<TreeBoxParam {...makeProps({ multiValue: ["leaf-1"] })} />);
    const branchALabel = screen.getByText("Branch A");
    const checkbox = branchALabel.parentElement?.querySelector(
      'input[type="checkbox"]',
    ) as HTMLInputElement;
    expect(checkbox.indeterminate).toBe(true);
    expect(checkbox.checked).toBe(false);
  });

  it("branch checkbox is checked when all children selected", () => {
    render(<TreeBoxParam {...makeProps({ multiValue: ["leaf-1", "leaf-2"] })} />);
    const branchALabel = screen.getByText("Branch A");
    const checkbox = branchALabel.parentElement?.querySelector(
      'input[type="checkbox"]',
    ) as HTMLInputElement;
    expect(checkbox.checked).toBe(true);
    expect(checkbox.indeterminate).toBe(false);
  });
});

describe("TreeBoxParam — single-pick (radios)", () => {
  it("renders radio buttons when multi is false", () => {
    render(<TreeBoxParam {...makeProps({ multi: false, value: "leaf-2" })} />);
    const radios = screen.getAllByRole("radio");
    // Only leaves get radios: leaf-1, leaf-2, leaf-3, leaf-4
    expect(radios.length).toBe(4);
  });

  it("selects the radio matching value", () => {
    render(<TreeBoxParam {...makeProps({ multi: false, value: "leaf-2" })} />);
    const leaf2Label = screen.getByText("Leaf 2");
    const radio = leaf2Label.parentElement?.querySelector(
      'input[type="radio"]',
    ) as HTMLInputElement;
    expect(radio.checked).toBe(true);
  });

  it("calls onChangeSingle when a radio is clicked", () => {
    const onChangeSingle = vi.fn();
    render(
      <TreeBoxParam {...makeProps({ multi: false, value: "", onChangeSingle })} />,
    );
    fireEvent.click(screen.getByText("Leaf 3"));
    expect(onChangeSingle).toHaveBeenCalledWith("leaf-3");
  });
});

describe("TreeBoxParam — search filter", () => {
  it("renders search input", () => {
    render(<TreeBoxParam {...makeProps()} />);
    const searchInput = screen.getByPlaceholderText("Search...");
    expect(searchInput).toBeTruthy();
  });

  it("filters nodes by search term", () => {
    render(<TreeBoxParam {...makeProps()} />);
    const searchInput = screen.getByPlaceholderText("Search...");
    fireEvent.change(searchInput, { target: { value: "Leaf 1" } });
    expect(screen.getByText("Leaf 1")).toBeTruthy();
    expect(screen.queryByText("Leaf 3")).toBeNull();
    expect(screen.queryByText("Leaf 4")).toBeNull();
  });

  it("shows ancestor branches when a descendant matches search", () => {
    render(<TreeBoxParam {...makeProps()} />);
    const searchInput = screen.getByPlaceholderText("Search...");
    fireEvent.change(searchInput, { target: { value: "Leaf 3" } });
    // Branch B and Root should remain visible as ancestors
    expect(screen.getByText("Root")).toBeTruthy();
    expect(screen.getByText("Branch B")).toBeTruthy();
    expect(screen.getByText("Leaf 3")).toBeTruthy();
    // Branch A and its children should be hidden
    expect(screen.queryByText("Branch A")).toBeNull();
    expect(screen.queryByText("Leaf 1")).toBeNull();
  });
});

describe("TreeBoxParam — flat vocab fallback", () => {
  it("falls back to flat checkboxes when vocabTree is null (multi)", () => {
    render(
      <TreeBoxParam
        {...makeProps({ vocabTree: null, multi: true, multiValue: ["leaf-1"] })}
      />,
    );
    // Should render flat checkbox list
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes.length).toBe(5); // 4 options + Select all
    expect(screen.getByText("Leaf 1")).toBeTruthy();
  });

  it("falls back to flat radios when vocabTree is null (single)", () => {
    render(
      <TreeBoxParam
        {...makeProps({ vocabTree: null, multi: false, value: "leaf-2" })}
      />,
    );
    const radios = screen.getAllByRole("radio");
    expect(radios.length).toBe(4);
  });
});
