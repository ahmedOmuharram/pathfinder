/**
 * Tests for useStepParameters — verifies that dependent parameter refresh
 * fires when a parameter with `dependentParams` changes, populates
 * dependentOptions on success, and captures errors in dependentErrors.
 *
 * @vitest-environment jsdom
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import type { ParamSpec, Search } from "@pathfinder/shared";

// ---------------------------------------------------------------------------
// Hoisted mocks — must be declared before vi.mock calls
// ---------------------------------------------------------------------------

const refreshDependentParamsMock = vi.hoisted(() => vi.fn());
const getParamSpecsMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/sites", () => ({
  getParamSpecs: getParamSpecsMock,
  refreshDependentParams: refreshDependentParamsMock,
}));

// Mock useParamSpecs to return controlled paramSpecs without calling API
const useParamSpecsMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/hooks/useParamSpecs", () => ({
  useParamSpecs: useParamSpecsMock,
}));

import { useStepParameters } from "./useStepParameters";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeParamSpec(overrides: Partial<ParamSpec>): ParamSpec {
  return {
    name: "test_param",
    displayName: "Test Param",
    type: "string",
    allowEmptyValue: true,
    allowMultipleValues: false,
    multiPick: false,
    minSelectedCount: null,
    maxSelectedCount: null,
    countOnlyLeaves: false,
    initialDisplayValue: null,
    vocabulary: null,
    min: null,
    max: null,
    increment: null,
    isNumber: false,
    displayType: null,
    isVisible: true,
    group: null,
    help: null,
    ...overrides,
  };
}

const ORGANISM_SPEC = makeParamSpec({
  name: "organism",
  displayName: "Organism",
  dependentParams: ["gene_list", "gene_type"],
  vocabulary: ["Plasmodium falciparum 3D7", "Toxoplasma gondii ME49"],
});

const GENE_LIST_SPEC = makeParamSpec({
  name: "gene_list",
  displayName: "Gene List",
  vocabulary: ["PF3D7_0100100", "PF3D7_0100200"],
});

const GENE_TYPE_SPEC = makeParamSpec({
  name: "gene_type",
  displayName: "Gene Type",
  vocabulary: ["protein_coding", "rRNA"],
});

const INDEPENDENT_SPEC = makeParamSpec({
  name: "some_other_param",
  displayName: "Some Other Param",
  // No dependentParams
});

const ALL_SPECS = [ORGANISM_SPEC, GENE_LIST_SPEC, GENE_TYPE_SPEC, INDEPENDENT_SPEC];

function makeBaseArgs(overrides: Partial<Parameters<typeof useStepParameters>[0]> = {}) {
  return {
    stepId: "step-1",
    siteId: "plasmodb",
    recordType: "transcript",
    kind: "search" as const,
    searchName: "GenesByTaxon",
    selectedSearch: null as Search | null,
    isSearchNameAvailable: true,
    apiRecordTypeValue: "transcript",
    resolveRecordTypeForSearch: () => "transcript",
    initialParameters: {},
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useStepParameters dependent param refresh", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useParamSpecsMock.mockReturnValue({ paramSpecs: ALL_SPECS, isLoading: false });
    refreshDependentParamsMock.mockResolvedValue([]);
  });

  it("returns empty dependent state initially", () => {
    const { result } = renderHook(() => useStepParameters(makeBaseArgs()));
    expect(result.current.dependentOptions).toEqual({});
    expect(result.current.dependentLoading).toEqual({});
    expect(result.current.dependentErrors).toEqual({});
  });

  it("triggers refresh when a param with dependentParams changes", async () => {
    const refreshedGeneList = makeParamSpec({
      name: "gene_list",
      vocabulary: ["NEW_GENE_1", "NEW_GENE_2"],
    });
    const refreshedGeneType = makeParamSpec({
      name: "gene_type",
      vocabulary: ["new_type_a", "new_type_b"],
    });
    refreshDependentParamsMock.mockResolvedValue([refreshedGeneList, refreshedGeneType]);

    const { result } = renderHook(() => useStepParameters(makeBaseArgs()));

    // Change the organism parameter (which has dependentParams)
    act(() => {
      result.current.setParameters({ organism: "Plasmodium falciparum 3D7" });
    });

    // The hook should call refreshDependentParams
    await waitFor(() => {
      expect(refreshDependentParamsMock).toHaveBeenCalledWith(
        "plasmodb",
        "transcript",
        "GenesByTaxon",
        "organism",
        { organism: "Plasmodium falciparum 3D7" },
      );
    });

    // After resolution, dependentOptions should be populated
    await waitFor(() => {
      expect(result.current.dependentOptions["gene_list"]).toBeDefined();
      expect(result.current.dependentOptions["gene_list"]!.length).toBeGreaterThan(0);
      expect(result.current.dependentOptions["gene_type"]).toBeDefined();
      expect(result.current.dependentOptions["gene_type"]!.length).toBeGreaterThan(0);
    });

    // Loading should be cleared
    expect(result.current.dependentLoading["gene_list"]).toBe(false);
    expect(result.current.dependentLoading["gene_type"]).toBe(false);
  });

  it("does NOT trigger refresh when a param without dependentParams changes", async () => {
    const { result } = renderHook(() => useStepParameters(makeBaseArgs()));

    // Change a param that has no dependentParams
    act(() => {
      result.current.setParameters({ some_other_param: "new_value" });
    });

    // Wait a tick to ensure any effects have run
    await act(async () => {
      await new Promise<void>((r) => setTimeout(r, 50));
    });

    expect(refreshDependentParamsMock).not.toHaveBeenCalled();
  });

  it("captures errors in dependentErrors when the API call fails", async () => {
    refreshDependentParamsMock.mockRejectedValue(new Error("Network failure"));

    const { result } = renderHook(() => useStepParameters(makeBaseArgs()));

    act(() => {
      result.current.setParameters({ organism: "Plasmodium falciparum 3D7" });
    });

    await waitFor(() => {
      expect(result.current.dependentErrors["gene_list"]).toBe("Network failure");
      expect(result.current.dependentErrors["gene_type"]).toBe("Network failure");
    });

    // Loading should be cleared even on error
    expect(result.current.dependentLoading["gene_list"]).toBe(false);
    expect(result.current.dependentLoading["gene_type"]).toBe(false);
  });

  it("sets dependentLoading for dependent params while request is in flight", async () => {
    // Create a promise that we control resolution of
    let resolveRefresh!: (value: ParamSpec[]) => void;
    refreshDependentParamsMock.mockReturnValue(
      new Promise<ParamSpec[]>((resolve) => {
        resolveRefresh = resolve;
      }),
    );

    const { result } = renderHook(() => useStepParameters(makeBaseArgs()));

    act(() => {
      result.current.setParameters({ organism: "Plasmodium falciparum 3D7" });
    });

    // While in flight, loading should be true for dependent params
    await waitFor(() => {
      expect(result.current.dependentLoading["gene_list"]).toBe(true);
      expect(result.current.dependentLoading["gene_type"]).toBe(true);
    });

    // Resolve the request
    await act(async () => {
      resolveRefresh([
        makeParamSpec({ name: "gene_list", vocabulary: ["G1"] }),
        makeParamSpec({ name: "gene_type", vocabulary: ["T1"] }),
      ]);
    });

    // After resolution, loading should be false
    await waitFor(() => {
      expect(result.current.dependentLoading["gene_list"]).toBe(false);
      expect(result.current.dependentLoading["gene_type"]).toBe(false);
    });
  });

  it("ignores stale responses when a newer refresh is triggered", async () => {
    let resolveFirst!: (value: ParamSpec[]) => void;
    let resolveSecond!: (value: ParamSpec[]) => void;

    refreshDependentParamsMock
      .mockReturnValueOnce(
        new Promise<ParamSpec[]>((resolve) => {
          resolveFirst = resolve;
        }),
      )
      .mockReturnValueOnce(
        new Promise<ParamSpec[]>((resolve) => {
          resolveSecond = resolve;
        }),
      );

    const { result } = renderHook(() => useStepParameters(makeBaseArgs()));

    // First change
    act(() => {
      result.current.setParameters({ organism: "Plasmodium falciparum 3D7" });
    });

    await waitFor(() => {
      expect(refreshDependentParamsMock).toHaveBeenCalledTimes(1);
    });

    // Second change before first resolves
    act(() => {
      result.current.setParameters({
        organism: "Toxoplasma gondii ME49",
      });
    });

    await waitFor(() => {
      expect(refreshDependentParamsMock).toHaveBeenCalledTimes(2);
    });

    // Resolve the second (newer) first
    await act(async () => {
      resolveSecond([makeParamSpec({ name: "gene_list", vocabulary: ["TOXO_GENE"] })]);
    });

    await waitFor(() => {
      expect(result.current.dependentOptions["gene_list"]).toBeDefined();
      expect(result.current.dependentOptions["gene_list"]![0]!.value).toBe("TOXO_GENE");
    });

    // Resolve the first (stale) — should be ignored
    await act(async () => {
      resolveFirst([makeParamSpec({ name: "gene_list", vocabulary: ["STALE_GENE"] })]);
    });

    // Should still have the second response, not the first
    expect(result.current.dependentOptions["gene_list"]![0]!.value).toBe("TOXO_GENE");
  });

  it("does not trigger refresh for combine kind steps", async () => {
    useParamSpecsMock.mockReturnValue({ paramSpecs: ALL_SPECS, isLoading: false });

    const { result } = renderHook(() =>
      useStepParameters(makeBaseArgs({ kind: "combine" })),
    );

    act(() => {
      result.current.setParameters({ organism: "Plasmodium falciparum 3D7" });
    });

    await act(async () => {
      await new Promise<void>((r) => setTimeout(r, 50));
    });

    expect(refreshDependentParamsMock).not.toHaveBeenCalled();
  });
});
