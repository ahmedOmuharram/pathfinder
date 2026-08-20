/**
 * @vitest-environment jsdom
 */
import { beforeEach, describe, expect, it } from "vitest";
import { fireEvent, render, renderHook, screen } from "@testing-library/react";

import { authStatusOptions } from "@/lib/api/veupathdb-auth";
import { createTestWrapper } from "@/lib/query/testing";
import { useAuthGateStore } from "@/state/useAuthGateStore";
import { useSessionStore } from "@/state/useSessionStore";

import {
  VeupathdbSignInRequired,
  useVeupathdbSignedIn,
} from "./VeupathdbSignInRequired";

function setup(signedIn: boolean | null) {
  const { queryClient, Wrapper } = createTestWrapper();
  const siteId = useSessionStore.getState().selectedSite;
  if (signedIn !== null) {
    queryClient.setQueryData(authStatusOptions(siteId).queryKey, { signedIn });
  }
  return { Wrapper };
}

beforeEach(() => {
  useAuthGateStore.getState().dismissSignIn();
});

describe("VeupathdbSignInRequired", () => {
  it("asks a signed-out user to sign in to VEuPathDB", () => {
    const { Wrapper } = setup(false);
    render(<VeupathdbSignInRequired />, { wrapper: Wrapper });
    expect(screen.getByTestId("veupathdb-signin-required")).toHaveTextContent(
      "Sign in to VEuPathDB to build strategies",
    );
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("opens the sign-in prompt when the button is pressed", () => {
    const { Wrapper } = setup(false);
    render(<VeupathdbSignInRequired />, { wrapper: Wrapper });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(useAuthGateStore.getState().signInRequired).toBe(true);
  });

  it("renders nothing for a signed-in user", () => {
    const { Wrapper } = setup(true);
    const { container } = render(<VeupathdbSignInRequired />, { wrapper: Wrapper });
    expect(container.childElementCount).toBe(0);
  });
});

describe("useVeupathdbSignedIn", () => {
  it("is true only when the auth status says so", () => {
    const signedIn = setup(true);
    expect(
      renderHook(() => useVeupathdbSignedIn(), { wrapper: signedIn.Wrapper }).result
        .current,
    ).toBe(true);

    const signedOut = setup(false);
    expect(
      renderHook(() => useVeupathdbSignedIn(), { wrapper: signedOut.Wrapper }).result
        .current,
    ).toBe(false);
  });

  it("treats an unresolved auth status as signed out", () => {
    const unknown = setup(null);
    expect(
      renderHook(() => useVeupathdbSignedIn(), { wrapper: unknown.Wrapper }).result
        .current,
    ).toBe(false);
  });
});
