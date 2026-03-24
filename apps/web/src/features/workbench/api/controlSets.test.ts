import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

// Mock requestJson, requestVoid, and requestBlob before importing the module under test
vi.mock("@/lib/api/http", () => ({
  requestJson: vi.fn(),
  requestVoid: vi.fn(),
  requestBlob: vi.fn(),
}));

import {
  listControlSets,
  getControlSet,
  createControlSet,
  deleteControlSet,
  getExperimentReport,
} from "./controlSets";
import { requestJson, requestVoid, requestBlob } from "@/lib/api/http";
import type { ControlSet } from "@pathfinder/shared";

const mockRequestJson = vi.mocked(requestJson);
const mockRequestVoid = vi.mocked(requestVoid);
const mockRequestBlob = vi.mocked(requestBlob);

beforeEach(() => {
  mockRequestJson.mockReset();
  mockRequestVoid.mockReset();
  mockRequestBlob.mockReset();
});

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const controlSetFixture: ControlSet = {
  id: "cs-1",
  name: "Kinase Controls",
  siteId: "plasmodb",
  recordType: "gene",
  positiveIds: ["PF3D7_0100100", "PF3D7_0200200"],
  negativeIds: ["PF3D7_0300300", "PF3D7_0400400"],
  source: "curation",
  tags: ["kinase", "validated"],
  provenanceNotes: "Manually curated from literature review",
  version: 1,
  isPublic: true,
  userId: "user-1",
  createdAt: "2026-01-01T00:00:00Z",
};

// ---------------------------------------------------------------------------
// listControlSets
// ---------------------------------------------------------------------------

describe("listControlSets", () => {
  it("sends GET to /api/v1/control-sets with siteId query", async () => {
    mockRequestJson.mockResolvedValue([controlSetFixture]);

    const result = await listControlSets("plasmodb");

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/control-sets",
      {
        query: { siteId: "plasmodb" },
      },
    );
    expect(result).toEqual([controlSetFixture]);
  });

  it("returns empty array when no control sets exist", async () => {
    mockRequestJson.mockResolvedValue([]);

    const result = await listControlSets("toxodb");

    expect(result).toEqual([]);
  });

  it("returns multiple control sets", async () => {
    const second: ControlSet = {
      ...controlSetFixture,
      id: "cs-2",
      name: "Protease Controls",
    };
    mockRequestJson.mockResolvedValue([controlSetFixture, second]);

    const result = await listControlSets("plasmodb");

    expect(result).toHaveLength(2);
  });

  it("propagates errors", async () => {
    mockRequestJson.mockRejectedValue(new Error("Unauthorized"));

    await expect(listControlSets("plasmodb")).rejects.toThrow("Unauthorized");
  });
});

// ---------------------------------------------------------------------------
// getControlSet
// ---------------------------------------------------------------------------

describe("getControlSet", () => {
  it("sends GET to /api/v1/control-sets/:id", async () => {
    mockRequestJson.mockResolvedValue(controlSetFixture);

    const result = await getControlSet("cs-1");

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/control-sets/cs-1",
    );
    expect(result).toEqual(controlSetFixture);
  });

  it("returns control set with all fields", async () => {
    mockRequestJson.mockResolvedValue(controlSetFixture);

    const result = await getControlSet("cs-1");

    expect(result.positiveIds).toEqual(["PF3D7_0100100", "PF3D7_0200200"]);
    expect(result.negativeIds).toEqual(["PF3D7_0300300", "PF3D7_0400400"]);
    expect(result.source).toBe("curation");
    expect(result.tags).toEqual(["kinase", "validated"]);
  });

  it("propagates errors", async () => {
    mockRequestJson.mockRejectedValue(new Error("404 Not Found"));

    await expect(getControlSet("nonexistent")).rejects.toThrow("404 Not Found");
  });
});

// ---------------------------------------------------------------------------
// createControlSet
// ---------------------------------------------------------------------------

