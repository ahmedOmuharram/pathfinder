// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("@/features/settings/api/memories", () => ({
  listMemories: vi.fn(),
  searchMemories: vi.fn(),
  editMemory: vi.fn(),
  deleteMemory: vi.fn(),
}));

import {
  deleteMemory,
  editMemory,
  listMemories,
} from "@/features/settings/api/memories";
import type { MemoryItem, MemoryListResponse } from "@pathfinder/shared";
import { MemorySettings } from "./MemorySettings";

const mockedList = vi.mocked(listMemories);
const mockedEdit = vi.mocked(editMemory);
const mockedDelete = vi.mocked(deleteMemory);

function item(name: string, kind: MemoryItem["value"]["kind"]): MemoryItem {
  return {
    key: `k-${name}`,
    value: {
      kind,
      name,
      summary: `${name} summary`,
      tags: [],
      content: {},
      autoRetrieve: true,
      createdAt: new Date().toISOString(),
    },
  };
}

function emptyList(): MemoryListResponse {
  return {
    geneSets: [],
    strategies: [],
    preferences: [],
    knowledge: [],
    pageSize: 50,
    offset: 0,
    hasMore: false,
  };
}

beforeEach(() => {
  mockedList.mockReset();
  mockedEdit.mockReset();
  mockedDelete.mockReset();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("MemorySettings", () => {
  it("renders four MemorySection accordions", async () => {
    mockedList.mockResolvedValue(emptyList());
    render(<MemorySettings />);
    await screen.findByRole("button", { name: /Gene Sets/i });
    expect(screen.getByRole("button", { name: /Gene Sets/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Strategies/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Preferences/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Knowledge/i })).toBeInTheDocument();
  });

  it("shows error state on failed list", async () => {
    mockedList.mockRejectedValue(new Error("boom"));
    render(<MemorySettings />);
    await waitFor(() => {
      expect(screen.getByText(/Failed to load/i)).toBeInTheDocument();
    });
  });

  it("deletes memory on confirmed delete", async () => {
    const gs = item("drug_targets", "gene_set");
    mockedList.mockResolvedValue({
      geneSets: [gs],
      strategies: [],
      preferences: [],
      knowledge: [],
      pageSize: 50,
      offset: 0,
      hasMore: false,
    });
    mockedDelete.mockResolvedValue(undefined);
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<MemorySettings />);
    await screen.findByRole("button", { name: /Gene Sets/i });
    fireEvent.click(screen.getByRole("button", { name: /Gene Sets/i }));
    fireEvent.click(screen.getByLabelText(/delete drug_targets/i));
    expect(confirmSpy).toHaveBeenCalled();
    await waitFor(() => {
      expect(mockedDelete).toHaveBeenCalledWith("k-drug_targets", "gene_set");
    });
  });

  it("skips delete when user cancels confirm", async () => {
    const gs = item("drug_targets", "gene_set");
    mockedList.mockResolvedValue({
      geneSets: [gs],
      strategies: [],
      preferences: [],
      knowledge: [],
      pageSize: 50,
      offset: 0,
      hasMore: false,
    });
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<MemorySettings />);
    await screen.findByRole("button", { name: /Gene Sets/i });
    fireEvent.click(screen.getByRole("button", { name: /Gene Sets/i }));
    fireEvent.click(screen.getByLabelText(/delete drug_targets/i));
    expect(mockedDelete).not.toHaveBeenCalled();
  });

  it("calls editMemory on auto-retrieve toggle", async () => {
    const k = item("my_knowledge", "knowledge");
    mockedList.mockResolvedValue({
      geneSets: [],
      strategies: [],
      preferences: [],
      knowledge: [k],
      pageSize: 50,
      offset: 0,
      hasMore: false,
    });
    mockedEdit.mockResolvedValue(k);
    render(<MemorySettings />);
    await screen.findByRole("button", { name: /Gene Sets/i });
    fireEvent.click(screen.getByRole("button", { name: /Knowledge/i }));
    fireEvent.click(screen.getByRole("checkbox"));
    await waitFor(() => {
      expect(mockedEdit).toHaveBeenCalledWith("k-my_knowledge", "knowledge", {
        autoRetrieve: false,
      });
    });
  });

  it("opens editor on row click and saves edits", async () => {
    const k = item("my_knowledge", "knowledge");
    mockedList.mockResolvedValue({
      geneSets: [],
      strategies: [],
      preferences: [],
      knowledge: [k],
      pageSize: 50,
      offset: 0,
      hasMore: false,
    });
    mockedEdit.mockResolvedValue(k);
    render(<MemorySettings />);
    await screen.findByRole("button", { name: /Gene Sets/i });
    fireEvent.click(screen.getByRole("button", { name: /Knowledge/i }));
    fireEvent.click(screen.getByTestId("memory-row-body"));
    expect(screen.getByRole("dialog", { name: /edit memory/i })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/^name$/i), {
      target: { value: "Updated" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => {
      expect(mockedEdit).toHaveBeenCalled();
    });
    const [, kind, body] = mockedEdit.mock.calls[0] ?? [];
    expect(kind).toBe("knowledge");
    expect(body?.name).toBe("Updated");
  });

  it("requests next page when Load more clicked", async () => {
    const gs = item("first_page", "gene_set");
    mockedList.mockResolvedValue({
      geneSets: [gs],
      strategies: [],
      preferences: [],
      knowledge: [],
      pageSize: 50,
      offset: 0,
      hasMore: true,
    });
    render(<MemorySettings />);
    await screen.findByRole("button", { name: /Gene Sets/i });
    const loadMore = screen.getByRole("button", { name: /load more/i });
    const callsBefore = mockedList.mock.calls.length;
    fireEvent.click(loadMore);
    await waitFor(() => {
      expect(mockedList.mock.calls.length).toBeGreaterThan(callsBefore);
    });
    const lastCall = mockedList.mock.calls.at(-1)?.[0];
    expect(lastCall).toMatchObject({ limit: 50, offset: 50 });
  });

  it("hides Load more when hasMore is false", async () => {
    mockedList.mockResolvedValue(emptyList());
    render(<MemorySettings />);
    await screen.findByRole("button", { name: /Gene Sets/i });
    expect(
      screen.queryByRole("button", { name: /load more/i }),
    ).not.toBeInTheDocument();
  });
});
