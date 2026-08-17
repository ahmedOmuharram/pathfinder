// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { useForm, useStore } from "@tanstack/react-form";
import {
  buildPhyleticTree,
  encodeProfilePattern,
  decodeProfilePattern,
  leafStates,
  buildSpeciesLists,
  claimsPhyleticParams,
} from "./phyleticProfileLogic";
import { PhyleticProfileParam } from "./PhyleticProfileParam";
import type { WDKVocabTerm } from "@pathfinder/shared";

import type { ParamSpec } from "@/features/strategy/parameters/spec";
import type { ParamForm } from "../hooks/useParamForm";

afterEach(cleanup);

const TERM_MAP_VOCAB: WDKVocabTerm[] = [
  ["ALL", "Root", null],
  ["EUKARYA", "Eukaryota", null],
  ["pfal", "P. falciparum", null],
  ["hsap", "H. sapiens", null],
  ["BACTERIA", "Bacteria", null],
  ["ecol", "E. coli", null],
];

const INDENT_MAP_VOCAB: WDKVocabTerm[] = [
  ["ALL", "0", null],
  ["EUKARYA", "1", null],
  ["pfal", "2", null],
  ["hsap", "2", null],
  ["BACTERIA", "1", null],
  ["ecol", "2", null],
];

const PARAM_DEFAULTS = {
  allowEmptyValue: false,
  countOnlyLeaves: false,
  isNumber: false,
  isVisible: true,
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
    {
      ...PARAM_DEFAULTS,
      name: "phyletic_indent_map",
      type: "string",
      vocabulary: INDENT_MAP_VOCAB,
    },
    {
      ...PARAM_DEFAULTS,
      name: "phyletic_term_map",
      type: "string",
      vocabulary: TERM_MAP_VOCAB,
    },
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
    defaultValues: { ...PHYLETIC_DEFAULTS, ...defaultValues } as Record<
      string,
      string | string[]
    >,
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
  // profile_pattern is a SQL LIKE pattern over a colon-joined species census.
  // The % characters are the wildcard, and the tokens between them are
  // code:Y for present and code:N for absent.
  it("wraps and separates the tokens with the LIKE wildcard", () => {
    const states = new Map([
      ["hsap", "exclude" as const],
      ["pfal", "include" as const],
    ]);

    expect(encodeProfilePattern(states)).toBe("%hsap:N%pfal:Y%");
  });

  it("leaves an unconstrained species out of the pattern", () => {
    const states = new Map([
      ["pfal", "include" as const],
      ["ecol", "unconstrained" as const],
    ]);

    expect(encodeProfilePattern(states)).toBe("%pfal:Y%");
  });

  it("sorts the tokens into ascending code order", () => {
    // The census lists codes ascending, so %B%A% describes a census that
    // cannot exist however correct each token is.
    const clicked = new Map([
      ["yepe", "include" as const],
      ["wsuc", "include" as const],
    ]);

    expect(encodeProfilePattern(clicked)).toBe("%wsuc:Y%yepe:Y%");
  });

  it("writes a bare wildcard for an empty selection", () => {
    // The empty string is the one value WDK refuses: allowEmptyValue is false.
    expect(encodeProfilePattern(new Map())).toBe("%");
  });
});