describe("createControlSet", () => {
  it("sends POST to /api/v1/control-sets with required fields", async () => {
    mockRequestJson.mockResolvedValue(controlSetFixture);

    const body = {
      name: "Kinase Controls",
      siteId: "plasmodb",
      recordType: "gene",
      positiveIds: ["PF3D7_0100100", "PF3D7_0200200"],
      negativeIds: ["PF3D7_0300300", "PF3D7_0400400"],
    };

    const result = await createControlSet(body);

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/control-sets",
      {
        method: "POST",
        body,
      },
    );
    expect(result).toEqual(controlSetFixture);
  });

  it("includes optional fields when provided", async () => {
    mockRequestJson.mockResolvedValue(controlSetFixture);

    const body = {
      name: "Full Controls",
      siteId: "toxodb",
      recordType: "gene",
      positiveIds: ["G1"],
      negativeIds: ["G2"],
      source: "paper",
      tags: ["paper", "validated"],
      provenanceNotes: "From Smith et al. 2025",
      isPublic: true,
    };

    await createControlSet(body);

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/control-sets",
      {
        method: "POST",
        body,
      },
    );
  });

  it("handles empty positive and negative ID lists", async () => {
    mockRequestJson.mockResolvedValue({
      ...controlSetFixture,
      positiveIds: [],
      negativeIds: [],
    });

    const body = {
      name: "Empty Controls",
      siteId: "plasmodb",
      recordType: "gene",
      positiveIds: [] as string[],
      negativeIds: [] as string[],
    };

    await createControlSet(body);

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/control-sets",
      {
        method: "POST",
        body: expect.objectContaining({
          positiveIds: [],
          negativeIds: [],
        }),
      },
    );
  });

  it("propagates errors", async () => {
    mockRequestJson.mockRejectedValue(new Error("Validation error"));

    await expect(
      createControlSet({
        name: "fail",
        siteId: "plasmodb",
        recordType: "gene",
        positiveIds: [],
        negativeIds: [],
      }),
    ).rejects.toThrow("Validation error");
  });
});

// ---------------------------------------------------------------------------
// deleteControlSet
// ---------------------------------------------------------------------------

describe("deleteControlSet", () => {
  it("sends DELETE to /api/v1/control-sets/:id", async () => {
    mockRequestVoid.mockResolvedValue(undefined);

    await deleteControlSet("cs-1");

    expect(mockRequestVoid).toHaveBeenCalledWith("/api/v1/control-sets/cs-1", {
      method: "DELETE",
    });
  });

  it("propagates errors on deletion failure", async () => {
    mockRequestVoid.mockRejectedValue(new Error("403 Forbidden"));

    await expect(deleteControlSet("cs-1")).rejects.toThrow("403 Forbidden");
  });
});

// ---------------------------------------------------------------------------
// getExperimentReport
// ---------------------------------------------------------------------------

describe("getExperimentReport", () => {
  let clickSpy: ReturnType<typeof vi.fn>;
  let createdUrls: string[];
  let revokedUrls: string[];

  beforeEach(() => {
    clickSpy = vi.fn();
    createdUrls = [];
    revokedUrls = [];

    vi.stubGlobal("URL", {
      createObjectURL: vi.fn((_blob: Blob) => {
        const url = `blob:mock-${createdUrls.length}`;
        createdUrls.push(url);
        return url;
      }),
      revokeObjectURL: vi.fn((url: string) => {
        revokedUrls.push(url);
      }),
    });

    vi.stubGlobal("document", {
      createElement: vi.fn(() => ({
        href: "",
        download: "",
        click: clickSpy,
      })),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("fetches a blob and triggers a download with correct filename", async () => {
    const mockBlob = new Blob(["<html>report</html>"], {
      type: "text/html",
    });
    mockRequestBlob.mockResolvedValue(mockBlob);

    await getExperimentReport("exp-1");

    expect(mockRequestBlob).toHaveBeenCalledWith("/api/v1/experiments/exp-1/export");
    expect(clickSpy).toHaveBeenCalledOnce();
    expect(createdUrls).toHaveLength(1);
    expect(revokedUrls).toHaveLength(1);
  });

  it("uses fixed filename experiment-report.html", async () => {
    const mockBlob = new Blob(["<html>report</html>"], {
      type: "text/html",
    });
    mockRequestBlob.mockResolvedValue(mockBlob);

    const el = { href: "", download: "", click: clickSpy };
    vi.mocked(document.createElement).mockReturnValue(el as unknown as HTMLElement);

    await getExperimentReport("exp-1");

    expect(el.download).toBe("experiment-report.html");
  });

  it("revokes the object URL after download", async () => {
    const mockBlob = new Blob(["content"], { type: "text/html" });
    mockRequestBlob.mockResolvedValue(mockBlob);

    await getExperimentReport("exp-1");

    expect(revokedUrls).toHaveLength(1);
    expect(revokedUrls[0]).toBe(createdUrls[0]);
  });

  it("propagates blob fetch errors", async () => {
    mockRequestBlob.mockRejectedValue(new Error("Network error"));

    await expect(getExperimentReport("exp-1")).rejects.toThrow("Network error");
  });
});
