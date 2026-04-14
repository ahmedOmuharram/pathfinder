// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { Strategy } from "@pathfinder/shared";

import type { ConversationItem } from "./conversationSidebarTypes";
import { ConversationListItem } from "./ConversationListItem";

const STRATEGY: Strategy = {
  id: "strat_1",
  name: "My pipeline",
  siteId: "plasmodb",
  isSaved: false,
  stepCount: 3,
  wdkStrategyId: 12345,
  graph: { rootStepId: "step_1", stepTree: { stepId: 1 }, steps: {} },
} as unknown as Strategy;

const ITEM: ConversationItem = {
  id: "conv_1",
  kind: "strategy",
  title: "Untitled conversation",
  updatedAt: "2026-04-01T12:00:00Z",
  siteId: "plasmodb",
  stepCount: 3,
  strategyItem: STRATEGY,
};

const NO_STRATEGY_ITEM: ConversationItem = {
  id: "conv_2",
  kind: "strategy",
  title: "Brand new chat",
  updatedAt: "2026-04-01T12:00:00Z",
};

function renderItem(overrides: Partial<Parameters<typeof ConversationListItem>[0]> = {}) {
  const props: Parameters<typeof ConversationListItem>[0] = {
    item: ITEM,
    isActive: false,
    isRenaming: false,
    renameValue: "",
    graphHasValidationIssue: false,
    isActiveStreaming: false,
    activePhase: null,
    activePhaseStatus: null,
    onRenameValueChange: vi.fn(),
    onCommitRename: vi.fn(),
    onCancelRename: vi.fn(),
    onSelect: vi.fn(),
    onStartRename: vi.fn(),
    onStartDelete: vi.fn(),
    onStartDuplicate: vi.fn(),
    onToggleSaved: vi.fn(),
    ...overrides,
  };
  render(<ConversationListItem {...props} />);
  return props;
}

afterEach(() => cleanup());

describe("ConversationListItem", () => {
  it("renders the conversation title and step count", () => {
    renderItem();
    expect(screen.getByText("Untitled conversation")).toBeInTheDocument();
    expect(screen.getByText(/3 steps/i)).toBeInTheDocument();
  });

  it("calls onSelect when the item body is clicked", () => {
    const props = renderItem();
    fireEvent.click(screen.getByRole("button", { name: /Untitled conversation/i }));
    expect(props.onSelect).toHaveBeenCalledWith(ITEM);
  });

  it("renders an inline rename input when isRenaming is true", () => {
    const props = renderItem({ isRenaming: true, renameValue: "Editing…" });
    const input = screen.getByDisplayValue("Editing…");
    expect(input).toBeInTheDocument();
    fireEvent.change(input, { target: { value: "New title" } });
    expect(props.onRenameValueChange).toHaveBeenCalledWith("New title");
  });

  it("commits rename when the user presses Enter in the rename input", () => {
    const props = renderItem({ isRenaming: true, renameValue: "Editing" });
    const input = screen.getByDisplayValue("Editing");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(props.onCommitRename).toHaveBeenCalledWith(ITEM);
  });

  it("cancels rename when the user presses Escape", () => {
    const props = renderItem({ isRenaming: true, renameValue: "Editing" });
    fireEvent.keyDown(screen.getByDisplayValue("Editing"), { key: "Escape" });
    expect(props.onCancelRename).toHaveBeenCalledTimes(1);
  });

  it("commits rename on blur", () => {
    const props = renderItem({ isRenaming: true, renameValue: "Editing" });
    fireEvent.blur(screen.getByDisplayValue("Editing"));
    expect(props.onCommitRename).toHaveBeenCalledWith(ITEM);
  });

  it("opens an actions dropdown when the more-vertical button is clicked", async () => {
    const user = userEvent.setup();
    renderItem();
    await user.click(screen.getByRole("button", { name: /conversation actions/i }));
    expect(await screen.findByRole("menuitem", { name: /rename/i })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /duplicate/i })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /delete/i })).toBeInTheDocument();
  });

  it("calls onStartRename when Rename is selected from the menu", async () => {
    const user = userEvent.setup();
    const props = renderItem();
    await user.click(screen.getByRole("button", { name: /conversation actions/i }));
    await user.click(await screen.findByRole("menuitem", { name: /rename/i }));
    expect(props.onStartRename).toHaveBeenCalledWith(ITEM);
  });

  it("calls onStartDuplicate with the strategy when Duplicate is selected", async () => {
    const user = userEvent.setup();
    const props = renderItem();
    await user.click(screen.getByRole("button", { name: /conversation actions/i }));
    await user.click(await screen.findByRole("menuitem", { name: /duplicate/i }));
    expect(props.onStartDuplicate).toHaveBeenCalledWith(STRATEGY);
  });

  it("calls onStartDelete when Delete is selected", async () => {
    const user = userEvent.setup();
    const props = renderItem();
    await user.click(screen.getByRole("button", { name: /conversation actions/i }));
    await user.click(await screen.findByRole("menuitem", { name: /delete/i }));
    expect(props.onStartDelete).toHaveBeenCalledWith(ITEM);
  });

  it("calls onToggleSaved when Mark as saved is selected for an unsaved strategy", async () => {
    const user = userEvent.setup();
    const props = renderItem();
    await user.click(screen.getByRole("button", { name: /conversation actions/i }));
    await user.click(await screen.findByRole("menuitem", { name: /mark as saved/i }));
    expect(props.onToggleSaved).toHaveBeenCalledWith(STRATEGY);
  });

  it("offers Revert to draft when the strategy is already saved", async () => {
    const user = userEvent.setup();
    renderItem({
      item: { ...ITEM, strategyItem: { ...STRATEGY, isSaved: true } as Strategy },
    });
    await user.click(screen.getByRole("button", { name: /conversation actions/i }));
    expect(
      await screen.findByRole("menuitem", { name: /revert to draft/i }),
    ).toBeInTheDocument();
  });

  it("hides Duplicate / toggle when there is no underlying strategy", async () => {
    const user = userEvent.setup();
    renderItem({ item: NO_STRATEGY_ITEM });
    await user.click(screen.getByRole("button", { name: /conversation actions/i }));
    expect(await screen.findByRole("menuitem", { name: /rename/i })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: /duplicate/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: /mark as saved/i })).not.toBeInTheDocument();
  });

  it("renders a streaming indicator on the active streaming item", () => {
    renderItem({ isActive: true, isActiveStreaming: true });
    expect(screen.getByText(/streaming/i)).toBeInTheDocument();
  });

  it("highlights validation issues with a destructive dot", () => {
    const { container } = render(
      <ConversationListItem
        {...{
          item: ITEM,
          isActive: false,
          isRenaming: false,
          renameValue: "",
          graphHasValidationIssue: true,
          isActiveStreaming: false,
          activePhase: null,
          activePhaseStatus: null,
          onRenameValueChange: () => {},
          onCommitRename: () => {},
          onCancelRename: () => {},
          onSelect: () => {},
          onStartRename: () => {},
          onStartDelete: () => {},
          onStartDuplicate: () => {},
          onToggleSaved: () => {},
        }}
      />,
    );
    expect(container.querySelector('[title="Validation issues"]')).toBeInTheDocument();
  });
});
