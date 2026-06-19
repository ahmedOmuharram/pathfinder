// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ConversationResponse } from "@pathfinder/shared/generated/types/ConversationResponse";

import type { ConversationItem } from "./conversationSidebarTypes";

vi.mock("@/features/strategy/hooks/useFlushBeforeNav", () => ({
  useFlushBeforeNav: () => ({ navigate: vi.fn(), pending: false }),
}));

import { ConversationListItem } from "./ConversationListItem";

function makeItem(): ConversationItem {
  return {
    id: "c1",
    title: "Kinase strategy",
    updatedAt: "2026-01-01T00:00:00Z",
    siteId: "plasmodb",
    isDismissed: false,
    isSaved: false,
    stepCount: 1,
    experimentId: null,
    parentConversationId: null,
    parentMessageId: null,
    chat: { id: "c1", name: "Kinase strategy" } as ConversationResponse,
  };
}

const noop = (): void => {};

function renderItem(over: Partial<Parameters<typeof ConversationListItem>[0]> = {}) {
  return render(
    <ConversationListItem
      item={makeItem()}
      isActive={false}
      isRenaming={false}
      renameValue=""
      isActiveStreaming={false}
      activePhase={null}
      activePhaseStatus={null}
      onRenameValueChange={noop}
      onCommitRename={noop}
      onCancelRename={noop}
      onStartRename={noop}
      onStartDelete={noop}
      onToggleSaved={noop}
      {...over}
    />,
  );
}

describe("ConversationListItem duplicate action", () => {
  afterEach(cleanup);

  it("invokes onDuplicate once with the full conversation item", async () => {
    const onDuplicate = vi.fn();
    renderItem({ onDuplicate });

    await userEvent.click(
      screen.getByRole("button", { name: /conversation actions/i }),
    );
    await userEvent.click(
      await screen.findByRole("menuitem", { name: /^duplicate$/i }),
    );

    // The handler receives the exact item it should copy — id, title, site and
    // saved-state all flow through so the duplicate targets the right row.
    expect(onDuplicate.mock.calls).toEqual([[makeItem()]]);
  });

  it("offers Rename / Mark as saved / Delete but no Duplicate when unwired", async () => {
    renderItem();

    await userEvent.click(
      screen.getByRole("button", { name: /conversation actions/i }),
    );
    const labels = (await screen.findAllByRole("menuitem")).map((el) =>
      el.textContent.trim(),
    );
    expect(labels).toEqual(["Rename", "Mark as saved", "Delete"]);
  });
});
