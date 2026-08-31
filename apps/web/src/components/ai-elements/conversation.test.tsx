/**
 * @vitest-environment jsdom
 */
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

const viewportProps: Record<string, unknown>[] = [];

vi.mock("@assistant-ui/react", () => ({
  ThreadPrimitive: {
    Viewport: ({ children, ...props }: { children?: ReactNode }) => {
      viewportProps.push(props as Record<string, unknown>);
      return <div data-testid="thread-viewport">{children}</div>;
    },
    ScrollToBottom: ({ children }: { children?: ReactNode }) => (
      <div data-testid="scroll-to-bottom">{children}</div>
    ),
  },
}));

import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "./conversation";

describe("the thread scroll surface", () => {
  it("is the thread primitive's own viewport, scrolling to the bottom on send", () => {
    render(
      <Conversation>
        <ConversationContent>
          <p>a message</p>
        </ConversationContent>
        <ConversationScrollButton />
      </Conversation>,
    );

    expect(screen.getByTestId("thread-viewport")).toBeInTheDocument();
    expect(screen.getByText("a message")).toBeInTheDocument();
    expect(screen.getByTestId("scroll-to-bottom")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Scroll to the latest message" }).className,
    ).toContain("disabled:invisible");

    const props = viewportProps[viewportProps.length - 1] ?? {};
    expect(props["autoScroll"]).not.toBe(false);
    expect(props["scrollToBottomOnRunStart"]).not.toBe(false);
    expect(props["turnAnchor"]).not.toBe("top");
  });
});
