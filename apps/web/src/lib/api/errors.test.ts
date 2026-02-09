import { describe, expect, it } from "vitest";
import { APIError } from "./http";
import { isProblemDetail, toUserMessage } from "./errors";

describe("lib/api/errors", () => {
  it("detects FastAPI-style problem detail objects", () => {
    expect(isProblemDetail({ title: "Bad Request", status: 400, detail: "nope" })).toBe(
      true,
    );
    expect(isProblemDetail({ title: "x", status: "400", detail: "nope" })).toBe(false);
    expect(isProblemDetail(null)).toBe(false);
  });

  it("formats APIError messages using problem detail when present", () => {
    const err = new APIError("fallback", {
      status: 422,
      statusText: "Unprocessable Entity",
      url: "http://localhost:8000/api",
      data: { title: "Validation Error", status: 422, detail: "Invalid input" },
    });
    expect(toUserMessage(err, "Request failed.")).toBe("Invalid input");
  });

  it("falls back to APIError.message when not problem+json", () => {
    const err = new APIError("HTTP 500", {
      status: 500,
      statusText: "Internal Server Error",
      url: "http://localhost:8000/api",
      data: { detail: "Something broke" },
    });
    expect(toUserMessage(err, "Request failed.")).toBe("Something broke");
  });

  it("formats unknown errors safely", () => {
    expect(toUserMessage(new Error("Boom"), "Request failed.")).toBe("Boom");
    expect(toUserMessage("string error", "Request failed.")).toBe("string error");
    expect(toUserMessage(null, "Request failed.")).toBe("Request failed.");
  });
});
