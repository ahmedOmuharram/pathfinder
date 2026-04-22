// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
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

function stateOf(label: string): string | null {
  return screen.getByLabelText(label).getAttribute("data-state");
}

describe("TreeBoxParam — multi-pick (shadcn checkboxes)", () => {
  it("renders checkboxes for all nodes", () => {
    render(
      <WidgetTestForm name="test_tree" defaultValue={[]}>
        {(field) => <TreeBoxParam spec={makeSpec()} name="test_tree" options={flatOptions} vocabTree={sampleTree} field={field} />}
      </WidgetTestForm>,
    );
    expect(screen.getAllByRole("checkbox").length).toBe(7);
  });

  it("checks a leaf when its value is in the form value", () => {
    render(
      <WidgetTestForm name="test_tree" defaultValue={["leaf-1"]}>
        {(field) => <TreeBoxParam spec={makeSpec()} name="test_tree" options={flatOptions} vocabTree={sampleTree} field={field} />}
      </WidgetTestForm>,
    );
    expect(stateOf("Leaf 1")).toBe("checked");
  });

  it("clicking a leaf adds it to the form value", async () => {
    const user = userEvent.setup();
    render(
      <WidgetTestForm name="test_tree" defaultValue={[]}>
        {(field) => <TreeBoxParam spec={makeSpec()} name="test_tree" options={flatOptions} vocabTree={sampleTree} field={field} />}
      </WidgetTestForm>,
    );
    await user.click(screen.getByLabelText("Leaf 1"));
    expect(stateOf("Leaf 1")).toBe("checked");
  });

  it("clicking a checked leaf removes it from the form value", async () => {
    const user = userEvent.setup();
    render(
      <WidgetTestForm name="test_tree" defaultValue={["leaf-1", "leaf-2"]}>
        {(field) => <TreeBoxParam spec={makeSpec()} name="test_tree" options={flatOptions} vocabTree={sampleTree} field={field} />}
      </WidgetTestForm>,
    );
    await user.click(screen.getByLabelText("Leaf 1"));
    expect(stateOf("Leaf 1")).toBe("unchecked");
    expect(stateOf("Leaf 2")).toBe("checked");
  });

  it("clicking a branch selects all its leaf descendants", async () => {
    const user = userEvent.setup();
    render(
      <WidgetTestForm name="test_tree" defaultValue={[]}>
        {(field) => <TreeBoxParam spec={makeSpec()} name="test_tree" options={flatOptions} vocabTree={sampleTree} field={field} />}
      </WidgetTestForm>,
    );
    await user.click(screen.getByLabelText("Branch A"));
    expect(stateOf("Leaf 1")).toBe("checked");
    expect(stateOf("Leaf 2")).toBe("checked");
  });

  it("branch checkbox is indeterminate when some children selected", () => {
    render(
      <WidgetTestForm name="test_tree" defaultValue={["leaf-1"]}>
        {(field) => <TreeBoxParam spec={makeSpec()} name="test_tree" options={flatOptions} vocabTree={sampleTree} field={field} />}
      </WidgetTestForm>,
    );
    expect(stateOf("Branch A")).toBe("indeterminate");
  });

  it("branch checkbox is checked when all children selected", () => {
    render(
      <WidgetTestForm name="test_tree" defaultValue={["leaf-1", "leaf-2"]}>
        {(field) => <TreeBoxParam spec={makeSpec()} name="test_tree" options={flatOptions} vocabTree={sampleTree} field={field} />}
      </WidgetTestForm>,
    );
    expect(stateOf("Branch A")).toBe("checked");
  });
});

describe("TreeBoxParam — search filter", () => {
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
