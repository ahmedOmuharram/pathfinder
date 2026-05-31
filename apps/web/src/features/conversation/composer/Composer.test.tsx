/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AssistantRuntimeProvider, useLocalRuntime } from "@assistant-ui/react";
import type { ReactNode } from "react";

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

describe("Composer", () => {
  it("renders an input and send button", () => {
    render(
      <StubRuntimeProvider>
        <Composer conversationId="test-conversation" />
      </StubRuntimeProvider>,
    );
    expect(screen.getByPlaceholderText(/ask about strategies/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();
  });
});
