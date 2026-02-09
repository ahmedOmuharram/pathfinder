import { describe, expect, it } from "vitest";
import { APIError } from "@/lib/api/client";
import { classifyOpenStrategyError } from "@/features/sidebar/utils/openError";

describe("classifyOpenStrategyError", () => {
  it("classifies 403 for WDK open", () => {
    const err = new APIError("Forbidden", {
      status: 403,
      statusText: "Forbidden",
      url: "x",
      data: { detail: "forbidden" },
    });
    const res = classifyOpenStrategyError({ err, payload: { wdkStrategyId: 1 } });
    expect(res.refresh).toBe(true);
    expect(res.message).toMatch(/Sign in/);
  });

  it("classifies 403 for local strategy session mismatch", () => {
    const err = new APIError("Forbidden", {
      status: 403,
      statusText: "Forbidden",
      url: "x",
      data: { detail: "forbidden" },
    });
    const res = classifyOpenStrategyError({ err, payload: { strategyId: "s1" } });
    expect(res.refresh).toBe(true);
    expect(res.removeStrategyId).toBe("s1");
  });

  it("returns generic disposition for non-403", () => {
    const err = new APIError("Bad", {
      status: 400,
      statusText: "Bad",
      url: "x",
      data: { detail: "bad" },
    });
    const res = classifyOpenStrategyError({ err, payload: {} });
    expect(res.refresh).toBe(false);
    expect(res.message).toBe("Failed to open strategy.");
  });
});
