import { describe, expect, it } from "vitest";
import { APIError } from "./http";
import { isProblemDetail, toUserMessage, wdkLoginRequiredDetail } from "./errors";

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

const LOGIN_REQUIRED_BODY = {
  type: "about:blank",
  title: "VEuPathDB login required",
  status: 401,
  detail: "Sign in to VEuPathDB to use searches, strategies and gene sets.",
  code: "WDK_LOGIN_REQUIRED",
};

describe("wdkLoginRequiredDetail", () => {
  it("returns the server detail for a 401 APIError carrying the code", () => {
    const err = new APIError(LOGIN_REQUIRED_BODY.detail, {
      status: 401,
      statusText: "Unauthorized",
      url: "http://localhost:3000/api/v1/conversations/c1/begin",
      data: LOGIN_REQUIRED_BODY,
    });
    expect(wdkLoginRequiredDetail(err)).toBe(
      "Sign in to VEuPathDB to use searches, strategies and gene sets.",
    );
  });

  it("returns the server detail when the chat transport rethrows the body as text", () => {
    const err = new Error(JSON.stringify(LOGIN_REQUIRED_BODY));
    expect(wdkLoginRequiredDetail(err)).toBe(
      "Sign in to VEuPathDB to use searches, strategies and gene sets.",
    );
  });

  it("ignores a 401 that carries another code", () => {
    const err = new APIError("Unauthorized", {
      status: 401,
      statusText: "Unauthorized",
      url: "/x",
      data: { title: "Unauthorized", status: 401, detail: "no", code: "UNAUTHORIZED" },
    });
    expect(wdkLoginRequiredDetail(err)).toBeNull();
  });

  it("ignores non-401 errors, plain text errors and non-errors", () => {
    const wrongStatus = new APIError("nope", {
      status: 403,
      statusText: "Forbidden",
      url: "/x",
      data: LOGIN_REQUIRED_BODY,
    });
    expect(wdkLoginRequiredDetail(wrongStatus)).toBeNull();
    expect(wdkLoginRequiredDetail(new Error("Failed to fetch"))).toBeNull();
    expect(wdkLoginRequiredDetail(null)).toBeNull();
    expect(wdkLoginRequiredDetail("WDK_LOGIN_REQUIRED")).toBeNull();
  });
});
