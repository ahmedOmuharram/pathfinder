/**
 * @vitest-environment jsdom
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";
import { z } from "zod";

import { APIError, requestJson } from "@/lib/api/http";
import {
  WDK_LOGIN_REQUIRED_TOAST_ID,
  handleWdkLoginRequired,
  requiresFullScreenSignIn,
  useAuthGateStore,
} from "./useAuthGateStore";

vi.mock("sonner", () => ({ toast: { error: vi.fn() } }));

const LOGIN_REQUIRED_BODY = {
  type: "about:blank",
  title: "VEuPathDB login required",
  status: 401,
  detail: "Sign in to VEuPathDB to use searches, strategies and gene sets.",
  code: "WDK_LOGIN_REQUIRED",
};

beforeEach(() => {
  useAuthGateStore.getState().dismissSignIn();
  vi.mocked(toast.error).mockClear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useAuthGateStore", () => {
  it("starts closed", () => {
    expect(useAuthGateStore.getState().signInRequired).toBe(false);
    expect(useAuthGateStore.getState().signInReason).toBeNull();
  });

  it("opens without a reason when the user asks to sign in", () => {
    useAuthGateStore.getState().requestSignIn();
    expect(useAuthGateStore.getState().signInRequired).toBe(true);
    expect(useAuthGateStore.getState().signInReason).toBeNull();
  });

  it("keeps the reason the server gave and clears it on dismiss", () => {
    useAuthGateStore.getState().requestSignIn(LOGIN_REQUIRED_BODY.detail);
    expect(useAuthGateStore.getState().signInReason).toBe(LOGIN_REQUIRED_BODY.detail);
    useAuthGateStore.getState().dismissSignIn();
    expect(useAuthGateStore.getState().signInRequired).toBe(false);
    expect(useAuthGateStore.getState().signInReason).toBeNull();
  });

  it("does not replace the state when the same request repeats", () => {
    useAuthGateStore.getState().requestSignIn(LOGIN_REQUIRED_BODY.detail);
    const first = useAuthGateStore.getState();
    useAuthGateStore.getState().requestSignIn(LOGIN_REQUIRED_BODY.detail);
    expect(useAuthGateStore.getState()).toBe(first);
  });
});

describe("handleWdkLoginRequired", () => {
  it("opens the sign-in prompt and reports the server detail once", () => {
    const err = new APIError(LOGIN_REQUIRED_BODY.detail, {
      status: 401,
      statusText: "Unauthorized",
      url: "/api/v1/conversations/c1/begin",
      data: LOGIN_REQUIRED_BODY,
    });
    expect(handleWdkLoginRequired(err)).toBe(true);
    expect(vi.mocked(toast.error)).toHaveBeenCalledWith(
      "Sign in to VEuPathDB to use searches, strategies and gene sets.",
      { id: WDK_LOGIN_REQUIRED_TOAST_ID },
    );
    expect(useAuthGateStore.getState().signInRequired).toBe(true);
    expect(useAuthGateStore.getState().signInReason).toBe(LOGIN_REQUIRED_BODY.detail);
  });

  it("reuses one toast id so concurrent refusals do not stack", () => {
    const err = new APIError(LOGIN_REQUIRED_BODY.detail, {
      status: 401,
      statusText: "Unauthorized",
      url: "/api/v1/gene-sets",
      data: LOGIN_REQUIRED_BODY,
    });
    handleWdkLoginRequired(err);
    handleWdkLoginRequired(err);
    expect(vi.mocked(toast.error).mock.calls.map((call) => call[1])).toEqual([
      { id: WDK_LOGIN_REQUIRED_TOAST_ID },
      { id: WDK_LOGIN_REQUIRED_TOAST_ID },
    ]);
  });

  it("leaves other errors to their own handler", () => {
    const err = new APIError("Conversation not found", {
      status: 404,
      statusText: "Not Found",
      url: "/x",
      data: { title: "Not found", status: 404, detail: "gone", code: "NOT_FOUND" },
    });
    expect(handleWdkLoginRequired(err)).toBe(false);
    expect(vi.mocked(toast.error)).not.toHaveBeenCalled();
    expect(useAuthGateStore.getState().signInRequired).toBe(false);
  });

  it("routes a real 401 problem+json response from the API layer", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Response(JSON.stringify(LOGIN_REQUIRED_BODY), {
            status: 401,
            statusText: "Unauthorized",
            headers: { "content-type": "application/problem+json" },
          }),
      ),
    );

    const thrown = await requestJson(z.object({}), "/api/v1/conversations/c1/begin", {
      method: "POST",
      body: { siteId: "plasmodb" },
    }).catch((err: unknown) => err);

    expect(handleWdkLoginRequired(thrown)).toBe(true);
    expect(vi.mocked(toast.error)).toHaveBeenCalledWith(
      "Sign in to VEuPathDB to use searches, strategies and gene sets.",
      { id: WDK_LOGIN_REQUIRED_TOAST_ID },
    );
    expect(useAuthGateStore.getState().signInRequired).toBe(true);
  });
});

describe("requiresFullScreenSignIn", () => {
  it("blocks a standalone session that has no VEuPathDB login", () => {
    expect(requiresFullScreenSignIn({ embedded: false, signedIn: false })).toBe(true);
  });

  it("lets an embedded session render so the composer can carry the prompt", () => {
    expect(requiresFullScreenSignIn({ embedded: true, signedIn: false })).toBe(false);
  });

  it("never blocks a signed-in session", () => {
    expect(requiresFullScreenSignIn({ embedded: false, signedIn: true })).toBe(false);
    expect(requiresFullScreenSignIn({ embedded: true, signedIn: true })).toBe(false);
  });
});
