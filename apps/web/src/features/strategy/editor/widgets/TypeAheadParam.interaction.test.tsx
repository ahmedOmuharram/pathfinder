// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  render,
  screen,
  fireEvent,
  act,
} from "@testing-library/react";
import { FormProvider, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { TypeAheadParam } from "./TypeAheadParam";
import type { ParamSpec } from "@pathfinder/shared";
import type { VocabOption } from "@/lib/utils/vocab";

afterEach(cleanup);

const sampleOptions: VocabOption[] = [
  { label: "Plasmodium falciparum", value: "pf" },
  { label: "Plasmodium vivax", value: "pv" },
  { label: "Plasmodium knowlesi", value: "pk" },
  { label: "Toxoplasma gondii", value: "tg" },
  { label: "Cryptosporidium parvum", value: "cp" },
];

const manyOptions: VocabOption[] = Array.from({ length: 80 }, (_, i) => ({
  label: `Option ${String(i + 1).padStart(3, "0")}`,
  value: `opt-${i + 1}`,
}));

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

function TestForm({
  spec,
  schema,
  defaultValue,
  options = sampleOptions,
}: {
  spec: ParamSpec;
  schema: z.ZodObject<Record<string, z.ZodTypeAny>>;
  defaultValue?: string | string[];
  options?: VocabOption[];
}) {
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: { [spec.name]: defaultValue ?? "" },
    mode: "onBlur",
  });
  return (
    <FormProvider {...form}>
      <TypeAheadParam
        spec={spec}
        name={spec.name}
        options={options}
        vocabTree={null}
      />
    </FormProvider>
  );
}

describe("TypeAheadParam -- multi-pick", () => {
  const multiSpec = makeSpec({ multiPick: true });

  it("selects multiple options into form array", async () => {
    vi.useFakeTimers();
    render(
      <TestForm
        spec={multiSpec}
        schema={z.object({ test_param: z.array(z.string()) })}
        defaultValue={[]}
      />,
    );
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "falciparum" } });
    act(() => {
      vi.advanceTimersByTime(250);
    });
    fireEvent.click(screen.getByText("Plasmodium falciparum"));
    expect(screen.getByText("Plasmodium falciparum")).toBeTruthy();
    fireEvent.change(input, { target: { value: "vivax" } });
    act(() => {
      vi.advanceTimersByTime(250);
    });
    fireEvent.click(screen.getByText("Plasmodium vivax"));
    expect(screen.getByText("Plasmodium falciparum")).toBeTruthy();
    expect(screen.getByText("Plasmodium vivax")).toBeTruthy();
    vi.useRealTimers();
  });

  it("renders chips for selected values from form default", () => {
    render(
      <TestForm
        spec={multiSpec}
        schema={z.object({ test_param: z.array(z.string()) })}
        defaultValue={["pf", "tg"]}
      />,
    );
    expect(screen.getByText("Plasmodium falciparum")).toBeTruthy();
    expect(screen.getByText("Toxoplasma gondii")).toBeTruthy();
  });

  it("removes chip and updates form array", () => {
    render(
      <TestForm
        spec={multiSpec}
        schema={z.object({ test_param: z.array(z.string()) })}
        defaultValue={["pf", "tg"]}
      />,
    );
    expect(screen.getByText("Plasmodium falciparum")).toBeTruthy();
    expect(screen.getByText("Toxoplasma gondii")).toBeTruthy();
    const removeButtons = screen.getAllByRole("button");
    fireEvent.click(removeButtons[0]!);
    expect(screen.queryByText("Plasmodium falciparum")).toBeNull();
    expect(screen.getByText("Toxoplasma gondii")).toBeTruthy();
  });

  it("clears search term after selecting in multi mode", async () => {
    vi.useFakeTimers();
    render(
      <TestForm
        spec={multiSpec}
        schema={z.object({ test_param: z.array(z.string()) })}
        defaultValue={[]}
      />,
    );
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "Plasmo" } });
    act(() => {
      vi.advanceTimersByTime(250);
    });
    fireEvent.click(screen.getByText("Plasmodium falciparum"));
    expect((input as HTMLInputElement).value).toBe("");
    vi.useRealTimers();
  });

  it("does not add duplicate values", async () => {
    vi.useFakeTimers();
    render(
      <TestForm
        spec={multiSpec}
        schema={z.object({ test_param: z.array(z.string()) })}
        defaultValue={["pf"]}
      />,
    );
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "falciparum" } });
    act(() => {
      vi.advanceTimersByTime(250);
    });
    fireEvent.click(screen.getByRole("option"));
    const removeButtons = screen.getAllByRole("button");
    expect(removeButtons.length).toBe(1);
    vi.useRealTimers();
  });
});

describe("TypeAheadParam -- search debounce", () => {
  it("does not show results before debounce completes", () => {
    vi.useFakeTimers();
    const spec = makeSpec();
    render(
      <TestForm spec={spec} schema={z.object({ test_param: z.string() })} />,
    );
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "Plasmo" } });
    act(() => {
      vi.advanceTimersByTime(100);
    });
    expect(screen.queryByText("Plasmodium falciparum")).toBeNull();
    act(() => {
      vi.advanceTimersByTime(150);
    });
    expect(screen.getByText("Plasmodium falciparum")).toBeTruthy();
    vi.useRealTimers();
  });
});

describe("TypeAheadParam -- outside click", () => {
  it("closes dropdown when clicking outside", async () => {
    vi.useFakeTimers();
    const spec = makeSpec();
    render(
      <div>
        <div data-testid="outside">outside</div>
        <TestForm
          spec={spec}
          schema={z.object({ test_param: z.string() })}
        />
      </div>,
    );
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "Plasmo" } });
    act(() => {
      vi.advanceTimersByTime(250);
    });
    expect(screen.getByText("Plasmodium falciparum")).toBeTruthy();
    fireEvent.mouseDown(screen.getByTestId("outside"));
    expect(screen.queryByText("Plasmodium falciparum")).toBeNull();
    vi.useRealTimers();
  });
});

describe("TypeAheadParam -- max results cap", () => {
  it("shows at most 50 matches with 'N more...' indicator", async () => {
    vi.useFakeTimers();
    const spec = makeSpec();
    render(
      <TestForm
        spec={spec}
        schema={z.object({ test_param: z.string() })}
        options={manyOptions}
      />,
    );
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "Option" } });
    act(() => {
      vi.advanceTimersByTime(250);
    });
    const items = screen.getAllByRole("option");
    expect(items.length).toBe(50);
    expect(screen.getByText("30 more...")).toBeTruthy();
    vi.useRealTimers();
  });
});

describe("TypeAheadParam -- no matches", () => {
  it("shows 'No matches' when search yields no results", async () => {
    vi.useFakeTimers();
    const spec = makeSpec();
    render(
      <TestForm spec={spec} schema={z.object({ test_param: z.string() })} />,
    );
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "zzzzzzz" } });
    act(() => {
      vi.advanceTimersByTime(250);
    });
    expect(screen.getByText("No matches")).toBeTruthy();
    vi.useRealTimers();
  });
});
