/**
 * Tests for useDependentParams — TanStack Query-based dependent parameter refresh.
 *
 * Verifies that the hook watches upstream params via useWatch, triggers
 * refresh when values change, populates dependentOptions on success, and
 * captures errors in dependentErrors.
 *
 * @vitest-environment jsdom
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { FormProvider, useForm, type UseFormReturn } from "react-hook-form";
import { QueryClientProvider } from "@tanstack/react-query";
import { createTestQueryClient } from "@/lib/query/testing";
import type { ParamSpec } from "@pathfinder/shared";

// ---------------------------------------------------------------------------
// Hoisted mocks — must be declared before vi.mock calls
// ---------------------------------------------------------------------------

const refreshDependentParamsMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/sites", () => ({
  refreshDependentParams: refreshDependentParamsMock,
}));

import { useDependentParams } from "./useDependentParams";

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

const BASE_ARGS = {
  siteId: "plasmodb",
  recordType: "transcript",
  searchName: "GenesByTaxon",
} as const;

// ---------------------------------------------------------------------------
// FormProvider + QueryClientProvider wrapper
// ---------------------------------------------------------------------------

function createFormWrapper(defaultValues: Record<string, string>) {
  let formRef: UseFormReturn<Record<string, string>>;
  const queryClient = createTestQueryClient();

  function Wrapper({ children }: { children: ReactNode }) {
    const form = useForm({ defaultValues });
    formRef = form;
    return createElement(
      QueryClientProvider,
      { client: queryClient },
      createElement(FormProvider, { ...form, children }),
    );
  }

  return {
    Wrapper,
    getForm: () => formRef,
    queryClient,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useDependentParams", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    refreshDependentParamsMock.mockResolvedValue([]);
  });

  it("returns empty state when no specs have dependentParams", () => {
    const specsWithoutDeps = [INDEPENDENT_SPEC];
    const { Wrapper, getForm } = createFormWrapper({ some_other_param: "val" });

    const { result } = renderHook(
      () =>
        useDependentParams({
          control: getForm().control,
          specs: specsWithoutDeps,
          ...BASE_ARGS,
        }),
      { wrapper: Wrapper },
    );

    expect(result.current.dependentOptions).toEqual({});
    expect(result.current.dependentLoading).toEqual({});
    expect(result.current.dependentErrors).toEqual({});
  });

  it("triggers refresh when an upstream param value changes", async () => {
    const refreshedGeneList = makeParamSpec({
      name: "gene_list",
      vocabulary: ["NEW_GENE_1", "NEW_GENE_2"],
    });
    const refreshedGeneType = makeParamSpec({
      name: "gene_type",
      vocabulary: ["new_type_a", "new_type_b"],
    });
    refreshDependentParamsMock.mockResolvedValue([refreshedGeneList, refreshedGeneType]);

    const { Wrapper, getForm } = createFormWrapper({
      organism: "",
      gene_list: "",
      gene_type: "",
      some_other_param: "",
    });

    const { result } = renderHook(
      () =>
        useDependentParams({
          control: getForm().control,
          specs: ALL_SPECS,
          ...BASE_ARGS,
        }),
      { wrapper: Wrapper },
    );

    // Change the organism parameter (which has dependentParams)
    act(() => {
      getForm().setValue("organism", "Plasmodium falciparum 3D7");
    });

    // Wait for debounce + API resolution
    await waitFor(() => {
      expect(refreshDependentParamsMock).toHaveBeenCalledWith(
        "plasmodb",
        "transcript",
        "GenesByTaxon",
        "organism",
        expect.objectContaining({ organism: "Plasmodium falciparum 3D7" }),
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

  it("sets loading state while request is in flight", async () => {
    let resolveRefresh!: (value: ParamSpec[]) => void;
    refreshDependentParamsMock.mockReturnValue(
      new Promise<ParamSpec[]>((resolve) => {
        resolveRefresh = resolve;
      }),
    );

    const { Wrapper, getForm } = createFormWrapper({
      organism: "",
      gene_list: "",
      gene_type: "",
    });

    const { result } = renderHook(
      () =>
        useDependentParams({
          control: getForm().control,
          specs: [ORGANISM_SPEC, GENE_LIST_SPEC, GENE_TYPE_SPEC],
          ...BASE_ARGS,
        }),
      { wrapper: Wrapper },
    );

    act(() => {
      getForm().setValue("organism", "Plasmodium falciparum 3D7");
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

  it("captures errors in dependentErrors when the API call fails", async () => {
    refreshDependentParamsMock.mockRejectedValue(new Error("Network failure"));

    const { Wrapper, getForm } = createFormWrapper({
      organism: "",
      gene_list: "",
      gene_type: "",
    });

    const { result } = renderHook(
      () =>
        useDependentParams({
          control: getForm().control,
          specs: [ORGANISM_SPEC, GENE_LIST_SPEC, GENE_TYPE_SPEC],
          ...BASE_ARGS,
        }),
      { wrapper: Wrapper },
    );

    act(() => {
      getForm().setValue("organism", "Plasmodium falciparum 3D7");
    });

    await waitFor(() => {
      expect(result.current.dependentErrors["gene_list"]).toBe("Network failure");
      expect(result.current.dependentErrors["gene_type"]).toBe("Network failure");
    });

    // Loading should be cleared even on error
    expect(result.current.dependentLoading["gene_list"]).toBe(false);
    expect(result.current.dependentLoading["gene_type"]).toBe(false);
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

    const { Wrapper, getForm } = createFormWrapper({
      organism: "",
      gene_list: "",
    });

    const { result } = renderHook(
      () =>
        useDependentParams({
          control: getForm().control,
          specs: [ORGANISM_SPEC, GENE_LIST_SPEC],
          ...BASE_ARGS,
        }),
      { wrapper: Wrapper },
    );

    // First change
    act(() => {
      getForm().setValue("organism", "Plasmodium falciparum 3D7");
    });

    await waitFor(() => {
      expect(refreshDependentParamsMock).toHaveBeenCalledTimes(1);
    });

    // Second change before first resolves — wait for debounce to fire
    act(() => {
      getForm().setValue("organism", "Toxoplasma gondii ME49");
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
      expect(result.current.dependentOptions["gene_list"]![0]!.value).toBe(
        "TOXO_GENE",
      );
    });

    // Resolve the first (stale) — TQ ignores it because the query key has changed
    await act(async () => {
      resolveFirst([makeParamSpec({ name: "gene_list", vocabulary: ["STALE_GENE"] })]);
    });

    // Should still have the second response, not the first
    expect(result.current.dependentOptions["gene_list"]![0]!.value).toBe("TOXO_GENE");
  });

  it("does not trigger refresh when a param without dependentParams changes", async () => {
    const { Wrapper, getForm } = createFormWrapper({
      organism: "",
      some_other_param: "",
    });

    renderHook(
      () =>
        useDependentParams({
          control: getForm().control,
          specs: ALL_SPECS,
          ...BASE_ARGS,
        }),
      { wrapper: Wrapper },
    );

    act(() => {
      getForm().setValue("some_other_param", "new_value");
    });

    // Wait long enough for the debounce to fire if it were going to
    await act(async () => {
      await new Promise<void>((r) => setTimeout(r, 400));
    });

    expect(refreshDependentParamsMock).not.toHaveBeenCalled();
  });

  it("does not trigger refresh on initial mount", async () => {
    const { Wrapper, getForm } = createFormWrapper({
      organism: "Plasmodium falciparum 3D7",
      gene_list: "",
    });

    renderHook(
      () =>
        useDependentParams({
          control: getForm().control,
          specs: [ORGANISM_SPEC, GENE_LIST_SPEC],
          ...BASE_ARGS,
        }),
      { wrapper: Wrapper },
    );

    // Wait long enough for any debounced call to fire
    await act(async () => {
      await new Promise<void>((r) => setTimeout(r, 400));
    });

    expect(refreshDependentParamsMock).not.toHaveBeenCalled();
  });
});
