// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import {
  cleanup,
  render,
  screen,
  fireEvent,
  waitFor,
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

describe("TreeBoxParam -- flat fallback", () => {
  it("delegates to CheckboxParam when vocabTree is null (multi)", () => {
    const spec = makeSpec({ multiPick: true });
    render(
      <TestForm
        spec={spec}
        schema={z.object({ test_tree: z.array(z.string()) })}
        defaultValue={["leaf-1"]}
        vocabTree={null}
      />,
    );
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes.length).toBe(5);
    expect(screen.getByText("Leaf 1")).toBeTruthy();
  });

  it("delegates to CheckboxParam when vocabTree is null (single)", () => {
    const spec = makeSpec({ multiPick: false });
    render(
      <TestForm
        spec={spec}
        schema={z.object({ test_tree: z.string() })}
        defaultValue="leaf-2"
        vocabTree={null}
      />,
    );
    const radios = screen.getAllByRole("radio");
    expect(radios.length).toBe(4);
    expect((radios[1] as HTMLInputElement).checked).toBe(true);
  });
});

describe("TreeBoxParam -- tree rendering", () => {
  it("renders the tree with root and branches visible (top 2 levels expanded by default)", () => {
    const spec = makeSpec();
    render(
      <TestForm
        spec={spec}
        schema={z.object({ test_tree: z.array(z.string()) })}
      />,
    );
    expect(screen.getByText("Root")).toBeTruthy();
    expect(screen.getByText("Branch A")).toBeTruthy();
    expect(screen.getByText("Branch B")).toBeTruthy();
  });

  it("shows leaves when branches are expanded by default (depth < 2)", () => {
    const spec = makeSpec();
    render(
      <TestForm
        spec={spec}
        schema={z.object({ test_tree: z.array(z.string()) })}
      />,
    );
    expect(screen.getByText("Leaf 1")).toBeTruthy();
    expect(screen.getByText("Leaf 2")).toBeTruthy();
    expect(screen.getByText("Leaf 3")).toBeTruthy();
    expect(screen.getByText("Leaf 4")).toBeTruthy();
  });

  it("shows selection count footer", () => {
    const spec = makeSpec();
    render(
      <TestForm
        spec={spec}
        schema={z.object({ test_tree: z.array(z.string()) })}
        defaultValue={["leaf-1", "leaf-3"]}
      />,
    );
    expect(screen.getByText("2 of 4 selected")).toBeTruthy();
  });

  it("shows '0 of N selected' when none selected", () => {
    const spec = makeSpec();
    render(
      <TestForm
        spec={spec}
        schema={z.object({ test_tree: z.array(z.string()) })}
        defaultValue={[]}
      />,
    );
    expect(screen.getByText("0 of 4 selected")).toBeTruthy();
  });

  it("shows 'N of N selected' when all selected", () => {
    const spec = makeSpec();
    render(
      <TestForm
        spec={spec}
        schema={z.object({ test_tree: z.array(z.string()) })}
        defaultValue={["leaf-1", "leaf-2", "leaf-3", "leaf-4"]}
      />,
    );
    expect(screen.getByText("4 of 4 selected")).toBeTruthy();
  });
});

describe("TreeBoxParam -- expand/collapse", () => {
  it("collapses a branch when its chevron is clicked", () => {
    const spec = makeSpec();
    render(
      <TestForm
        spec={spec}
        schema={z.object({ test_tree: z.array(z.string()) })}
      />,
    );
    expect(screen.getByText("Leaf 1")).toBeTruthy();
    const branchALabel = screen.getByText("Branch A");
    const branchARow = branchALabel.closest("[data-node-row]");
    const toggleBtn = branchARow?.querySelector("button");
    expect(toggleBtn).toBeTruthy();
    fireEvent.click(toggleBtn!);
    expect(screen.queryByText("Leaf 1")).toBeNull();
    expect(screen.queryByText("Leaf 2")).toBeNull();
    expect(screen.getByText("Leaf 3")).toBeTruthy();
  });

  it("re-expands a collapsed branch when chevron is clicked again", () => {
    const spec = makeSpec();
    render(
      <TestForm
        spec={spec}
        schema={z.object({ test_tree: z.array(z.string()) })}
      />,
    );
    const branchALabel = screen.getByText("Branch A");
    const branchARow = branchALabel.closest("[data-node-row]");
    const toggleBtn = branchARow?.querySelector("button");
    fireEvent.click(toggleBtn!);
    expect(screen.queryByText("Leaf 1")).toBeNull();
    fireEvent.click(toggleBtn!);
    expect(screen.getByText("Leaf 1")).toBeTruthy();
  });
});

describe("TreeBoxParam -- single-pick (radios)", () => {
  it("renders radio buttons when spec is not multi", () => {
    const spec = makeSpec({ multiPick: false });
    render(
      <TestForm
        spec={spec}
        schema={z.object({ test_tree: z.string() })}
        defaultValue="leaf-2"
      />,
    );
    const radios = screen.getAllByRole("radio");
    expect(radios.length).toBe(4);
  });

  it("selects the radio matching the form value", () => {
    const spec = makeSpec({ multiPick: false });
    render(
      <TestForm
        spec={spec}
        schema={z.object({ test_tree: z.string() })}
        defaultValue="leaf-2"
      />,
    );
    const leaf2Label = screen.getByText("Leaf 2");
    const radio = leaf2Label.parentElement?.querySelector(
      'input[type="radio"]',
    ) as HTMLInputElement;
    expect(radio.checked).toBe(true);
  });

  it("updates form value when a radio is clicked", () => {
    const spec = makeSpec({ multiPick: false });
    render(
      <TestForm
        spec={spec}
        schema={z.object({ test_tree: z.string() })}
        defaultValue=""
      />,
    );
    fireEvent.click(screen.getByText("Leaf 3"));
    const leaf3Label = screen.getByText("Leaf 3");
    const radio = leaf3Label.parentElement?.querySelector(
      'input[type="radio"]',
    ) as HTMLInputElement;
    expect(radio.checked).toBe(true);
  });
});

describe("TreeBoxParam -- error display", () => {
  const requiredSpec = makeSpec({ multiPick: true, allowEmptyValue: false });
  const requiredSchema = z.object({
    test_tree: z.array(z.string()).min(1, { message: "Select at least one" }),
  });

  function renderAndBlur() {
    render(<TestForm spec={requiredSpec} schema={requiredSchema} defaultValue={[]} />);
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.focus(checkboxes[0]!);
    fireEvent.blur(checkboxes[0]!);
  }

  it("shows error for required multi-pick field on blur", async () => {
    renderAndBlur();
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeTruthy();
      expect(screen.getByRole("alert").textContent).toBe("Select at least one");
    });
  });

  it("sets aria-invalid on container when error exists", async () => {
    renderAndBlur();
    await waitFor(() => {
      const container = screen.getByRole("alert").parentElement?.querySelector("[aria-invalid]");
      expect(container).toBeTruthy();
      expect(container?.getAttribute("aria-invalid")).toBe("true");
    });
  });
});

