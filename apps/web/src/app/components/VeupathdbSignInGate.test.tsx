/**
 * @vitest-environment jsdom
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { toast } from "sonner";

import { APIError } from "@/lib/api/http";
import { __makeQueryClientForTests, setQueryErrorHandler } from "@/lib/query/client";
import {
  WDK_LOGIN_REQUIRED_TOAST_ID,
  useAuthGateStore,
} from "@/state/useAuthGateStore";

import { VeupathdbSignInGate } from "./VeupathdbSignInGate";

vi.mock("sonner", () => ({ toast: { error: vi.fn() } }));

const LOGIN_REQUIRED_BODY = {
  type: "about:blank",
  title: "VEuPathDB login required",
  status: 401,
  detail: "Sign in to VEuPathDB to use searches, strategies and gene sets.",
  code: "WDK_LOGIN_REQUIRED",
};

function renderGate(forced: boolean) {
  return render(
    <VeupathdbSignInGate
      forced={forced}
      selectedSite="plasmodb"
      onSiteChange={vi.fn()}
    />,
  );
}

/** Drive a failing query through the handler the gate registered on render. */
async function failQuery(error: unknown): Promise<void> {
  await __makeQueryClientForTests()
    .fetchQuery({
      queryKey: ["gene-sets", crypto.randomUUID()],
      queryFn: () => Promise.reject(error),
      retry: false,
    })
    .catch(() => {});
}

beforeEach(() => {
  useAuthGateStore.getState().dismissSignIn();
  vi.mocked(toast.error).mockClear();
});

afterEach(() => {
  setQueryErrorHandler(null);
});

describe("VeupathdbSignInGate", () => {
  it("shows an undismissable prompt when the session has no VEuPathDB login", () => {
    renderGate(true);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Close" })).toBeNull();
  });

  it("shows nothing while the session is signed in and nothing was refused", () => {
    const { baseElement } = renderGate(false);
    expect(baseElement.querySelectorAll("[role='dialog']")).toHaveLength(0);
  });

  it("opens the prompt with the server detail when a query is refused for want of a login", async () => {
    renderGate(false);

    await failQuery(
      new APIError(LOGIN_REQUIRED_BODY.detail, {
        status: 401,
        statusText: "Unauthorized",
        url: "/api/v1/gene-sets",
        data: LOGIN_REQUIRED_BODY,
      }),
    );

    await waitFor(() => {
      expect(screen.getByText(LOGIN_REQUIRED_BODY.detail)).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
    expect(vi.mocked(toast.error)).toHaveBeenCalledWith(LOGIN_REQUIRED_BODY.detail, {
      id: WDK_LOGIN_REQUIRED_TOAST_ID,
    });
  });

  it("reports an unrelated query failure without opening the prompt", async () => {
    renderGate(false);

    await failQuery(new Error("network down"));

    expect(vi.mocked(toast.error)).toHaveBeenCalledWith("network down");
    expect(useAuthGateStore.getState().signInRequired).toBe(false);
  });
});
