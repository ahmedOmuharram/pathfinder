// @vitest-environment jsdom
import type { Attributes } from "@opentelemetry/api";
import { beforeEach, describe, expect, it, vi } from "vitest";

const setStatus = vi.fn();
const recordException = vi.fn();
const endSpan = vi.fn();
const startSpan = vi.fn((_name: string, _options: { attributes: Attributes }) => ({
  setStatus,
  recordException,
  end: endSpan,
}));

vi.mock("@opentelemetry/api", () => ({
  trace: { getTracer: () => ({ startSpan }) },
  SpanStatusCode: { ERROR: 2 },
}));

import { logError } from "./logError";

function lastAttributes(): Attributes {
  const call = startSpan.mock.calls[0];
  if (call === undefined) throw new Error("startSpan was not called");
  return call[1].attributes;
}

function lastRecordedMessage(): string {
  const recorded = recordException.mock.calls[0]?.[0] as Error;
  return recorded.message;
}

describe("logError", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("records the exception on a client.error span and ends it", () => {
    logError(new Error("kaboom"), { source: "app" });
    expect(startSpan).toHaveBeenCalledWith("client.error", expect.any(Object));
    expect(setStatus).toHaveBeenCalledWith(
      expect.objectContaining({ message: "kaboom" }),
    );
    expect(recordException).toHaveBeenCalledTimes(1);
    expect(endSpan).toHaveBeenCalledTimes(1);
  });

  it("tags source, route, component and extra context", () => {
    logError(new Error("x"), {
      source: "react.errorBoundary",
      route: "/strategy",
      component: "Graph",
      extra: { tab: "graph", count: 3 },
    });
    const attrs = lastAttributes();
    expect(attrs["error.source"]).toBe("react.errorBoundary");
    expect(attrs["client.route"]).toBe("/strategy");
    expect(attrs["client.component"]).toBe("Graph");
    expect(attrs["client.tab"]).toBe("graph");
    expect(attrs["client.count"]).toBe(3);
  });

  it("coerces a string error and scrubs bearer tokens", () => {
    logError("auth failed: Bearer abc.def.ghi leaked", { source: "app" });
    const message = lastRecordedMessage();
    expect(message).toContain("Bearer <redacted>");
    expect(message).not.toContain("abc.def.ghi");
  });

  it("scrubs api_key query params from coerced messages", () => {
    logError("GET /x?api_key=SECRET123&y=1 failed", { source: "app" });
    const message = lastRecordedMessage();
    expect(message).toContain("api_key=<redacted>");
    expect(message).not.toContain("SECRET123");
  });

  it("coerces a non-serializable value without throwing", () => {
    const circular: Record<string, unknown> = {};
    circular["self"] = circular;
    logError(circular, { source: "app" });
    expect(lastRecordedMessage()).toBe("non-serializable error");
  });
});