describe("decodeProfilePattern", () => {
  it("reads back the form the encoder writes", () => {
    const states = decodeProfilePattern("%hsap:N%pfal:Y%");

    expect(states.get("pfal")).toBe("include");
    expect(states.get("hsap")).toBe("exclude");
  });

  it("reads a pattern the backend built", () => {
    const states = decodeProfilePattern("%ggor:N%hsap:N%mmus:N%pfal:Y%");

    expect([...states.keys()].sort()).toEqual(["ggor", "hsap", "mmus", "pfal"]);
    expect(states.get("mmus")).toBe("exclude");
  });

  it("returns nothing for a bare wildcard", () => {
    expect(decodeProfilePattern("%").size).toBe(0);
  });

  it("returns nothing for an empty string", () => {
    expect(decodeProfilePattern("").size).toBe(0);
  });

  it("ignores a token in another site's grammar", () => {
    // hsap=1T is a valid OrthoMCL phyletic_expression, not a profile_pattern.
    expect(decodeProfilePattern("hsap=1T").size).toBe(0);
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
    expect(screen.getByTestId("form-profile_pattern").textContent).toContain(
      "%pfal:Y%",
    );

    fireEvent.click(toggleBtn);
    expect(screen.getByTestId("form-profile_pattern").textContent).toContain(
      "%pfal:N%",
    );

    fireEvent.click(toggleBtn);
    expect(screen.getByTestId("form-profile_pattern").textContent).not.toContain(
      "pfal",
    );
  });

  it("shows correct summary footer counts", () => {
    render(
      <TestForm defaultValues={{ profile_pattern: "%hsap:N%pfal:Y%" }}>
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
      <TestForm defaultValues={{ profile_pattern: "%pfal:Y%" }}>
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

describe("leafStates", () => {
  // Clade codes never appear in the census: %MAMM:Y% matches nothing while
  // %hsap:Y% matches. A clade selection has to become its leaves.
  const tree = [
    {
      code: "MAMM",
      label: "Mammals",
      depth: 1,
      children: [
        { code: "hsap", label: "H. sapiens", depth: 2, children: [] },
        { code: "mmus", label: "M. musculus", depth: 2, children: [] },
      ],
    },
    { code: "pfal", label: "P. falciparum", depth: 1, children: [] },
  ];

  it("replaces a clade with its leaves", () => {
    const expanded = leafStates(new Map([["MAMM", "exclude" as const]]), tree);

    expect([...expanded.keys()].sort()).toEqual(["hsap", "mmus"]);
  });

  it("gives every leaf the clade's state", () => {
    const expanded = leafStates(new Map([["MAMM", "exclude" as const]]), tree);

    expect(expanded.get("hsap")).toBe("exclude");
    expect(expanded.get("mmus")).toBe("exclude");
  });

  it("leaves a species alone", () => {
    const expanded = leafStates(new Map([["pfal", "include" as const]]), tree);

    expect([...expanded.entries()]).toEqual([["pfal", "include"]]);
  });

  it("lets an explicit leaf override the clade it sits in", () => {
    const expanded = leafStates(
      new Map([
        ["MAMM", "exclude" as const],
        ["hsap", "include" as const],
      ]),
      tree,
    );

    expect(expanded.get("hsap")).toBe("include");
    expect(expanded.get("mmus")).toBe("exclude");
  });

  it("produces a pattern of leaf tokens only", () => {
    const pattern = encodeProfilePattern(
      leafStates(new Map([["MAMM", "exclude" as const]]), tree),
    );

    expect(pattern).toBe("%hsap:N%mmus:N%");
  });
});

describe("buildSpeciesLists", () => {
  // The reference client reads these two back when reopening a step, and it
  // reads them as vocabulary terms rather than display labels.
  it("writes terms, not labels", () => {
    const lists = buildSpeciesLists(new Map([["pfal", "include" as const]]));

    expect(lists.included).toBe("pfal");
  });

  it("separates several terms the way the reference client does", () => {
    const lists = buildSpeciesLists(new Map([
        ["pfal", "include" as const],
        ["hsap", "include" as const],
      ]));

    expect(lists.included).toBe("pfal, hsap");
  });

  it("writes the empty set as the literal the client decodes", () => {
    const lists = buildSpeciesLists(new Map([["pfal", "include" as const]]));

    expect(lists.excluded).toBe("n/a");
  });
});

describe("an included species always reaches the matching branch", () => {
  // The query is a UNION whose first branch fires when the pattern contains no
  // `:Y`, returning the ortholog-less gene set instead of a phyletic match.
  // Every pattern carrying an inclusion must therefore carry a `:Y` token.
  it("writes a :Y token for an inclusion", () => {
    const pattern = encodeProfilePattern(new Map([["pfal", "include" as const]]));

    expect(pattern).toContain(":Y");
  });

  it("writes a :Y even when exclusions outnumber inclusions", () => {
    const pattern = encodeProfilePattern(
      new Map([
        ["hsap", "exclude" as const],
        ["mmus", "exclude" as const],
        ["pfal", "include" as const],
      ]),
    );

    expect(pattern).toContain("pfal:Y");
  });

  it("writes no :Y for an all-exclusion selection, which is its own question", () => {
    // Pure exclusion legitimately means "absent from these, or in no ortholog
    // group", which is the branch the query provides for it.
    const pattern = encodeProfilePattern(new Map([["hsap", "exclude" as const]]));

    expect(pattern).not.toContain(":Y");
  });

  it("never emits the other site's operator grammar", () => {
    const pattern = encodeProfilePattern(
      new Map([
        ["pfal", "include" as const],
        ["hsap", "exclude" as const],
      ]),
    );

    expect(pattern).not.toMatch(/[<>=]/);
  });
});
