// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { useForm, useStore } from "@tanstack/react-form";
import {
  buildPhyleticTree,
  encodeProfilePattern,
  decodeProfilePattern,
  claimsPhyleticParams,
} from "./phyleticProfileLogic";
import { PhyleticProfileParam } from "./PhyleticProfileParam";
import type { ParamSpec } from "@/features/strategy/parameters/spec";
import type { ParamForm } from "../hooks/useParamForm";

afterEach(cleanup);

const TERM_MAP_VOCAB = [
  ["ALL", "Root", null],
  ["EUKARYA", "Eukaryota", null],
  ["pfal", "P. falciparum", null],
  ["hsap", "H. sapiens", null],
  ["BACTERIA", "Bacteria", null],
  ["ecol", "E. coli", null],
];

const INDENT_MAP_VOCAB = [
  ["ALL", 0, null],
  ["EUKARYA", 1, null],
  ["pfal", 2, null],
  ["hsap", 2, null],
  ["BACTERIA", 1, null],
  ["ecol", 2, null],
];

const PARAM_DEFAULTS = {
  allowEmptyValue: false, countOnlyLeaves: false, isNumber: false, isVisible: true,
} as const;

const PHYLETIC_DEFAULTS: Record<string, string | string[] | unknown> = {
  profile_pattern: "",
  included_species: "",
  excluded_species: "",
  phyletic_indent_map: INDENT_MAP_VOCAB,
  phyletic_term_map: TERM_MAP_VOCAB,
};

function makeAllSpecs(): ParamSpec[] {
  return [
    { ...PARAM_DEFAULTS, name: "profile_pattern", type: "string" },
    { ...PARAM_DEFAULTS, name: "included_species", type: "string" },
    { ...PARAM_DEFAULTS, name: "excluded_species", type: "string" },
    { ...PARAM_DEFAULTS, name: "phyletic_indent_map", type: "string", vocabulary: INDENT_MAP_VOCAB },
    { ...PARAM_DEFAULTS, name: "phyletic_term_map", type: "string", vocabulary: TERM_MAP_VOCAB },
  ];
}

function TestForm({
  defaultValues,
  children,
}: {
  defaultValues?: Record<string, unknown>;
  children: (form: ParamForm) => React.ReactNode;
}) {
  const form = useForm({
    defaultValues: { ...PHYLETIC_DEFAULTS, ...defaultValues } as Record<string, string | string[]>,
    onSubmit: () => {},
  });
  return <>{children(form)}</>;
}

function FormValueReader({ form, name }: { form: ParamForm; name: string }) {
  const value = useStore(form.store, (s) => s.values[name]);
  return <output data-testid={`form-${name}`}>{String(value ?? "")}</output>;
}

describe("buildPhyleticTree", () => {
  it("builds correct hierarchy from term/indent map vocabs", () => {
    const roots = buildPhyleticTree(TERM_MAP_VOCAB, INDENT_MAP_VOCAB);
    expect(roots).toHaveLength(2);
    expect(roots[0]!.code).toBe("EUKARYA");
    expect(roots[0]!.children).toHaveLength(2);
    expect(roots[0]!.children[0]!.code).toBe("pfal");
    expect(roots[1]!.code).toBe("BACTERIA");
    expect(roots[1]!.children[0]!.code).toBe("ecol");
  });

  it("returns empty array for null/undefined input", () => {
    expect(buildPhyleticTree(null, null)).toEqual([]);
    expect(buildPhyleticTree(undefined, undefined)).toEqual([]);
  });

  it("handles empty arrays", () => {
    expect(buildPhyleticTree([], [])).toEqual([]);
  });
});

describe("encodeProfilePattern", () => {
  it("encodes include/exclude and skips unconstrained", () => {
    const states = new Map([
      ["pfal", "include" as const],
      ["hsap", "exclude" as const],
      ["ecol", "unconstrained" as const],
    ]);
    const result = encodeProfilePattern(states);
    expect(result).toContain("pfal>=1T");
    expect(result).toContain("hsap=0T");
    expect(result).not.toContain("ecol");
  });

  it("returns empty string for empty map", () => {
    expect(encodeProfilePattern(new Map())).toBe("");
  });
});

