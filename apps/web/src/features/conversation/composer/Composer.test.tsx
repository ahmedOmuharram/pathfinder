/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AssistantRuntimeProvider, useLocalRuntime } from "@assistant-ui/react";
import type { ReactNode } from "react";

import { authStatusOptions } from "@/lib/api/veupathdb-auth";
import { createTestWrapper } from "@/lib/query/testing";
import { useSessionStore } from "@/state/useSessionStore";

import { Composer } from "./Composer";

function StubRuntimeProvider({ children }: { children: ReactNode }) {
  const runtime = useLocalRuntime({
    async run() {
      return { content: [] };
    },
  });
  return (
    <AssistantRuntimeProvider runtime={runtime}>{children}</AssistantRuntimeProvider>
  );
}

function renderComposer(signedIn: boolean) {
  const { queryClient, Wrapper } = createTestWrapper();
  queryClient.setQueryData(
    authStatusOptions(useSessionStore.getState().selectedSite).queryKey,
    { signedIn },
  );
  return render(
    <StubRuntimeProvider>
      <Composer conversationId="test-conversation" />
    </StubRuntimeProvider>,
    { wrapper: Wrapper },
  );
}

describe("Composer", () => {
  it("renders an input and send button for a signed-in user", () => {
    renderComposer(true);
    expect(screen.getByPlaceholderText(/ask about strategies/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();
    expect(screen.queryByTestId("veupathdb-signin-required")).not.toBeInTheDocument();
  });

  it("disables the composer and asks for a VEuPathDB login when signed out", () => {
    renderComposer(false);
    expect(screen.getByTestId("veupathdb-signin-required")).toHaveTextContent(
      "Sign in to VEuPathDB to build strategies",
    );
    expect(
      screen.getByPlaceholderText("Sign in to VEuPathDB to build strategies"),
    ).toBeDisabled();
    expect(screen.getByTestId("send-button")).toBeDisabled();
  });
});
