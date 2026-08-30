import { describe, expect, it } from "vitest";
import { APIError } from "./http";
import { isProblemDetail, toUserMessage, wdkAuthRefusal } from "./errors";

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

const IDENTITY_MISMATCH_BODY = {
  type: "about:blank",
  title: "VEuPathDB account changed",
  status: 401,
  detail:
    "Signed in to VEuPathDB as a different account than this PathFinder session. Sign in again.",
  code: "WDK_IDENTITY_MISMATCH",
};

describe("wdkAuthRefusal", () => {
  it("names the code and detail for a 401 APIError that wants a login", () => {
    const err = new APIError(LOGIN_REQUIRED_BODY.detail, {
      status: 401,
      statusText: "Unauthorized",
      url: "http://localhost:3000/api/v1/conversations/c1/begin",
      data: LOGIN_REQUIRED_BODY,
    });
    expect(wdkAuthRefusal(err)).toEqual({
      code: "WDK_LOGIN_REQUIRED",
      detail: "Sign in to VEuPathDB to use searches, strategies and gene sets.",
    });
  });

  it("names the code and detail for a 401 that reports a second account", () => {
    const err = new APIError(IDENTITY_MISMATCH_BODY.detail, {
      status: 401,
      statusText: "Unauthorized",
      url: "http://localhost:3000/api/v1/eda/viz",
      data: IDENTITY_MISMATCH_BODY,
    });
    expect(wdkAuthRefusal(err)).toEqual({
      code: "WDK_IDENTITY_MISMATCH",
      detail: IDENTITY_MISMATCH_BODY.detail,
    });
  });

  it("reads the body when the chat transport rethrows it as text", () => {
    const err = new Error(JSON.stringify(LOGIN_REQUIRED_BODY));
    expect(wdkAuthRefusal(err)).toEqual({
      code: "WDK_LOGIN_REQUIRED",
      detail: "Sign in to VEuPathDB to use searches, strategies and gene sets.",
    });
  });

  it("ignores a 401 that carries another code", () => {
    const err = new APIError("Unauthorized", {
      status: 401,
      statusText: "Unauthorized",
      url: "/x",
      data: { title: "Unauthorized", status: 401, detail: "no", code: "UNAUTHORIZED" },
    });
    expect(wdkAuthRefusal(err)).toBeNull();
  });

  it("ignores non-401 errors, plain text errors and non-errors", () => {
    const wrongStatus = new APIError("nope", {
      status: 403,
      statusText: "Forbidden",
      url: "/x",
      data: LOGIN_REQUIRED_BODY,
    });
    expect(wdkAuthRefusal(wrongStatus)).toBeNull();
    expect(wdkAuthRefusal(new Error("Failed to fetch"))).toBeNull();
    expect(wdkAuthRefusal(null)).toBeNull();
    expect(wdkAuthRefusal("WDK_LOGIN_REQUIRED")).toBeNull();
  });
});