describe("decodeProfilePattern", () => {
  it("decodes include and exclude patterns", () => {
    const states = decodeProfilePattern("pfal>=1T,hsap=0T");
    expect(states.get("pfal")).toBe("include");
    expect(states.get("hsap")).toBe("exclude");
  });

  it("returns empty map for empty string", () => {
    expect(decodeProfilePattern("").size).toBe(0);
  });

  it("roundtrips with encodeProfilePattern", () => {
    const original = new Map([
      ["pfal", "include" as const],
      ["hsap", "exclude" as const],
    ]);
    const decoded = decodeProfilePattern(encodeProfilePattern(original));
    expect(decoded.get("pfal")).toBe("include");
    expect(decoded.get("hsap")).toBe("exclude");
  });
});

describe("claimsPhyleticParams", () => {
  it("returns all 5 param names when all present", () => {
    expect(claimsPhyleticParams(makeAllSpecs())).toHaveLength(5);
  });

  it("returns empty array when one param is missing", () => {
    const specs = makeAllSpecs().filter((s) => s.name !== "profile_pattern");
    expect(claimsPhyleticParams(specs)).toEqual([]);
  });

  it("returns empty array for empty specs", () => {
    expect(claimsPhyleticParams([])).toEqual([]);
  });
});

describe("PhyleticProfileParam component", () => {
  const specs = makeAllSpecs();

  it("renders tree nodes from vocab data in form context", () => {
    render(
      <TestForm>
        {(form) => <PhyleticProfileParam specs={specs} allSpecs={specs} form={form} />}
      </TestForm>,
    );
    expect(screen.getByText("Eukaryota")).toBeTruthy();
    expect(screen.getByText("Bacteria")).toBeTruthy();
    expect(screen.getByText("P. falciparum")).toBeTruthy();
    expect(screen.getByText("H. sapiens")).toBeTruthy();
    expect(screen.getByText("E. coli")).toBeTruthy();
  });

  it("clicking tri-state icon cycles through states and updates form", () => {
    render(
      <TestForm>
        {(form) => (
          <>
            <PhyleticProfileParam specs={specs} allSpecs={specs} form={form} />
            <FormValueReader form={form} name="profile_pattern" />
          </>
        )}
      </TestForm>,
    );

    const pfalRow = screen.getByText("P. falciparum").closest("[data-node]");
    const toggleBtn = pfalRow!.querySelector("[data-toggle]") as HTMLElement;

    fireEvent.click(toggleBtn);
    expect(screen.getByTestId("form-profile_pattern").textContent).toContain("pfal>=1T");

    fireEvent.click(toggleBtn);
    expect(screen.getByTestId("form-profile_pattern").textContent).toContain("pfal=0T");

    fireEvent.click(toggleBtn);
    expect(screen.getByTestId("form-profile_pattern").textContent).not.toContain("pfal");
  });

  it("shows correct summary footer counts", () => {
    render(
      <TestForm defaultValues={{ profile_pattern: "pfal>=1T,hsap=0T" }}>
        {(form) => <PhyleticProfileParam specs={specs} allSpecs={specs} form={form} />}
      </TestForm>,
    );
    expect(screen.getByText(/1 included/)).toBeTruthy();
    expect(screen.getByText(/1 excluded/)).toBeTruthy();
    expect(screen.getByText(/3 unconstrained/)).toBeTruthy();
  });

  it("search filters tree nodes by label", () => {
    render(
      <TestForm>
        {(form) => <PhyleticProfileParam specs={specs} allSpecs={specs} form={form} />}
      </TestForm>,
    );
    fireEvent.change(screen.getByPlaceholderText(/search/i), {
      target: { value: "falciparum" },
    });
    expect(screen.getByText("P. falciparum")).toBeTruthy();
    expect(screen.queryByText("E. coli")).toBeNull();
  });

  it("initializes state from existing profile_pattern in form", () => {
    render(
      <TestForm defaultValues={{ profile_pattern: "pfal>=1T" }}>
        {(form) => <PhyleticProfileParam specs={specs} allSpecs={specs} form={form} />}
      </TestForm>,
    );
    const pfalRow = screen.getByText("P. falciparum").closest("[data-node]");
    const toggleBtn = pfalRow!.querySelector("[data-toggle]") as HTMLElement;
    expect(toggleBtn.textContent).toContain("\u2713");
  });

  it("renders legend showing the three states", () => {
    render(
      <TestForm>
        {(form) => <PhyleticProfileParam specs={specs} allSpecs={specs} form={form} />}
      </TestForm>,
    );
    expect(screen.getAllByText(/unconstrained/i).length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText(/include/i).length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText(/exclude/i).length).toBeGreaterThanOrEqual(2);
  });
});
