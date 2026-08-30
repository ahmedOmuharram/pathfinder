/**
 * @vitest-environment jsdom
 */
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import type * as AssistantUi from "@assistant-ui/react";

vi.mock("@assistant-ui/react", async (importOriginal) => {
  const actual = await importOriginal<typeof AssistantUi>();
  return {
    ...actual,
    ActionBarPrimitive: {
      ...actual.ActionBarPrimitive,
      Reload: ({ children }: { children: ReactNode }) => children,
    },
  };
});

import { FailureNotice } from "./FailureNotice";

const DETAIL = "The worker running this turn stopped before it finished.";

describe("FailureNotice", () => {
  it("names the failure and repeats what the backend said", () => {
    render(<FailureNotice detail={DETAIL} />);
    const notice = screen.getByTestId("failure-notice");
    expect(notice).toHaveTextContent("Response failed");
    expect(notice).toHaveTextContent(DETAIL);
  });

  it("offers a retry", () => {
    render(<FailureNotice detail={DETAIL} />);
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("is a hairline and text, never a card", () => {
    render(<FailureNotice detail={DETAIL} />);
    const tokens = screen.getByTestId("failure-notice").className.split(/\s+/);
    expect(
      tokens.filter((t) => /^(border|rounded-lg|rounded-md|bg-destructive)/.test(t)),
    ).toEqual([]);
    expect(tokens).toContain("text-destructive");
  });

  it("draws no border on the retry button either", () => {
    render(<FailureNotice detail={DETAIL} />);
    const tokens = screen
      .getByRole("button", { name: "Try again" })
      .className.split(/\s+/);
    expect(tokens.filter((t) => t === "border" || t.startsWith("border-"))).toEqual([]);
  });
});
