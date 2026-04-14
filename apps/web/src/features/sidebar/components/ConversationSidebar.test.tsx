// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { ConversationItem } from "./conversationSidebarTypes";
import { ConversationSidebar } from "./ConversationSidebar";
import { useConversationSidebarActions } from "@/features/sidebar/hooks/useConversationSidebarActions";
import { useConversationSidebarData } from "@/features/sidebar/hooks/useConversationSidebarData";

vi.mock("@/features/sidebar/hooks/useConversationSidebarActions");
vi.mock("@/features/sidebar/hooks/useConversationSidebarData");
vi.mock("@/state/useStrategySelectors", () => ({
  useStrategyList: () => ({ graphValidationStatus: {} }),
}));

const ITEM_A: ConversationItem = {
  id: "conv_a",
  kind: "strategy",
  title: "Plasmo invasion screen",
  updatedAt: "2026-04-01T12:00:00Z",
  siteId: "plasmodb",
  stepCount: 4,
};

const ITEM_B: ConversationItem = {
  id: "conv_b",
  kind: "strategy",
  title: "Mosquito gut transcriptome",
  updatedAt: "2026-04-01T13:00:00Z",
  siteId: "vectorbase",
  stepCount: 2,
};

const DISMISSED: ConversationItem = {
  id: "conv_dismissed",
  kind: "strategy",
  title: "Old draft",
  updatedAt: "2026-03-30T08:00:00Z",
};

type DataReturn = ReturnType<typeof useConversationSidebarData>;
type ActionsReturn = ReturnType<typeof useConversationSidebarActions>;

function makeData(overrides: Partial<DataReturn> = {}): DataReturn {
  return {
    filtered: [ITEM_A, ITEM_B],
    hasConversations: true,
    hasInitiallyLoaded: true,
    query: "",
    setQuery: vi.fn(),
    isSyncing: false,
    invalidateStrategies: vi.fn().mockResolvedValue(undefined),
    handleManualRefresh: vi.fn().mockResolvedValue(undefined),
    dismissedConversations: [],
    ...overrides,
  };
}

function makeActions(overrides: Partial<ActionsReturn> = {}): ActionsReturn {
  return {
    activeId: null,
    handleSelect: vi.fn(),
    handleNewConversation: vi.fn().mockResolvedValue(undefined),
    handleToggleSaved: vi.fn().mockResolvedValue(undefined),
    renamingId: null,
    renameValue: "",
    setRenameValue: vi.fn(),
    startRename: vi.fn(),
    cancelRename: vi.fn(),
    commitRename: vi.fn().mockResolvedValue(undefined),
    duplicateModal: null,
    setDuplicateModal: vi.fn(),
    startDuplicate: vi.fn(),
    handleDuplicate: vi.fn().mockResolvedValue(undefined),
    deleteTarget: null,
    setDeleteTarget: vi.fn(),
    isDeleting: false,
    confirmDelete: vi.fn().mockResolvedValue(undefined),
    permanentDeleteTarget: null,
    setPermanentDeleteTarget: vi.fn(),
    confirmPermanentDelete: vi.fn().mockResolvedValue(undefined),
    handleRestore: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  } as ActionsReturn;
}

beforeEach(() => {
  vi.mocked(useConversationSidebarData).mockReturnValue(makeData());
  vi.mocked(useConversationSidebarActions).mockReturnValue(makeActions());
});

afterEach(() => cleanup());

