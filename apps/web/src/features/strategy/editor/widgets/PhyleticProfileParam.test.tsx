// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import {
  buildPhyleticTree,
  encodeProfilePattern,
  decodeProfilePattern,
  claimsPhyleticParams,
  PhyleticProfileParam,
} from "./PhyleticProfileParam";
import type { ParamSpec } from "@/features/strategy/parameters/spec";

afterEach(cleanup);

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

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

function makeAllSpecs(): ParamSpec[] {
  return [
    { name: "profile_pattern", type: "string" },
    { name: "included_species", type: "string" },
    { name: "excluded_species", type: "string" },
    {
      name: "phyletic_indent_map",
      type: "string",
      vocabulary: INDENT_MAP_VOCAB,
    },
    { name: "phyletic_term_map", type: "string", vocabulary: TERM_MAP_VOCAB },
  ];
}

function makeDefaultParameters() {
  return {
    profile_pattern: "",
    included_species: "",
    excluded_species: "",
    phyletic_indent_map: "",
    phyletic_term_map: "",
  };
}

// ---------------------------------------------------------------------------
// buildPhyleticTree
// ---------------------------------------------------------------------------

describe("buildPhyleticTree", () => {
  it("builds correct hierarchy from term/indent map vocabs", () => {
    const roots = buildPhyleticTree(TERM_MAP_VOCAB, INDENT_MAP_VOCAB);
    expect(roots).toHaveLength(2); // EUKARYA, BACTERIA
    expect(roots[0].code).toBe("EUKARYA");
    expect(roots[0].label).toBe("Eukaryota");
    expect(roots[0].depth).toBe(1);
    expect(roots[0].children).toHaveLength(2);
    expect(roots[0].children[0].code).toBe("pfal");
    expect(roots[0].children[0].label).toBe("P. falciparum");
    expect(roots[0].children[1].code).toBe("hsap");
    expect(roots[0].children[1].label).toBe("H. sapiens");
    expect(roots[1].code).toBe("BACTERIA");
    expect(roots[1].children).toHaveLength(1);
    expect(roots[1].children[0].code).toBe("ecol");
  });

  it("returns empty array for null/undefined input", () => {
    expect(buildPhyleticTree(null, null)).toEqual([]);
    expect(buildPhyleticTree(undefined, undefined)).toEqual([]);
  });

  it("handles empty arrays", () => {
    expect(buildPhyleticTree([], [])).toEqual([]);
  });

  it("handles single species (no tree depth)", () => {
    const terms = [["pfal", "P. falciparum", null]];
    const indents = [["pfal", 1, null]];
    const roots = buildPhyleticTree(terms, indents);
    expect(roots).toHaveLength(1);
    expect(roots[0].code).toBe("pfal");
    expect(roots[0].children).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// encodeProfilePattern
// ---------------------------------------------------------------------------

describe("encodeProfilePattern", () => {
  it("encodes include as code>=1T", () => {
    const states = new Map([["pfal", "include" as const]]);
    expect(encodeProfilePattern(states)).toBe("pfal>=1T");
  });

  it("encodes exclude as code=0T", () => {
    const states = new Map([["hsap", "exclude" as const]]);
    expect(encodeProfilePattern(states)).toBe("hsap=0T");
  });

  it("encodes multiple entries comma-separated", () => {
    const states = new Map([
      ["pfal", "include" as const],
      ["hsap", "exclude" as const],
    ]);
    const result = encodeProfilePattern(states);
    expect(result).toContain("pfal>=1T");
    expect(result).toContain("hsap=0T");
    expect(result.split(",")).toHaveLength(2);
  });

  it("skips unconstrained entries", () => {
    const states = new Map([
      ["pfal", "include" as const],
      ["hsap", "unconstrained" as const],
    ]);
    expect(encodeProfilePattern(states)).toBe("pfal>=1T");
  });

  it("returns empty string when no constrained entries", () => {
    const states = new Map([["pfal", "unconstrained" as const]]);
    expect(encodeProfilePattern(states)).toBe("");
  });

  it("returns empty string for empty map", () => {
    expect(encodeProfilePattern(new Map())).toBe("");
  });
});

// ---------------------------------------------------------------------------
// decodeProfilePattern
// ---------------------------------------------------------------------------

describe("decodeProfilePattern", () => {
  it("decodes include pattern (>=1T)", () => {
    const states = decodeProfilePattern("pfal>=1T");
    expect(states.get("pfal")).toBe("include");
  });

  it("decodes exclude pattern (=0T)", () => {
    const states = decodeProfilePattern("hsap=0T");
    expect(states.get("hsap")).toBe("exclude");
  });

  it("decodes multiple comma-separated entries", () => {
    const states = decodeProfilePattern("pfal>=1T,hsap=0T");
    expect(states.get("pfal")).toBe("include");
    expect(states.get("hsap")).toBe("exclude");
    expect(states.size).toBe(2);
  });

  it("handles whitespace in entries", () => {
    const states = decodeProfilePattern("pfal>=1T , hsap=0T");
    expect(states.get("pfal")).toBe("include");
    expect(states.get("hsap")).toBe("exclude");
  });

  it("returns empty map for empty string", () => {
    expect(decodeProfilePattern("").size).toBe(0);
  });

  it("returns empty map for undefined-like input", () => {
    expect(decodeProfilePattern("").size).toBe(0);
  });

  it("roundtrips with encodeProfilePattern", () => {
    const original = new Map([
      ["pfal", "include" as const],
      ["hsap", "exclude" as const],
      ["ecol", "include" as const],
    ]);
    const encoded = encodeProfilePattern(original);
    const decoded = decodeProfilePattern(encoded);
    expect(decoded.get("pfal")).toBe("include");
    expect(decoded.get("hsap")).toBe("exclude");
    expect(decoded.get("ecol")).toBe("include");
  });
});

// ---------------------------------------------------------------------------
// claimsPhyleticParams
// ---------------------------------------------------------------------------

describe("claimsPhyleticParams", () => {
  it("returns all 5 param names when all present", () => {
    const specs = makeAllSpecs();
    const claimed = claimsPhyleticParams(specs);
    expect(claimed).toHaveLength(5);
    expect(claimed).toContain("profile_pattern");
    expect(claimed).toContain("included_species");
    expect(claimed).toContain("excluded_species");
    expect(claimed).toContain("phyletic_indent_map");
    expect(claimed).toContain("phyletic_term_map");
  });

  it("returns empty array when one param is missing", () => {
    const specs = makeAllSpecs().filter((s) => s.name !== "profile_pattern");
    expect(claimsPhyleticParams(specs)).toEqual([]);
  });

  it("returns empty array for empty specs", () => {
    expect(claimsPhyleticParams([])).toEqual([]);
  });

  it("returns empty array when only some phyletic params present", () => {
    const specs: ParamSpec[] = [
      { name: "profile_pattern" },
      { name: "included_species" },
    ];
    expect(claimsPhyleticParams(specs)).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Component rendering
// ---------------------------------------------------------------------------

describe("PhyleticProfileParam component", () => {
  it("renders tree nodes from vocab data", () => {
    const specs = makeAllSpecs();
    const parameters = {
      ...makeDefaultParameters(),
      phyletic_term_map: TERM_MAP_VOCAB,
      phyletic_indent_map: INDENT_MAP_VOCAB,
    };
    render(
      <PhyleticProfileParam
        specs={specs}
        allSpecs={specs}
        parameters={parameters}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByText("Eukaryota")).toBeTruthy();
    expect(screen.getByText("Bacteria")).toBeTruthy();
    // Leaf nodes should be visible (default: top 2 depth levels expanded)
    expect(screen.getByText("P. falciparum")).toBeTruthy();
    expect(screen.getByText("H. sapiens")).toBeTruthy();
    expect(screen.getByText("E. coli")).toBeTruthy();
  });

  it("clicking tri-state icon cycles through states", () => {
    const onChange = vi.fn();
    const specs = makeAllSpecs();
    const parameters = {
      ...makeDefaultParameters(),
      phyletic_term_map: TERM_MAP_VOCAB,
      phyletic_indent_map: INDENT_MAP_VOCAB,
    };
    render(
      <PhyleticProfileParam
        specs={specs}
        allSpecs={specs}
        parameters={parameters}
        onChange={onChange}
      />,
    );

    // Find the toggle button for P. falciparum
    const pfalRow = screen.getByText("P. falciparum").closest("[data-node]");
    expect(pfalRow).toBeTruthy();
    const toggleBtn = pfalRow!.querySelector("[data-toggle]") as HTMLElement;
    expect(toggleBtn).toBeTruthy();

    // Click 1: unconstrained -> include
    fireEvent.click(toggleBtn);
    expect(onChange).toHaveBeenCalledTimes(1);
    const firstCall = onChange.mock.calls[0][0];
    expect(firstCall.profile_pattern).toContain("pfal>=1T");

    // Click 2: include -> exclude
    fireEvent.click(toggleBtn);
    expect(onChange).toHaveBeenCalledTimes(2);
    const secondCall = onChange.mock.calls[1][0];
    expect(secondCall.profile_pattern).toContain("pfal=0T");

    // Click 3: exclude -> unconstrained
    fireEvent.click(toggleBtn);
    expect(onChange).toHaveBeenCalledTimes(3);
    const thirdCall = onChange.mock.calls[2][0];
    expect(thirdCall.profile_pattern).not.toContain("pfal");
  });

  it("shows correct summary footer counts", () => {
    const specs = makeAllSpecs();
    const parameters = {
      ...makeDefaultParameters(),
      phyletic_term_map: TERM_MAP_VOCAB,
      phyletic_indent_map: INDENT_MAP_VOCAB,
      profile_pattern: "pfal>=1T,hsap=0T",
    };
    render(
      <PhyleticProfileParam
        specs={specs}
        allSpecs={specs}
        parameters={parameters}
        onChange={vi.fn()}
      />,
    );
    // 1 included (pfal), 1 excluded (hsap), 3 unconstrained (EUKARYA, BACTERIA, ecol)
    expect(screen.getByText(/1 included/)).toBeTruthy();
    expect(screen.getByText(/1 excluded/)).toBeTruthy();
    expect(screen.getByText(/3 unconstrained/)).toBeTruthy();
  });

  it("search filters tree nodes by label", () => {
    const specs = makeAllSpecs();
    const parameters = {
      ...makeDefaultParameters(),
      phyletic_term_map: TERM_MAP_VOCAB,
      phyletic_indent_map: INDENT_MAP_VOCAB,
    };
    render(
      <PhyleticProfileParam
        specs={specs}
        allSpecs={specs}
        parameters={parameters}
        onChange={vi.fn()}
      />,
    );

    const searchInput = screen.getByPlaceholderText(/search/i);
    fireEvent.change(searchInput, { target: { value: "falciparum" } });

    // P. falciparum should still be visible
    expect(screen.getByText("P. falciparum")).toBeTruthy();
    // Non-matching leaf nodes should be hidden
    expect(screen.queryByText("E. coli")).toBeNull();
  });

  it("initializes state from existing profile_pattern", () => {
    const specs = makeAllSpecs();
    const parameters = {
      ...makeDefaultParameters(),
      phyletic_term_map: TERM_MAP_VOCAB,
      phyletic_indent_map: INDENT_MAP_VOCAB,
      profile_pattern: "pfal>=1T",
    };
    render(
      <PhyleticProfileParam
        specs={specs}
        allSpecs={specs}
        parameters={parameters}
        onChange={vi.fn()}
      />,
    );

    const pfalRow = screen.getByText("P. falciparum").closest("[data-node]");
    const toggleBtn = pfalRow!.querySelector("[data-toggle]") as HTMLElement;
    // Should show include icon (checkmark)
    expect(toggleBtn.textContent).toContain("\u2713");
  });

  it("passes through structural params unchanged on onChange", () => {
    const onChange = vi.fn();
    const specs = makeAllSpecs();
    const parameters = {
      ...makeDefaultParameters(),
      phyletic_term_map: TERM_MAP_VOCAB,
      phyletic_indent_map: INDENT_MAP_VOCAB,
    };
    render(
      <PhyleticProfileParam
        specs={specs}
        allSpecs={specs}
        parameters={parameters}
        onChange={onChange}
      />,
    );

    // Toggle any node
    const pfalRow = screen.getByText("P. falciparum").closest("[data-node]");
    const toggleBtn = pfalRow!.querySelector("[data-toggle]") as HTMLElement;
    fireEvent.click(toggleBtn);

    const call = onChange.mock.calls[0][0];
    expect(call.phyletic_term_map).toBe(TERM_MAP_VOCAB);
    expect(call.phyletic_indent_map).toBe(INDENT_MAP_VOCAB);
  });

  it("renders legend showing the three states", () => {
    const specs = makeAllSpecs();
    const parameters = {
      ...makeDefaultParameters(),
      phyletic_term_map: TERM_MAP_VOCAB,
      phyletic_indent_map: INDENT_MAP_VOCAB,
    };
    render(
      <PhyleticProfileParam
        specs={specs}
        allSpecs={specs}
        parameters={parameters}
        onChange={vi.fn()}
      />,
    );

    // Legend uses exact text like "○ unconstrained", "✓ include", "✗ exclude"
    // Use getAllByText since these words also appear in the summary footer
    const unconstrainedMatches = screen.getAllByText(/unconstrained/i);
    expect(unconstrainedMatches.length).toBeGreaterThanOrEqual(2); // legend + summary
    const includeMatches = screen.getAllByText(/include/i);
    expect(includeMatches.length).toBeGreaterThanOrEqual(2); // legend + summary
    const excludeMatches = screen.getAllByText(/exclude/i);
    expect(excludeMatches.length).toBeGreaterThanOrEqual(2); // legend + summary
  });
});
