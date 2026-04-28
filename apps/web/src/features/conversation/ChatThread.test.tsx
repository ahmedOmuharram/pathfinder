/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  AssistantRuntimeProvider,
  useLocalRuntime,
} from "@assistant-ui/react";
import { http } from "msw";
import type { ReactNode } from "react";

import { server } from "../../../vitest.msw-setup";
import { ChatThread } from "./ChatThread";

function StubRuntimeProvider({ children }: { children: ReactNode }) {
  const runtime = useLocalRuntime({
    async run() {
      return { content: [] };
    },
  });
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  );
}

describe("ChatThread", () => {
  it("renders the thread root and composer with a textarea + send button", () => {
    server.use(
      http.post("http://localhost:3000/api/v1/chat", () => new Response(null)),
    );

    render(
      <StubRuntimeProvider>
        <ChatThread conversationId="c1" />
      </StubRuntimeProvider>,
    );

    expect(screen.getByPlaceholderText(/ask about strategies/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();
  });
});