describe("ConversationSidebar", () => {
  it("renders the conversation list with all loaded items", () => {
    render(<ConversationSidebar siteId="plasmodb" />);
    expect(screen.getByText("Plasmo invasion screen")).toBeInTheDocument();
    expect(screen.getByText("Mosquito gut transcriptome")).toBeInTheDocument();
  });

  it("typing in the search box calls data.setQuery on each character", () => {
    const setQuery = vi.fn();
    vi.mocked(useConversationSidebarData).mockReturnValue(makeData({ setQuery }));
    render(<ConversationSidebar siteId="plasmodb" />);

    const search = screen.getByPlaceholderText(/search conversations/i);
    fireEvent.change(search, { target: { value: "plasmo" } });

    expect(setQuery).toHaveBeenCalledWith("plasmo");
  });

  it("clicking Refresh triggers data.handleManualRefresh", async () => {
    const user = userEvent.setup();
    const handleManualRefresh = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useConversationSidebarData).mockReturnValue(
      makeData({ handleManualRefresh }),
    );
    render(<ConversationSidebar siteId="plasmodb" />);

    await user.click(screen.getByTestId("conversations-refresh-button"));
    expect(handleManualRefresh).toHaveBeenCalledTimes(1);
  });

  it("clicking New Chat triggers actions.handleNewConversation", async () => {
    const user = userEvent.setup();
    const handleNewConversation = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useConversationSidebarActions).mockReturnValue(
      makeActions({ handleNewConversation }),
    );
    render(<ConversationSidebar siteId="plasmodb" />);

    await user.click(screen.getByTestId("conversations-new-button"));
    expect(handleNewConversation).toHaveBeenCalledTimes(1);
  });

  it("disables Refresh and New Chat while a chat stream is in progress", async () => {
    const { useSessionStore } = await import("@/state/useSessionStore");
    useSessionStore.setState({ chatIsStreaming: true });

    render(<ConversationSidebar siteId="plasmodb" />);

    expect(screen.getByTestId("conversations-refresh-button")).toBeDisabled();
    expect(screen.getByTestId("conversations-new-button")).toBeDisabled();

    useSessionStore.setState({ chatIsStreaming: false });
  });

  it("shows a loading spinner before the first fetch completes", () => {
    vi.mocked(useConversationSidebarData).mockReturnValue(
      makeData({ filtered: [], hasInitiallyLoaded: false }),
    );
    render(<ConversationSidebar siteId="plasmodb" />);

    expect(screen.getByText(/loading conversations/i)).toBeInTheDocument();
  });

  it("renders an empty-state message when no conversations and no query", () => {
    vi.mocked(useConversationSidebarData).mockReturnValue(
      makeData({ filtered: [] }),
    );
    render(<ConversationSidebar siteId="plasmodb" />);

    expect(screen.getByText(/no conversations yet/i)).toBeInTheDocument();
  });

  it("shows search-empty message when query has no matches", () => {
    vi.mocked(useConversationSidebarData).mockReturnValue(
      makeData({ filtered: [], query: "nothing-matches" }),
    );
    render(<ConversationSidebar siteId="plasmodb" />);

    expect(
      screen.getByText(/no conversations match your search/i),
    ).toBeInTheDocument();
  });

  it("renders a Dismissed section when there are dismissed conversations", async () => {
    const user = userEvent.setup();
    vi.mocked(useConversationSidebarData).mockReturnValue(
      makeData({ dismissedConversations: [DISMISSED] }),
    );
    render(<ConversationSidebar siteId="plasmodb" />);

    const toggle = screen.getByTestId("dismissed-toggle");
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveTextContent(/dismissed \(1\)/i);

    await user.click(toggle);
    expect(screen.getByText("Old draft")).toBeInTheDocument();
  });

  it("Restore button on a dismissed item calls actions.handleRestore", async () => {
    const user = userEvent.setup();
    const handleRestore = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useConversationSidebarData).mockReturnValue(
      makeData({ dismissedConversations: [DISMISSED] }),
    );
    vi.mocked(useConversationSidebarActions).mockReturnValue(
      makeActions({ handleRestore }),
    );
    render(<ConversationSidebar siteId="plasmodb" />);

    await user.click(screen.getByTestId("dismissed-toggle"));
    await user.click(screen.getByTestId("dismissed-restore-button"));

    expect(handleRestore).toHaveBeenCalledWith("conv_dismissed");
  });

  it("Delete button on a dismissed item opens the permanent-delete dialog", async () => {
    const user = userEvent.setup();
    const setPermanentDeleteTarget = vi.fn();
    vi.mocked(useConversationSidebarData).mockReturnValue(
      makeData({ dismissedConversations: [DISMISSED] }),
    );
    vi.mocked(useConversationSidebarActions).mockReturnValue(
      makeActions({ setPermanentDeleteTarget }),
    );
    render(<ConversationSidebar siteId="plasmodb" />);

    await user.click(screen.getByTestId("dismissed-toggle"));
    await user.click(screen.getByTestId("dismissed-delete-button"));

    expect(setPermanentDeleteTarget).toHaveBeenCalledWith("conv_dismissed");
  });

  it("renders the permanent-delete dialog when actions.permanentDeleteTarget is set", () => {
    vi.mocked(useConversationSidebarActions).mockReturnValue(
      makeActions({ permanentDeleteTarget: "conv_dismissed" }),
    );
    render(<ConversationSidebar siteId="plasmodb" />);

    expect(screen.getByRole("dialog")).toHaveTextContent(/permanently delete strategy/i);
    expect(screen.getByRole("dialog")).toHaveTextContent(/cannot be undone/i);
  });

  it("permanent-delete dialog Confirm button calls confirmPermanentDelete", async () => {
    const user = userEvent.setup();
    const confirmPermanentDelete = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useConversationSidebarActions).mockReturnValue(
      makeActions({
        permanentDeleteTarget: "conv_dismissed",
        confirmPermanentDelete,
      }),
    );
    render(<ConversationSidebar siteId="plasmodb" />);

    await user.click(screen.getByRole("button", { name: /delete permanently/i }));
    expect(confirmPermanentDelete).toHaveBeenCalledTimes(1);
  });

  it("delete-confirmation dialog opens when actions.deleteTarget is set", () => {
    vi.mocked(useConversationSidebarActions).mockReturnValue(
      makeActions({ deleteTarget: ITEM_A }),
    );
    render(<ConversationSidebar siteId="plasmodb" />);

    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("Plasmo invasion screen");
  });

  it("invokes onToast({type:'error'}) when reportError is called via the actions hook", () => {
    const onToast = vi.fn();
    let capturedReportError: ((m: string) => void) | undefined;

    vi.mocked(useConversationSidebarActions).mockImplementation((args) => {
      capturedReportError = args.reportError;
      return makeActions();
    });

    render(<ConversationSidebar siteId="plasmodb" onToast={onToast} />);

    capturedReportError?.("WDK timeout");
    expect(onToast).toHaveBeenCalledWith({ type: "error", message: "WDK timeout" });
  });
});
