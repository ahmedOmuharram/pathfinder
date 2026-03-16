// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { ConversationListItem } from "./ConversationListItem";
import type { ConversationItem } from "./conversationSidebarTypes";
import type { Strategy } from "@pathfinder/shared";

afterEach(cleanup);

function makeStrategy(overrides: Partial<Strategy> = {}): Strategy {
  return {
    id: "s1",
    name: "Test Strategy",
    siteId: "plasmodb",
    recordType: "gene",
    steps: [],
    rootStepId: null,
    isSaved: false,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeItem(strategy: Strategy): ConversationItem {
  return {
    id: strategy.id,
    kind: "strategy",
    title: strategy.name,
    updatedAt: strategy.updatedAt,
    siteId: strategy.siteId,
    stepCount: strategy.stepCount ?? strategy.steps.length,
    strategyItem: strategy,
  };
}

const noop = vi.fn();

function renderItem(
  strategy: Strategy,
  { isActiveStreaming = false }: { isActiveStreaming?: boolean } = {},
) {
  return render(
    <ConversationListItem
      item={makeItem(strategy)}
      isActive={false}
      isRenaming={false}
      renameValue=""
      graphHasValidationIssue={false}
      isActiveStreaming={isActiveStreaming}
      onRenameValueChange={noop}
      onCommitRename={noop}
      onCancelRename={noop}
      onSelect={noop}
      onStartRename={noop}
      onStartDelete={noop}
      onStartDuplicate={noop}
      onToggleSaved={noop}
    />,
  );
}

describe("ConversationListItem status badge", () => {
  it("shows 'Building' when active, streaming, and no wdkStrategyId", () => {
    const strategy = makeStrategy({ stepCount: 3 });
    renderItem(strategy, { isActiveStreaming: true });
    expect(screen.getByText("Building")).toBeTruthy();
  });

  it("shows 'Draft' when steps exist, no wdkStrategyId, and NOT streaming", () => {
    const strategy = makeStrategy({ stepCount: 3 });
    renderItem(strategy, { isActiveStreaming: false });
    expect(screen.getByText("Draft")).toBeTruthy();
    expect(screen.queryByText("Building")).toBeNull();
  });

  it("shows 'Draft' when wdkStrategyId is set but isSaved is false", () => {
    const strategy = makeStrategy({
      stepCount: 3,
      wdkStrategyId: 42,
      isSaved: false,
    });
    renderItem(strategy);
    expect(screen.getByText("Draft")).toBeTruthy();
  });

  it("shows 'Saved' when wdkStrategyId is set and isSaved is true", () => {
    const strategy = makeStrategy({
      stepCount: 3,
      wdkStrategyId: 42,
      isSaved: true,
    });
    renderItem(strategy);
    expect(screen.getByText("Saved")).toBeTruthy();
  });

  it("does not show a status badge when no steps and no wdkStrategyId", () => {
    const strategy = makeStrategy({ stepCount: 0 });
    renderItem(strategy);
    expect(screen.queryByText("Building")).toBeNull();
    expect(screen.queryByText("Draft")).toBeNull();
    expect(screen.queryByText("Saved")).toBeNull();
  });

  it("shows 'Draft' for inactive item even when streaming is in progress elsewhere", () => {
    // isActiveStreaming is false because this item is not the active one
    const strategy = makeStrategy({ stepCount: 2 });
    renderItem(strategy, { isActiveStreaming: false });
    expect(screen.getByText("Draft")).toBeTruthy();
    expect(screen.queryByText("Building")).toBeNull();
  });
});
