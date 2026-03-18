import { beforeEach, describe, expect, it, vi } from "vitest";
import type { StrategyPlan } from "@pathfinder/shared";

vi.mock("./http", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./http")>();
  return {
    ...actual,
    requestJson: vi.fn(),
    requestJsonValidated: vi.fn(),
  };
});

import { requestJson, requestJsonValidated } from "./http";
import { APIError } from "./http";
import {
  listSites,
  getRecordTypes,
  getSearches,
  getParamSpecs,
  validateSearchParams,
} from "./sites";
import {
  listStrategies,
  syncWdkStrategies,
  openStrategy,
  getStrategy,
  createStrategy,
  updateStrategy,
  deleteStrategy,
  normalizePlan,
  computeStepCounts,
} from "./strategies";
import {
  getVeupathdbAuthStatus,
  loginVeupathdb,
  logoutVeupathdb,
} from "./veupathdb-auth";

const requestJsonMock = vi.mocked(requestJson);
const requestJsonValidatedMock = vi.mocked(requestJsonValidated);

describe("lib/api functions", () => {
  beforeEach(() => {
    requestJsonMock.mockReset();
    requestJsonValidatedMock.mockReset();
  });

  it("getStrategy fails fast on non-UUID ids", async () => {
    await expect(getStrategy("wdk:123")).rejects.toBeInstanceOf(APIError);
    await expect(getStrategy("wdk:123")).rejects.toMatchObject({
      status: 400,
      message: "Invalid strategy id.",
    });
  });

  it("getStrategy calls requestJsonValidated for UUID ids", async () => {
    requestJsonValidatedMock.mockResolvedValueOnce({ id: "x" });
    const id = "00000000-0000-4000-8000-000000000000";
    await getStrategy(id);
    expect(requestJsonValidatedMock).toHaveBeenCalledWith(
      expect.anything(),
      `/api/v1/strategies/${id}`,
    );
  });

  it("loginVeupathdb validates required inputs before making a request", async () => {
    await expect(loginVeupathdb("", "", "veupathdb")).rejects.toBeInstanceOf(Error);
    expect(requestJsonMock).not.toHaveBeenCalled();
  });

  it("listSites hits the sites endpoint", async () => {
    requestJsonValidatedMock.mockResolvedValueOnce([]);
    await listSites();
    expect(requestJsonValidatedMock).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/sites",
    );
  });

  it("getRecordTypes encodes the site id", async () => {
    requestJsonValidatedMock.mockResolvedValueOnce([]);
    await getRecordTypes("foo/bar");
    expect(requestJsonValidatedMock).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/sites/foo%2Fbar/record-types",
    );
  });

  it("getSearches only includes query when recordType is provided", async () => {
    requestJsonValidatedMock.mockResolvedValueOnce([]);
    await getSearches("plasmodb", null);
    expect(requestJsonValidatedMock).toHaveBeenLastCalledWith(
      expect.anything(),
      "/api/v1/sites/plasmodb/searches",
      {
        query: undefined,
      },
    );

    requestJsonValidatedMock.mockResolvedValueOnce([]);
    await getSearches("plasmodb", "gene");
    expect(requestJsonValidatedMock).toHaveBeenLastCalledWith(
      expect.anything(),
      "/api/v1/sites/plasmodb/searches",
      {
        query: { recordType: "gene" },
      },
    );
  });

  it("getParamSpecs uses POST body with contextValues and encodes url parts", async () => {
    requestJsonValidatedMock.mockResolvedValueOnce([]);
    await getParamSpecs("site 1", "gene/type", "my search", { a: 1 });
    expect(requestJsonValidatedMock).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/sites/site%201/searches/gene%2Ftype/my%20search/param-specs",
      { method: "POST", body: { contextValues: { a: 1 } } },
    );
  });

  it("validateSearchParams uses POST body with contextValues", async () => {
    requestJsonValidatedMock.mockResolvedValueOnce({ valid: true });
    await validateSearchParams("plasmodb", "gene", "search", { x: "y" });
    expect(requestJsonValidatedMock).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/sites/plasmodb/searches/gene/search/validate",
      { method: "POST", body: { contextValues: { x: "y" } } },
    );
  });

  it("listStrategies includes siteId query when provided", async () => {
    requestJsonValidatedMock.mockResolvedValueOnce([]);
    await listStrategies("plasmodb");
    expect(requestJsonValidatedMock).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/strategies",
      { query: { siteId: "plasmodb" } },
    );
  });

  it("openStrategy POSTs payload", async () => {
    requestJsonValidatedMock.mockResolvedValueOnce({ strategyId: "x" });
    await openStrategy({ siteId: "plasmodb", wdkStrategyId: 123 });
    expect(requestJsonValidatedMock).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/strategies/open",
      { method: "POST", body: { siteId: "plasmodb", wdkStrategyId: 123 } },
    );
  });

  it("create/update/delete strategy use correct methods", async () => {
    const plan: StrategyPlan = {
      recordType: "gene",
      root: { searchName: "s", id: "n1", displayName: "d", parameters: {} },
      metadata: { name: "x" },
    };
    requestJsonValidatedMock.mockResolvedValueOnce({ id: "s1" });
    await createStrategy({ name: "N", siteId: "plasmodb", plan });
    expect(requestJsonValidatedMock).toHaveBeenLastCalledWith(
      expect.anything(),
      "/api/v1/strategies",
      { method: "POST", body: { name: "N", siteId: "plasmodb", plan } },
    );

    requestJsonValidatedMock.mockResolvedValueOnce({ id: "s1" });
    await updateStrategy("s1", { name: "N2" });
    expect(requestJsonValidatedMock).toHaveBeenLastCalledWith(
      expect.anything(),
      "/api/v1/strategies/s1",
      { method: "PATCH", body: { name: "N2" } },
    );

    requestJsonMock.mockResolvedValueOnce(undefined);
    await deleteStrategy("s1");
    expect(requestJsonMock).toHaveBeenLastCalledWith("/api/v1/strategies/s1", {
      method: "DELETE",
    });
  });

  it("normalizePlan and computeStepCounts POST expected payloads", async () => {
    const plan: StrategyPlan = {
      recordType: "gene",
      root: { searchName: "s", id: "n1", displayName: "d", parameters: {} },
      metadata: { name: "x" },
    };
    requestJsonValidatedMock.mockResolvedValueOnce({ plan });
    await normalizePlan("plasmodb", plan);
    expect(requestJsonValidatedMock).toHaveBeenLastCalledWith(
      expect.anything(),
      "/api/v1/strategies/plan/normalize",
      { method: "POST", body: { siteId: "plasmodb", plan } },
    );

    requestJsonValidatedMock.mockResolvedValueOnce({ counts: {} });
    await computeStepCounts("plasmodb", plan);
    expect(requestJsonValidatedMock).toHaveBeenLastCalledWith(
      expect.anything(),
      "/api/v1/strategies/step-counts",
      { method: "POST", body: { siteId: "plasmodb", plan } },
    );
  });

  it("syncWdkStrategies calls the batch sync endpoint", async () => {
    requestJsonValidatedMock.mockResolvedValueOnce([]);
    await syncWdkStrategies("plasmodb");
    expect(requestJsonValidatedMock).toHaveBeenLastCalledWith(
      expect.anything(),
      "/api/v1/strategies/sync-wdk",
      { method: "POST", query: { siteId: "plasmodb" } },
    );
  });

  it("auth bridge endpoints forward the provided siteId", async () => {
    requestJsonValidatedMock.mockResolvedValueOnce({
      signedIn: false,
      name: null,
      email: null,
    });
    await getVeupathdbAuthStatus("plasmodb");
    expect(requestJsonValidatedMock).toHaveBeenLastCalledWith(
      expect.anything(),
      "/api/v1/veupathdb/auth/status",
      { query: { siteId: "plasmodb" } },
    );

    requestJsonValidatedMock.mockResolvedValueOnce({ success: true });
    await loginVeupathdb("a@b.com", "pw", "plasmodb");
    expect(requestJsonValidatedMock).toHaveBeenLastCalledWith(
      expect.anything(),
      "/api/v1/veupathdb/auth/login",
      {
        method: "POST",
        query: { siteId: "plasmodb" },
        body: { email: "a@b.com", password: "pw" },
      },
    );

    requestJsonValidatedMock.mockResolvedValueOnce({ success: true });
    await logoutVeupathdb("plasmodb");
    expect(requestJsonValidatedMock).toHaveBeenLastCalledWith(
      expect.anything(),
      "/api/v1/veupathdb/auth/logout",
      { method: "POST", query: { siteId: "plasmodb" } },
    );
  });
});
