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
    paramSpecs: [],
    hiddenDefaults: {},
    recordTypeValue: "transcript",
    resolveRecordTypeForSearch: (rt?: string | null) => rt ?? "transcript",
    operatorValue: "",
    colocationParams: null,
    getDirtyFields: () => ({}),
    onUpdate: vi.fn(),
    onClose: vi.fn(),
    setError: vi.fn(),
    setFieldError: vi.fn(),
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
            general: expect.arrayContaining([expect.stringContaining("not available")]),
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
      colocationParams: {
        operation: "contains",
        strand: "same strand",
        output: "a",
        regionA: "upstream",
        beginA: "start",
        beginDirectionA: "-",
        beginOffsetA: 500,
        endA: "start",
        endDirectionA: "+",
        endOffsetA: 0,
        regionB: "exact",
        beginB: "start",
        beginDirectionB: "+",
        beginOffsetB: 0,
        endB: "stop",
        endDirectionB: "+",
        endOffsetB: 0,
      },
    });
    mockValidateSearchParams.mockResolvedValue({
      validation: { isValid: true, errors: { general: [], byKey: {} } },
    });

    const handleSave = buildStepSaveHandler(args);
    await handleSave();

    expect(args.onUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        operator: "COLOCATE",
        colocationParams: {
          operation: "contains",
          strand: "same strand",
          output: "a",
          regionA: "upstream",
          beginA: "start",
          beginDirectionA: "-",
          beginOffsetA: 500,
          endA: "start",
          endDirectionA: "+",
          endOffsetA: 0,
          regionB: "exact",
          beginB: "start",
          beginDirectionB: "+",
          beginOffsetB: 0,
          endB: "stop",
          endDirectionB: "+",
          endOffsetB: 0,
        },
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

  // ---------------------------------------------------------------------------
  // Gap 1: Dirty-only PATCH — only send params that the user actually changed
  // ---------------------------------------------------------------------------

  it("only includes dirty params and hidden defaults in the update", async () => {
    const args = makeBaseArgs({
      parameters: { organism: "Plasmodium falciparum 3D7", otherParam: "unchanged" },
      hiddenDefaults: { hiddenParam: "default-val" },
      getDirtyFields: () => ({ organism: true }),
    });
    mockValidateSearchParams.mockResolvedValue({
      validation: { isValid: true, errors: { general: [], byKey: {} } },
    });

    const handleSave = buildStepSaveHandler(args);
    await handleSave();

    const params = args.onUpdate.mock.calls[0]?.[0]?.parameters;
    // Dirty param included
    expect(params?.organism).toBe("Plasmodium falciparum 3D7");
    // Hidden default included
    expect(params?.hiddenParam).toBe("default-val");
    // Non-dirty param excluded
    expect(params).not.toHaveProperty("otherParam");
  });

  it("includes all params when dirtyFields is empty (no form context)", async () => {
    const args = makeBaseArgs({
      parameters: { organism: "Plasmodium falciparum 3D7", otherParam: "val" },
      getDirtyFields: () => ({}),
    });
    mockValidateSearchParams.mockResolvedValue({
      validation: { isValid: true, errors: { general: [], byKey: {} } },
    });

    const handleSave = buildStepSaveHandler(args);
    await handleSave();

    const params = args.onUpdate.mock.calls[0]?.[0]?.parameters;
    expect(params?.organism).toBe("Plasmodium falciparum 3D7");
    expect(params?.otherParam).toBe("val");
  });

  // ---------------------------------------------------------------------------
  // Gap 2: WDK field-level validation errors → setFieldError
  // ---------------------------------------------------------------------------

  it("calls setFieldError for each byKey validation error", async () => {
    const setFieldError = vi.fn();
    const args = makeBaseArgs({
      setFieldError,
    });
    const failResponse: SearchValidationResponse = {
      validation: {
        isValid: false,
        errors: {
          general: [],
          byKey: {
            organism: ["Invalid organism value"],
            text_expression: ["Expression too short", "Must contain wildcard"],
          },
        },
      },
    };
    mockValidateSearchParams.mockResolvedValue(failResponse);

    const handleSave = buildStepSaveHandler(args);
    await handleSave();

    expect(setFieldError).toHaveBeenCalledWith("organism", {
      type: "server",
      message: "Invalid organism value",
    });
    expect(setFieldError).toHaveBeenCalledWith("text_expression", {
      type: "server",
      message: "Expression too short",
    });
  });

  it("does not call setFieldError when byKey is empty", async () => {
    const setFieldError = vi.fn();
    const args = makeBaseArgs({
      setFieldError,
    });
    mockValidateSearchParams.mockResolvedValue({
      validation: {
        isValid: false,
        errors: { general: ["Something wrong"], byKey: {} },
      },
    });

    const handleSave = buildStepSaveHandler(args);
    await handleSave();

    expect(setFieldError).not.toHaveBeenCalled();
  });

  // ---------------------------------------------------------------------------
  // Gap 3: Multi-pick serialization — arrays → JSON strings for WDK
  // ---------------------------------------------------------------------------

  it("serializes multi-pick array values to JSON strings", async () => {
    const args = makeBaseArgs({
      parameters: { organism: ["GO:0006915", "GO:0006916"] },
      paramSpecs: [
        { name: "organism", type: "multi-pick-vocabulary", allowMultipleValues: true },
      ],
    });
    mockValidateSearchParams.mockResolvedValue({
      validation: { isValid: true, errors: { general: [], byKey: {} } },
    });

    const handleSave = buildStepSaveHandler(args);
    await handleSave();

    const params = args.onUpdate.mock.calls[0]?.[0]?.parameters;
    expect(params?.organism).toBe('["GO:0006915","GO:0006916"]');
  });

  it("does not double-serialize already-string parameters", async () => {
    const args = makeBaseArgs({
      parameters: { organism: "Plasmodium falciparum 3D7" },
      paramSpecs: [
        { name: "organism", type: "string" },
      ],
    });
    mockValidateSearchParams.mockResolvedValue({
      validation: { isValid: true, errors: { general: [], byKey: {} } },
    });

    const handleSave = buildStepSaveHandler(args);
    await handleSave();

    const params = args.onUpdate.mock.calls[0]?.[0]?.parameters;
    expect(params?.organism).toBe("Plasmodium falciparum 3D7");
  });
});
