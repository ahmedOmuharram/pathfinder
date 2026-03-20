import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

// Mock the http module before importing the module under test
vi.mock("@/lib/api/http", () => ({
  requestJson: vi.fn(),
  requestJsonValidated: vi.fn(),
  buildUrl: vi.fn((path: string) => `http://localhost:8000${path}`),
  getAuthHeaders: vi.fn(),
  APIError: class APIError extends Error {
    status: number;
    statusText: string;
    url: string;
    data: unknown;
    constructor(
      message: string,
      args: { status: number; statusText: string; url: string; data: unknown },
    ) {
      super(message);
      this.name = "APIError";
      this.status = args.status;
      this.statusText = args.statusText;
      this.url = args.url;
      this.data = args.data;
    }
  },
}));

import {
  getStrategy,
  createStrategy,
  updateStrategy,
  restoreStrategy,
  listStrategies,
  listDismissedStrategies,
} from "./strategies";
import { requestJson, requestJsonValidated } from "@/lib/api/http";
const mockRequestJsonValidated = vi.mocked(requestJsonValidated);
const mockRequestJson = vi.mocked(requestJson);

beforeEach(() => {
  mockRequestJsonValidated.mockReset();
  mockRequestJson.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const VALID_UUID = "a1b2c3d4-e5f6-1a2b-9c3d-e4f5a6b7c8d9";

/** Minimal API response — steps and rootStepId omitted (as they are optional). */
const minimalApiResponse = {
  id: VALID_UUID,
  name: "Test Strategy",
  siteId: "PlasmoDB",
  recordType: "transcript",
  isSaved: true,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

/** API response with steps explicitly omitted (undefined). */
const responseWithoutSteps = {
  id: VALID_UUID,
  name: "No Steps Strategy",
  siteId: "PlasmoDB",
  recordType: null,
  isSaved: false,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

/** API response with all fields populated. */
const fullApiResponse = {
  id: VALID_UUID,
  name: "Full Strategy",
  siteId: "PlasmoDB",
  recordType: "gene",
  steps: [{ id: "step-1", displayName: "Step 1", searchName: "GenesByText" }],
  rootStepId: "step-1",
  isSaved: true,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

// ---------------------------------------------------------------------------
// withDefaults (tested indirectly through public functions)
// ---------------------------------------------------------------------------

describe("withDefaults applied to API functions", () => {
  describe("getStrategy", () => {
    it("defaults steps to [] when API omits them", async () => {
      mockRequestJsonValidated.mockResolvedValueOnce(responseWithoutSteps);

      const result = await getStrategy(VALID_UUID);

      expect(result.steps).toEqual([]);
    });

    it("defaults rootStepId to null when API omits it", async () => {
      mockRequestJsonValidated.mockResolvedValueOnce(minimalApiResponse);

      const result = await getStrategy(VALID_UUID);

      expect(result.rootStepId).toBeNull();
    });

    it("defaults isSaved to false when API omits it", async () => {
      // Simulate an API response where isSaved is missing
      const { isSaved: _, ...withoutIsSaved } = minimalApiResponse;
      mockRequestJsonValidated.mockResolvedValueOnce(withoutIsSaved);

      const result = await getStrategy(VALID_UUID);

      expect(result.isSaved).toBe(false);
    });

    it("preserves steps when API includes them", async () => {
      mockRequestJsonValidated.mockResolvedValueOnce(fullApiResponse);

      const result = await getStrategy(VALID_UUID);

      expect(result.steps).toHaveLength(1);
      expect(result.steps[0]!.id).toBe("step-1");
    });

    it("preserves isSaved=true when API includes it", async () => {
      mockRequestJsonValidated.mockResolvedValueOnce(fullApiResponse);

      const result = await getStrategy(VALID_UUID);

      expect(result.isSaved).toBe(true);
    });

    it("returns a complete Strategy shape with all required fields", async () => {
      mockRequestJsonValidated.mockResolvedValueOnce(responseWithoutSteps);

      const result = await getStrategy(VALID_UUID);

      // All required Strategy fields must be present
      expect(result).toEqual(
        expect.objectContaining({
          id: VALID_UUID,
          name: "No Steps Strategy",
          siteId: "PlasmoDB",
          steps: [],
          rootStepId: null,
          recordType: null,
          isSaved: false,
        }),
      );
    });
  });

  describe("createStrategy", () => {
    it("defaults steps to [] when API omits them", async () => {
      mockRequestJsonValidated.mockResolvedValueOnce(responseWithoutSteps);

      const result = await createStrategy({
        name: "New",
        siteId: "PlasmoDB",
        plan: { recordType: "gene", root: { searchName: "GenesByText" } },
      });

      expect(result.steps).toEqual([]);
      expect(result.rootStepId).toBeNull();
    });

    it("preserves full response when all fields present", async () => {
      mockRequestJsonValidated.mockResolvedValueOnce(fullApiResponse);

      const result = await createStrategy({
        name: "New",
        siteId: "PlasmoDB",
        plan: { recordType: "gene", root: { searchName: "GenesByText" } },
      });

      expect(result.steps).toHaveLength(1);
      expect(result.rootStepId).toBe("step-1");
    });
  });

  describe("updateStrategy", () => {
    it("defaults steps to [] when API omits them", async () => {
      mockRequestJsonValidated.mockResolvedValueOnce(responseWithoutSteps);

      const result = await updateStrategy(VALID_UUID, { name: "Renamed" });

      expect(result.steps).toEqual([]);
      expect(result.rootStepId).toBeNull();
    });

    it("preserves full response when all fields present", async () => {
      mockRequestJsonValidated.mockResolvedValueOnce(fullApiResponse);

      const result = await updateStrategy(VALID_UUID, { name: "Renamed" });

      expect(result.steps).toHaveLength(1);
    });
  });

  describe("restoreStrategy", () => {
    it("defaults steps to [] when API omits them", async () => {
      mockRequestJson.mockResolvedValueOnce(responseWithoutSteps);

      const result = await restoreStrategy(VALID_UUID);

      expect(result.steps).toEqual([]);
      expect(result.rootStepId).toBeNull();
    });

    it("preserves full response when all fields present", async () => {
      mockRequestJson.mockResolvedValueOnce(fullApiResponse);

      const result = await restoreStrategy(VALID_UUID);

      expect(result.steps).toHaveLength(1);
    });
  });

  describe("listStrategies", () => {
    it("applies withDefaults to each item", async () => {
      mockRequestJsonValidated.mockResolvedValueOnce([
        responseWithoutSteps,
        minimalApiResponse,
      ]);

      const result = await listStrategies();

      expect(result).toHaveLength(2);
      for (const s of result) {
        expect(s.steps).toEqual([]);
        expect(s.rootStepId).toBeNull();
      }
    });
  });

  describe("listDismissedStrategies", () => {
    it("applies withDefaults to each item", async () => {
      mockRequestJson.mockResolvedValueOnce([responseWithoutSteps]);

      const result = await listDismissedStrategies("PlasmoDB");

      expect(result).toHaveLength(1);
      expect(result[0]!.steps).toEqual([]);
      expect(result[0]!.rootStepId).toBeNull();
    });
  });
});
