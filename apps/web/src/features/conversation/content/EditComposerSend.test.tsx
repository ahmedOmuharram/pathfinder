/**
 * @vitest-environment jsdom
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const pushMock = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  usePathname: () => "/toxodb/conversation/conv-2",
  useRouter: () => ({ push: pushMock }),
}));

vi.mock("@assistant-ui/react", () => ({
  useAuiState: (
    select: (state: {
      message: { id: string; parentId: string; role: string; content: never[] };
    }) => unknown,
  ) =>
    select({
      message: { id: "msg-5", parentId: "msg-4", role: "user", content: [] },
    }),
  useEditComposer: (select: (state: { text: string }) => unknown) =>
    select({ text: "  narrow it to kinases  " }),
}));

vi.mock("@pathfinder/shared/generated/hooks/useForkStrategy", () => ({
  forkStrategy: vi.fn(() => Promise.resolve({ id: "fork-4" })),
}));

vi.mock("sonner", () => ({ toast: { error: vi.fn() } }));

import { forkStrategy } from "@pathfinder/shared/generated/hooks/useForkStrategy";
import { chatUrl } from "@/lib/routes";
import { useSessionStore } from "@/state/useSessionStore";

import { EditComposerBranchOrRevert } from "./EditComposerSend";

describe("EditComposerBranchOrRevert", () => {
  afterEach(() => {
    useSessionStore.getState().setPendingUserSubmission(null);
  });

  it("pushes the fork's chat url built from the path's site id", async () => {
    render(<EditComposerBranchOrRevert />);

    fireEvent.click(screen.getByTestId("edit-composer-branch-or-revert"));
    fireEvent.click(screen.getByTestId("edit-branch-button"));

    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith(chatUrl("toxodb", "fork-4"));
    });
    expect(vi.mocked(forkStrategy)).toHaveBeenCalledWith("conv-2", {
      fromMessageId: "msg-4",
    });
    expect(useSessionStore.getState().pendingUserSubmission).toEqual({
      conversationId: "fork-4",
      content: "narrow it to kinases",
    });
  });
});
