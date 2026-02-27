import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./http", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./http")>();
  return {
    ...actual,
    requestJson: vi.fn(),
  };
});

import { requestJson } from "./http";
import {
  APIError,
  computeStepCounts,
  createStrategy,
  deletePlanSession,
  deleteStrategy,
  getParamSpecs,
  getPlanSession,
  getRecordTypes,
  getSearches,
  getStrategy,
  getVeupathdbAuthStatus,
  listPlans,
  listSites,
  listStrategies,
  loginVeupathdb,
  logoutVeupathdb,
  normalizePlan,
  openPlanSession,
  openStrategy,
  syncWdkStrategies,
  updatePlanSession,
  updateStrategy,
  validateSearchParams,
} from "./client";

const requestJsonMock = vi.mocked(requestJson);

describe("lib/api/client", () => {
  beforeEach(() => {
    requestJsonMock.mockReset();
  });

  it("getStrategy fails fast on non-UUID ids", async () => {
    await expect(getStrategy("wdk:123")).rejects.toBeInstanceOf(APIError);
    await expect(getStrategy("wdk:123")).rejects.toMatchObject({
      status: 400,
      message: "Invalid strategy id.",
    });
  });

  it("getStrategy calls requestJson for UUID ids", async () => {
    requestJsonMock.mockResolvedValueOnce({ id: "x" } as any);
    const id = "00000000-0000-4000-8000-000000000000";
    await getStrategy(id);
    expect(requestJsonMock).toHaveBeenCalledWith(`/api/v1/strategies/${id}`);
  });

  it("loginVeupathdb validates required inputs before making a request", async () => {
    await expect(loginVeupathdb("", "")).rejects.toBeInstanceOf(Error);
    expect(requestJsonMock).not.toHaveBeenCalled();
  });

  it("listSites hits the sites endpoint", async () => {
    requestJsonMock.mockResolvedValueOnce([]);
    await listSites();
    expect(requestJsonMock).toHaveBeenCalledWith("/api/v1/sites");
  });

  it("getRecordTypes encodes the site id", async () => {
    requestJsonMock.mockResolvedValueOnce([]);
    await getRecordTypes("foo/bar");
    expect(requestJsonMock).toHaveBeenCalledWith(
      "/api/v1/sites/foo%2Fbar/record-types",
    );
  });

  it("getSearches only includes query when recordType is provided", async () => {
    requestJsonMock.mockResolvedValueOnce([]);
    await getSearches("plasmodb", null);
    expect(requestJsonMock).toHaveBeenLastCalledWith(
      "/api/v1/sites/plasmodb/searches",
      {
        query: undefined,
      },
    );

    requestJsonMock.mockResolvedValueOnce([]);
    await getSearches("plasmodb", "gene");
    expect(requestJsonMock).toHaveBeenLastCalledWith(
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
      "/api/v1/sites/site%201/searches/gene%2Ftype/my%20search/param-specs",
      { method: "POST", body: { contextValues: { a: 1 } } },
    );
  });

  it("validateSearchParams uses POST body with contextValues", async () => {
    requestJsonMock.mockResolvedValueOnce({ valid: true } as any);
    await validateSearchParams("plasmodb", "gene", "search", { x: "y" });
    expect(requestJsonMock).toHaveBeenCalledWith(
      "/api/v1/sites/plasmodb/searches/gene/search/validate",
      { method: "POST", body: { contextValues: { x: "y" } } },
    );
  });

  it("listStrategies includes siteId query when provided", async () => {
    requestJsonMock.mockResolvedValueOnce([]);
    await listStrategies("plasmodb");
    expect(requestJsonMock).toHaveBeenCalledWith("/api/v1/strategies", {
      query: { siteId: "plasmodb" },
    });
  });

  it("openStrategy POSTs payload", async () => {
    requestJsonMock.mockResolvedValueOnce({ strategyId: "x" });
    await openStrategy({ siteId: "plasmodb", wdkStrategyId: 123 });
    expect(requestJsonMock).toHaveBeenCalledWith("/api/v1/strategies/open", {
      method: "POST",
      body: { siteId: "plasmodb", wdkStrategyId: 123 },
    });
  });

  it("create/update/delete strategy use correct methods", async () => {
    const plan = {
      recordType: "gene",
      root: { id: "n1", searchName: "s", displayName: "d", parameters: {} },
      metadata: { name: "x" },
    } as any;
    requestJsonMock.mockResolvedValueOnce({ id: "s1" } as any);
    await createStrategy({ name: "N", siteId: "plasmodb", plan });
    expect(requestJsonMock).toHaveBeenLastCalledWith("/api/v1/strategies", {
      method: "POST",
      body: { name: "N", siteId: "plasmodb", plan },
    });

    requestJsonMock.mockResolvedValueOnce({ id: "s1" } as any);
    await updateStrategy("s1", { name: "N2" });
    expect(requestJsonMock).toHaveBeenLastCalledWith("/api/v1/strategies/s1", {
      method: "PATCH",
      body: { name: "N2" },
    });

    requestJsonMock.mockResolvedValueOnce(undefined as any);
    await deleteStrategy("s1");
    expect(requestJsonMock).toHaveBeenLastCalledWith("/api/v1/strategies/s1", {
      method: "DELETE",
    });
  });

  it("normalizePlan and computeStepCounts POST expected payloads", async () => {
    const plan = {
      recordType: "gene",
      root: { id: "n1", searchName: "s", displayName: "d", parameters: {} },
      metadata: { name: "x" },
    } as any;
    requestJsonMock.mockResolvedValueOnce({ plan });
    await normalizePlan("plasmodb", plan);
    expect(requestJsonMock).toHaveBeenLastCalledWith(
      "/api/v1/strategies/plan/normalize",
      {
        method: "POST",
        body: { siteId: "plasmodb", plan },
      },
    );

    requestJsonMock.mockResolvedValueOnce({ counts: {} });
    await computeStepCounts("plasmodb", plan);
    expect(requestJsonMock).toHaveBeenLastCalledWith("/api/v1/strategies/step-counts", {
      method: "POST",
      body: { siteId: "plasmodb", plan },
    });
  });

  it("syncWdkStrategies calls the batch sync endpoint", async () => {
    requestJsonMock.mockResolvedValueOnce([]);
    await syncWdkStrategies("plasmodb");
    expect(requestJsonMock).toHaveBeenLastCalledWith("/api/v1/strategies/sync-wdk", {
      method: "POST",
      query: { siteId: "plasmodb" },
    });
  });

  it("plan session endpoints use expected methods", async () => {
    requestJsonMock.mockResolvedValueOnce([]);
    await listPlans("plasmodb");
    expect(requestJsonMock).toHaveBeenLastCalledWith("/api/v1/plans", {
      query: { siteId: "plasmodb" },
    });

    requestJsonMock.mockResolvedValueOnce({ planSessionId: "p1" });
    await openPlanSession({ siteId: "plasmodb", title: "T" });
    expect(requestJsonMock).toHaveBeenLastCalledWith("/api/v1/plans/open", {
      method: "POST",
      body: { siteId: "plasmodb", title: "T" },
    });

    requestJsonMock.mockResolvedValueOnce({ id: "p1" } as any);
    await getPlanSession("p1");
    expect(requestJsonMock).toHaveBeenLastCalledWith("/api/v1/plans/p1");

    requestJsonMock.mockResolvedValueOnce({ planSessionId: "p1" } as any);
    await updatePlanSession("p1", { title: "New" });
    expect(requestJsonMock).toHaveBeenLastCalledWith("/api/v1/plans/p1", {
      method: "PATCH",
      body: { title: "New" },
    });

    requestJsonMock.mockResolvedValueOnce({ success: true } as any);
    await deletePlanSession("p1");
    expect(requestJsonMock).toHaveBeenLastCalledWith("/api/v1/plans/p1", {
      method: "DELETE",
    });
  });

  it("auth bridge endpoints always use veupathdb portal site ID", async () => {
    requestJsonMock.mockResolvedValueOnce({
      signedIn: false,
      name: null,
      email: null,
    } as any);
    await getVeupathdbAuthStatus();
    expect(requestJsonMock).toHaveBeenLastCalledWith("/api/v1/veupathdb/auth/status", {
      query: { siteId: "veupathdb" },
    });

    requestJsonMock.mockResolvedValueOnce({ success: true } as any);
    await loginVeupathdb("a@b.com", "pw");
    expect(requestJsonMock).toHaveBeenLastCalledWith("/api/v1/veupathdb/auth/login", {
      method: "POST",
      query: { siteId: "veupathdb" },
      body: { email: "a@b.com", password: "pw" },
    });

    requestJsonMock.mockResolvedValueOnce({ success: true } as any);
    await logoutVeupathdb();
    expect(requestJsonMock).toHaveBeenLastCalledWith("/api/v1/veupathdb/auth/logout", {
      method: "POST",
    });
  });
});
