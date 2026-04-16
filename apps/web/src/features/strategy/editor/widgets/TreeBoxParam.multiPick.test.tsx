// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { TreeBoxParam } from "./TreeBoxParam";
import type { ParamSpec } from "@pathfinder/shared";
import type { VocabNode, VocabOption } from "@/lib/utils/vocab";
import { WidgetTestForm } from "./testUtils";

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

const flatOptions: VocabOption[] = [
  { label: "Leaf 1", value: "leaf-1" },
  { label: "Leaf 2", value: "leaf-2" },
  { label: "Leaf 3", value: "leaf-3" },
  { label: "Leaf 4", value: "leaf-4" },
];

function makeSpec(overrides: Partial<ParamSpec> = {}): ParamSpec {
  return {
    name: "test_tree",
    type: "string",
    displayName: "Test Tree",
    displayType: "",
    allowEmptyValue: true,
    isVisible: true,
    isNumber: false,
    countOnlyLeaves: false,
    multiPick: true,
    ...overrides,
  } as ParamSpec;
}

function checkboxFor(label: string): HTMLInputElement {
  return screen.getByText(label).parentElement?.querySelector(
    'input[type="checkbox"]',
  ) as HTMLInputElement;
}

describe("TreeBoxParam -- multi-pick checkboxes", () => {
  it("renders checkboxes for all nodes", () => {
    render(
      <WidgetTestForm name="test_tree" defaultValue={[]}>
        {(field) => <TreeBoxParam spec={makeSpec()} name="test_tree" options={flatOptions} vocabTree={sampleTree} field={field} />}
      </WidgetTestForm>,
    );
    expect(screen.getAllByRole("checkbox").length).toBe(7);
  });

  it("checks a leaf checkbox when its value is in the form value", () => {
    render(
      <WidgetTestForm name="test_tree" defaultValue={["leaf-1"]}>
        {(field) => <TreeBoxParam spec={makeSpec()} name="test_tree" options={flatOptions} vocabTree={sampleTree} field={field} />}
      </WidgetTestForm>,
    );
    expect(checkboxFor("Leaf 1").checked).toBe(true);
  });

  it("clicking a leaf adds it to the form value", () => {
    render(
      <WidgetTestForm name="test_tree" defaultValue={[]}>
        {(field) => <TreeBoxParam spec={makeSpec()} name="test_tree" options={flatOptions} vocabTree={sampleTree} field={field} />}
      </WidgetTestForm>,
    );
    fireEvent.click(screen.getByText("Leaf 1"));
    expect(checkboxFor("Leaf 1").checked).toBe(true);
  });

  it("clicking a checked leaf removes it from the form value", () => {
    render(
      <WidgetTestForm name="test_tree" defaultValue={["leaf-1", "leaf-2"]}>
        {(field) => <TreeBoxParam spec={makeSpec()} name="test_tree" options={flatOptions} vocabTree={sampleTree} field={field} />}
      </WidgetTestForm>,
    );
    fireEvent.click(screen.getByText("Leaf 1"));
    expect(checkboxFor("Leaf 1").checked).toBe(false);
    expect(checkboxFor("Leaf 2").checked).toBe(true);
  });

  it("clicking a branch selects all its leaf descendants", () => {
    render(
      <WidgetTestForm name="test_tree" defaultValue={[]}>
        {(field) => <TreeBoxParam spec={makeSpec()} name="test_tree" options={flatOptions} vocabTree={sampleTree} field={field} />}
      </WidgetTestForm>,
    );
    fireEvent.click(screen.getByText("Branch A"));
    expect(checkboxFor("Leaf 1").checked).toBe(true);
    expect(checkboxFor("Leaf 2").checked).toBe(true);
  });

  it("clicking a fully-selected branch deselects all its leaf descendants", () => {
    render(
      <WidgetTestForm name="test_tree" defaultValue={["leaf-1", "leaf-2"]}>
        {(field) => <TreeBoxParam spec={makeSpec()} name="test_tree" options={flatOptions} vocabTree={sampleTree} field={field} />}
      </WidgetTestForm>,
    );
    fireEvent.click(screen.getByText("Branch A"));
    expect(checkboxFor("Leaf 1").checked).toBe(false);
    expect(checkboxFor("Leaf 2").checked).toBe(false);
  });

  it("branch checkbox is indeterminate when some children selected", () => {
    render(
      <WidgetTestForm name="test_tree" defaultValue={["leaf-1"]}>
        {(field) => <TreeBoxParam spec={makeSpec()} name="test_tree" options={flatOptions} vocabTree={sampleTree} field={field} />}
      </WidgetTestForm>,
    );
    const checkbox = checkboxFor("Branch A");
    expect(checkbox.indeterminate).toBe(true);
    expect(checkbox.checked).toBe(false);
  });

  it("branch checkbox is checked when all children selected", () => {
    render(
      <WidgetTestForm name="test_tree" defaultValue={["leaf-1", "leaf-2"]}>
        {(field) => <TreeBoxParam spec={makeSpec()} name="test_tree" options={flatOptions} vocabTree={sampleTree} field={field} />}
      </WidgetTestForm>,
    );
    const checkbox = checkboxFor("Branch A");
    expect(checkbox.checked).toBe(true);
    expect(checkbox.indeterminate).toBe(false);
  });
});

describe("TreeBoxParam -- search filter", () => {
  it("renders search input", () => {
    render(
      <WidgetTestForm name="test_tree" defaultValue={[]}>
        {(field) => <TreeBoxParam spec={makeSpec()} name="test_tree" options={flatOptions} vocabTree={sampleTree} field={field} />}
      </WidgetTestForm>,
    );
    expect(screen.getByPlaceholderText("Search...")).toBeTruthy();
  });

  it("filters nodes by search term", () => {
    render(
      <WidgetTestForm name="test_tree" defaultValue={[]}>
        {(field) => <TreeBoxParam spec={makeSpec()} name="test_tree" options={flatOptions} vocabTree={sampleTree} field={field} />}
      </WidgetTestForm>,
    );
    fireEvent.change(screen.getByPlaceholderText("Search..."), { target: { value: "Leaf 1" } });
    expect(screen.getByText("Leaf 1")).toBeTruthy();
    expect(screen.queryByText("Leaf 3")).toBeNull();
  });
});
