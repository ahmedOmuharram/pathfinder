// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import {
  cleanup,
  render,
  screen,
  fireEvent,
} from "@testing-library/react";
import { FormProvider, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { TreeBoxParam } from "./TreeBoxParam";
import type { ParamSpec } from "@pathfinder/shared";
import type { VocabNode, VocabOption } from "@/lib/utils/vocab";

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

function TestForm({
  spec,
  schema,
  defaultValue,
  vocabTree = sampleTree,
  options = flatOptions,
}: {
  spec: ParamSpec;
  schema: z.ZodObject<Record<string, z.ZodTypeAny>>;
  defaultValue?: string | string[];
  vocabTree?: VocabNode[] | null;
  options?: VocabOption[];
}) {
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: { [spec.name]: defaultValue ?? [] },
    mode: "onBlur",
  });
  return (
    <FormProvider {...form}>
      <TreeBoxParam
        spec={spec}
        name={spec.name}
        options={options}
        vocabTree={vocabTree}
      />
    </FormProvider>
  );
}

const multiSchema = z.object({ test_tree: z.array(z.string()) });

function checkboxFor(label: string): HTMLInputElement {
  return screen.getByText(label).parentElement?.querySelector(
    'input[type="checkbox"]',
  ) as HTMLInputElement;
}

describe("TreeBoxParam -- multi-pick checkboxes", () => {
  it("renders checkboxes for all nodes", () => {
    render(<TestForm spec={makeSpec()} schema={multiSchema} />);
    // root + branch-a + leaf-1 + leaf-2 + branch-b + leaf-3 + leaf-4 = 7
    expect(screen.getAllByRole("checkbox").length).toBe(7);
  });

  it("checks a leaf checkbox when its value is in the form value", () => {
    render(<TestForm spec={makeSpec()} schema={multiSchema} defaultValue={["leaf-1"]} />);
    expect(checkboxFor("Leaf 1").checked).toBe(true);
  });

  it("clicking a leaf adds it to the form value", () => {
    render(<TestForm spec={makeSpec()} schema={multiSchema} defaultValue={[]} />);
    fireEvent.click(screen.getByText("Leaf 1"));
    expect(checkboxFor("Leaf 1").checked).toBe(true);
  });

  it("clicking a checked leaf removes it from the form value", () => {
    render(<TestForm spec={makeSpec()} schema={multiSchema} defaultValue={["leaf-1", "leaf-2"]} />);
    fireEvent.click(screen.getByText("Leaf 1"));
    expect(checkboxFor("Leaf 1").checked).toBe(false);
    expect(checkboxFor("Leaf 2").checked).toBe(true);
  });

  it("clicking a branch selects all its leaf descendants", () => {
    render(<TestForm spec={makeSpec()} schema={multiSchema} defaultValue={[]} />);
    fireEvent.click(screen.getByText("Branch A"));
    expect(checkboxFor("Leaf 1").checked).toBe(true);
    expect(checkboxFor("Leaf 2").checked).toBe(true);
  });

  it("clicking a fully-selected branch deselects all its leaf descendants", () => {
    render(<TestForm spec={makeSpec()} schema={multiSchema} defaultValue={["leaf-1", "leaf-2"]} />);
    fireEvent.click(screen.getByText("Branch A"));
    expect(checkboxFor("Leaf 1").checked).toBe(false);
    expect(checkboxFor("Leaf 2").checked).toBe(false);
  });

  it("branch checkbox is indeterminate when some children selected", () => {
    render(<TestForm spec={makeSpec()} schema={multiSchema} defaultValue={["leaf-1"]} />);
    const checkbox = checkboxFor("Branch A");
    expect(checkbox.indeterminate).toBe(true);
    expect(checkbox.checked).toBe(false);
  });

  it("branch checkbox is checked when all children selected", () => {
    render(<TestForm spec={makeSpec()} schema={multiSchema} defaultValue={["leaf-1", "leaf-2"]} />);
    const checkbox = checkboxFor("Branch A");
    expect(checkbox.checked).toBe(true);
    expect(checkbox.indeterminate).toBe(false);
  });
});

describe("TreeBoxParam -- search filter", () => {
  it("renders search input", () => {
    render(<TestForm spec={makeSpec()} schema={multiSchema} />);
    expect(screen.getByPlaceholderText("Search...")).toBeTruthy();
  });

  it("filters nodes by search term", () => {
    render(<TestForm spec={makeSpec()} schema={multiSchema} />);
    fireEvent.change(screen.getByPlaceholderText("Search..."), { target: { value: "Leaf 1" } });
    expect(screen.getByText("Leaf 1")).toBeTruthy();
    expect(screen.queryByText("Leaf 3")).toBeNull();
    expect(screen.queryByText("Leaf 4")).toBeNull();
  });

  it("shows ancestor branches when a descendant matches search", () => {
    render(<TestForm spec={makeSpec()} schema={multiSchema} />);
    fireEvent.change(screen.getByPlaceholderText("Search..."), { target: { value: "Leaf 3" } });
    expect(screen.getByText("Root")).toBeTruthy();
    expect(screen.getByText("Branch B")).toBeTruthy();
    expect(screen.getByText("Leaf 3")).toBeTruthy();
    expect(screen.queryByText("Branch A")).toBeNull();
    expect(screen.queryByText("Leaf 1")).toBeNull();
  });
});

describe("TreeBoxParam -- buildDefaultExpanded", () => {
  it("does not expand nodes beyond depth 2", () => {
    const deepTree: VocabNode[] = [{
      value: "d0", label: "Depth 0", children: [{
        value: "d1", label: "Depth 1", children: [{
          value: "d2", label: "Depth 2",
          children: [{ value: "d3-leaf", label: "Depth 3 Leaf" }],
        }],
      }],
    }];
    render(<TestForm spec={makeSpec()} schema={multiSchema} vocabTree={deepTree} />);
    expect(screen.getByText("Depth 0")).toBeTruthy();
    expect(screen.getByText("Depth 1")).toBeTruthy();
    expect(screen.getByText("Depth 2")).toBeTruthy();
    expect(screen.queryByText("Depth 3 Leaf")).toBeNull();
  });
});
