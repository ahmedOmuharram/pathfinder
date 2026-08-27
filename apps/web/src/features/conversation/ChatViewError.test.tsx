/**
 * @vitest-environment jsdom
 */
import type * as ReactQueryModule from "@tanstack/react-query";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatViewError } from "./ChatViewError";

type ReactQueryExports = typeof ReactQueryModule;

describe("ChatViewError", () => {
  it("names the error and points back to the conversation list", async () => {
    const { render, screen } = await import("@testing-library/react");

    render(
      <ChatViewError
        error={new Error("A message with the same id already exists")}
        conversationsHref="/plasmodb/conversation"
      />,
    );

    expect(screen.getByText(/A message with the same id already exists/)).toBeTruthy();
    const back = screen.getByRole("link", { name: /back to conversations/i });
    expect(back.getAttribute("href")).toBe("/plasmodb/conversation");
  });

  it("names a thrown non-error too", async () => {
    const { render, screen } = await import("@testing-library/react");

    render(
      <ChatViewError error="plain string" conversationsHref="/toxodb/conversation" />,
    );

    expect(screen.getByText("plain string")).toBeTruthy();
  });
});

describe("ChatView error boundary", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  function mockChatViewDeps(pathname: string, siteId: string) {
    vi.doMock("next/navigation", () => ({
      redirect: vi.fn(),
      usePathname: () => pathname,
      useParams: () => ({ siteId }),
    }));
    vi.doMock("@tanstack/react-query", async () => {
      const actual = await vi.importActual<ReactQueryExports>("@tanstack/react-query");
      return {
        ...actual,
        useQuery: (opts: { queryKey: readonly unknown[] }) => {
          const key = opts.queryKey.join("/");
          if (key.includes("/detail")) {
            return {
              data: {
                id: "conv-1",
                name: "strat",
                siteId,
                steps: [],
                rootStepId: null,
                recordType: null,
                isSaved: false,
                createdAt: "2026-08-15T00:00:00Z",
                updatedAt: "2026-08-15T00:00:00Z",
              },
              isFetched: true,
              isPending: false,
            };
          }
          return { data: [], isFetched: true, isPending: false };
        },
      };
    });
    vi.doMock("nuqs", () => ({
      useQueryState: () => [null, () => {}],
      parseAsString: {},
    }));
    // The subject is where the boundary sits, so the chat runtime, the rail
    // and the provider stay out of the module graph.
    vi.doMock("@assistant-ui/react", () => ({
      AssistantRuntimeProvider: (props: { children: ReactNode }) => props.children,
    }));
    vi.doMock("./runtime/useChatRuntime", () => ({
      useChatRuntime: () => ({ runtime: {}, chat: {} }),
    }));
    vi.doMock("./runtime/chatHelpersContext", () => ({
      ChatHelpersProvider: (props: { children: ReactNode }) => props.children,
    }));
    vi.doMock("./rail/RightRail", () => ({ RightRail: () => null }));
  }

  it("renders the recovery panel instead of losing the whole view", async () => {
    mockChatViewDeps("/plasmodb/conversation/conv-1", "plasmodb");
    vi.doMock("./ChatThread", () => ({
      ChatThread: () => {
        throw new Error(
          "MessageRepository(performOp/link): A message with the same id already exists in the parent tree",
        );
      },
    }));
    // React reports a caught render error on the console; the panel is the
    // assertion.
    vi.spyOn(console, "error").mockImplementation(() => {});

    const { ChatView } = await import("./ChatView");
    const { render, screen } = await import("@testing-library/react");

    render(<ChatView conversationId="conv-1" allowMissing={false} />);

    expect(screen.getByText(/A message with the same id already exists/)).toBeTruthy();
    const back = screen.getByRole("link", { name: /back to conversations/i });
    expect(back.getAttribute("href")).toBe("/plasmodb/conversation");
  });

  it("leaves a thread that renders alone", async () => {
    mockChatViewDeps("/plasmodb/conversation/conv-1", "plasmodb");
    vi.doMock("./ChatThread", () => ({
      ChatThread: () => <div data-testid="thread" />,
    }));

    const { ChatView } = await import("./ChatView");
    const { render, screen } = await import("@testing-library/react");

    render(<ChatView conversationId="conv-1" allowMissing={false} />);

    expect(screen.getByTestId("thread")).toBeTruthy();
    expect(screen.queryByRole("link", { name: /back to conversations/i })).toBeNull();
  });
});
