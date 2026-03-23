// @vitest-environment jsdom
/**
 * Tests for useStepSaveHandler — the save workflow extracted from
 * useStepEditorState: validation, param coercion, API validation call,
 * error formatting, and the final onUpdate/onClose call.
 */

import { describe, expect, it, vi, afterEach } from "vitest";
import type { Step, SearchValidationResponse } from "@pathfinder/shared";

const mockValidateSearchParams = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/sites", () => ({
  validateSearchParams: (...args: unknown[]) => mockValidateSearchParams(...args),
}));

import { buildStepSaveHandler } from "./useStepSaveHandler";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeBaseArgs(overrides: Record<string, unknown> = {}) {
  return {
    step: {
      id: "s1",
      displayName: "Step 1",
      searchName: "GenesByTaxon",
      recordType: "transcript",
      parameters: { organism: "Plasmodium falciparum 3D7" },
      isBuilt: false,
      isFiltered: false,
    } as Step,
    siteId: "PlasmoDB",
    name: "Step 1",
    oldName: "Step 1",
    searchName: "GenesByTaxon",
    selectedSearch: { recordType: "transcript" },
    isSearchNameAvailable: true,
    kind: "search" as const,
    parameters: { organism: "Plasmodium falciparum 3D7" },
    showRaw: false,
    rawParams: "{}",
    paramSpecs: [],
    hiddenDefaults: {},
    recordTypeValue: "transcript",
    resolveRecordTypeForSearch: (rt?: string | null) => rt ?? "transcript",
    operatorValue: "",
    colocationParams: null,
    onUpdate: vi.fn(),
    onClose: vi.fn(),
    setError: vi.fn(),
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("buildStepSaveHandler", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("calls onUpdate and onClose on successful save", async () => {
    const args = makeBaseArgs();
    const successResponse: SearchValidationResponse = {
      validation: { isValid: true, errors: { general: [], byKey: {} } },
    };
    mockValidateSearchParams.mockResolvedValue(successResponse);

    const handleSave = buildStepSaveHandler(args);
    await handleSave();

    expect(args.onUpdate).toHaveBeenCalledTimes(1);
    expect(args.onClose).toHaveBeenCalledTimes(1);
    expect(args.onUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        displayName: "Step 1",
        searchName: "GenesByTaxon",
      }),
    );
  });

  it("sets validation error when search name is unavailable", async () => {
    const args = makeBaseArgs({ isSearchNameAvailable: false });

    const handleSave = buildStepSaveHandler(args);
    await handleSave();

    // Still calls onUpdate but with validation set
    expect(args.onUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        validation: expect.objectContaining({
          isValid: false,
          errors: expect.objectContaining({
            general: expect.arrayContaining([
              expect.stringContaining("not available"),
            ]),
          }),
        }),
      }),
    );
    expect(args.onClose).toHaveBeenCalledTimes(1);
  });

  it("sets validation error from backend validation response", async () => {
    const args = makeBaseArgs();
    const failResponse: SearchValidationResponse = {
      validation: {
        isValid: false,
        errors: {
          general: ["Something is wrong"],
          byKey: {},
        },
      },
    };
    mockValidateSearchParams.mockResolvedValue(failResponse);

    const handleSave = buildStepSaveHandler(args);
    await handleSave();

    expect(args.onUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        validation: expect.objectContaining({
          isValid: false,
          errors: expect.objectContaining({
            general: expect.arrayContaining([
              expect.stringContaining("Something is wrong"),
            ]),
          }),
        }),
      }),
    );
  });

  it("sets error on invalid JSON when showRaw is true", async () => {
    const args = makeBaseArgs({ showRaw: true, rawParams: "{bad json" });

    const handleSave = buildStepSaveHandler(args);
    await handleSave();

    expect(args.setError).toHaveBeenCalledWith("Invalid JSON in parameters");
    expect(args.onUpdate).not.toHaveBeenCalled();
    expect(args.onClose).not.toHaveBeenCalled();
  });

  it("requires operator for combine steps", async () => {
    const args = makeBaseArgs({
      kind: "combine",
      operatorValue: "",
      step: {
        id: "s1",
        displayName: "Combine",
        searchName: null,
        recordType: "transcript",
        operator: null,
      } as unknown as Step,
    });

    const handleSave = buildStepSaveHandler(args);
    await handleSave();

    expect(args.setError).toHaveBeenCalledWith(
      "Combine steps require an operator to be selected.",
    );
    expect(args.onUpdate).not.toHaveBeenCalled();
  });

  it("includes operator and colocationParams for COLOCATE operator", async () => {
    const args = makeBaseArgs({
      kind: "combine",
      operatorValue: "COLOCATE",
      colocationParams: { upstream: 500, downstream: 500, strand: "same" },
    });
    mockValidateSearchParams.mockResolvedValue({
      validation: { isValid: true, errors: { general: [], byKey: {} } },
    });

    const handleSave = buildStepSaveHandler(args);
    await handleSave();

    expect(args.onUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        operator: "COLOCATE",
        colocationParams: { upstream: 500, downstream: 500, strand: "same" },
      }),
    );
  });

  it("merges hidden defaults with lowest priority", async () => {
    const args = makeBaseArgs({
      hiddenDefaults: { hiddenParam: "default-val", organism: "should-be-overridden" },
      parameters: { organism: "Plasmodium falciparum 3D7" },
    });
    mockValidateSearchParams.mockResolvedValue({
      validation: { isValid: true, errors: { general: [], byKey: {} } },
    });

    const handleSave = buildStepSaveHandler(args);
    await handleSave();

    const params = args.onUpdate.mock.calls[0]?.[0]?.parameters;
    // User edits win over hidden defaults
    expect(params?.organism).toBe("Plasmodium falciparum 3D7");
    // Hidden defaults fill in missing params
    expect(params?.hiddenParam).toBe("default-val");
  });
});
