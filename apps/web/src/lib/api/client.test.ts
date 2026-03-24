import { beforeEach, describe, expect, it, vi } from "vitest";
import type { StrategyPlan } from "@pathfinder/shared";

vi.mock("./http", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    requestJson: vi.fn(),
    requestVoid: vi.fn(),
  };
});

import { requestJson, requestVoid } from "./http";
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
const requestVoidMock = vi.mocked(requestVoid);

describe("lib/api functions", () => {
  beforeEach(() => {
    requestJsonMock.mockReset();
    requestVoidMock.mockReset();
  });

  it("getStrategy fails fast on non-UUID ids", async () => {
    await expect(getStrategy("wdk:123")).rejects.toBeInstanceOf(APIError);
    await expect(getStrategy("wdk:123")).rejects.toMatchObject({
      status: 400,
      message: "Invalid strategy id.",
    });
  });

  it("getStrategy calls requestJson for UUID ids", async () => {
    requestJsonMock.mockResolvedValueOnce({ id: "x" });
    const id = "00000000-0000-4000-8000-000000000000";
    await getStrategy(id);
    expect(requestJsonMock).toHaveBeenCalledWith(
      expect.anything(),
      `/api/v1/strategies/${id}`,
    );
  });

  it("loginVeupathdb validates required inputs before making a request", async () => {
    await expect(loginVeupathdb("", "", "veupathdb")).rejects.toBeInstanceOf(Error);
    expect(requestJsonMock).not.toHaveBeenCalled();
  });

  it("listSites hits the sites endpoint", async () => {
    requestJsonMock.mockResolvedValueOnce([]);
    await listSites();
    expect(requestJsonMock).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/sites",
    );
  });

  it("getRecordTypes encodes the site id", async () => {
    requestJsonMock.mockResolvedValueOnce([]);
    await getRecordTypes("foo/bar");
    expect(requestJsonMock).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/sites/foo%2Fbar/record-types",
    );
  });

  it("getSearches only includes query when recordType is provided", async () => {
    requestJsonMock.mockResolvedValueOnce([]);
    await getSearches("plasmodb", null);
    expect(requestJsonMock).toHaveBeenLastCalledWith(
      expect.anything(),
      "/api/v1/sites/plasmodb/searches",
      {},
    );

    requestJsonMock.mockResolvedValueOnce([]);
    await getSearches("plasmodb", "gene");
    expect(requestJsonMock).toHaveBeenLastCalledWith(
      expect.anything(),
      "/api/v1/sites/plasmodb/searches",
      {
        query: { recordType: "gene" },
      },
    );
  });

  it("getParamSpecs uses POST body with contextValues and encodes url parts", async () => {
    requestJsonMock.mockResolvedValueOnce([]);
    await getParamSpecs("site 1", "gene/type", "my search", { a: 1 });
    expect(requestJsonMock).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/sites/site%201/searches/gene%2Ftype/my%20search/param-specs",
      { method: "POST", body: { contextValues: { a: 1 } } },
    );
  });

  it("validateSearchParams uses POST body with contextValues", async () => {
    requestJsonMock.mockResolvedValueOnce({ valid: true });
    await validateSearchParams("plasmodb", "gene", "search", { x: "y" });
    expect(requestJsonMock).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/sites/plasmodb/searches/gene/search/validate",
      { method: "POST", body: { contextValues: { x: "y" } } },
    );
  });

  it("listStrategies includes siteId query when provided", async () => {
    requestJsonMock.mockResolvedValueOnce([]);
    await listStrategies("plasmodb");
    expect(requestJsonMock).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/strategies",
      { query: { siteId: "plasmodb" } },
    );
  });

  it("openStrategy POSTs payload", async () => {
    requestJsonMock.mockResolvedValueOnce({ strategyId: "x" });
    await openStrategy({ siteId: "plasmodb", wdkStrategyId: 123 });
    expect(requestJsonMock).toHaveBeenCalledWith(
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
    requestJsonMock.mockResolvedValueOnce({ id: "s1" });
    await createStrategy({ name: "N", siteId: "plasmodb", plan });
    expect(requestJsonMock).toHaveBeenLastCalledWith(
      expect.anything(),
      "/api/v1/strategies",
      { method: "POST", body: { name: "N", siteId: "plasmodb", plan } },
    );

    requestJsonMock.mockResolvedValueOnce({ id: "s1" });
    await updateStrategy("s1", { name: "N2" });
    expect(requestJsonMock).toHaveBeenLastCalledWith(
      expect.anything(),
      "/api/v1/strategies/s1",
      { method: "PATCH", body: { name: "N2" } },
    );

    requestVoidMock.mockResolvedValueOnce(undefined);
    await deleteStrategy("s1");
    expect(requestVoidMock).toHaveBeenLastCalledWith("/api/v1/strategies/s1", {
      method: "DELETE",
    });
  });

  it("normalizePlan and computeStepCounts POST expected payloads", async () => {
    const plan: StrategyPlan = {
      recordType: "gene",
      root: { searchName: "s", id: "n1", displayName: "d", parameters: {} },
      metadata: { name: "x" },
    };
    requestJsonMock.mockResolvedValueOnce({ plan });
    await normalizePlan("plasmodb", plan);
    expect(requestJsonMock).toHaveBeenLastCalledWith(
      expect.anything(),
      "/api/v1/strategies/plan/normalize",
      { method: "POST", body: { siteId: "plasmodb", plan } },
    );

    requestJsonMock.mockResolvedValueOnce({ counts: {} });
    await computeStepCounts("plasmodb", plan);
    expect(requestJsonMock).toHaveBeenLastCalledWith(
      expect.anything(),
      "/api/v1/strategies/step-counts",
      { method: "POST", body: { siteId: "plasmodb", plan } },
    );
  });

  it("syncWdkStrategies calls the batch sync endpoint", async () => {
    requestJsonMock.mockResolvedValueOnce([]);
    await syncWdkStrategies("plasmodb");
    expect(requestJsonMock).toHaveBeenLastCalledWith(
      expect.anything(),
      "/api/v1/strategies/sync-wdk",
      { method: "POST", query: { siteId: "plasmodb" } },
    );
  });

  it("auth bridge endpoints forward the provided siteId", async () => {
    requestJsonMock.mockResolvedValueOnce({
      signedIn: false,
      name: null,
      email: null,
    });
    await getVeupathdbAuthStatus("plasmodb");
    expect(requestJsonMock).toHaveBeenLastCalledWith(
      expect.anything(),
      "/api/v1/veupathdb/auth/status",
      { query: { siteId: "plasmodb" } },
    );

    requestJsonMock.mockResolvedValueOnce({ success: true });
    await loginVeupathdb("a@b.com", "pw", "plasmodb");
    expect(requestJsonMock).toHaveBeenLastCalledWith(
      expect.anything(),
      "/api/v1/veupathdb/auth/login",
      {
        method: "POST",
        query: { siteId: "plasmodb" },
        body: { email: "a@b.com", password: "pw" },
      },
    );

    requestJsonMock.mockResolvedValueOnce({ success: true });
    await logoutVeupathdb("plasmodb");
    expect(requestJsonMock).toHaveBeenLastCalledWith(
      expect.anything(),
      "/api/v1/veupathdb/auth/logout",
      { method: "POST", query: { siteId: "plasmodb" } },
    );
  });
});
