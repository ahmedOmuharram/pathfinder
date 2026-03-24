// @vitest-environment jsdom
/**
 * Tests for useWorkbenchChat hook — focuses on testable behavior:
 * stop() calling cancelOperation, tool call preservation from loaded messages,
 * auto-trigger gating on historyLoaded, error state on SSE errors, and
 * workbench_gene_set events calling addGeneSet on the store.
 */

import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Hoisted mocks — must be declared before vi.mock calls
// ---------------------------------------------------------------------------

const mockGetMessages = vi.hoisted(() => vi.fn());
const mockStreamChat = vi.hoisted(() => vi.fn());
const mockCancelOperation = vi.hoisted(() => vi.fn());

const mockAddGeneSet = vi.hoisted(() => vi.fn());
const mockStoreGetState = vi.hoisted(() =>
  vi.fn(() => ({ addGeneSet: mockAddGeneSet })),
);

// ---------------------------------------------------------------------------
// vi.mock declarations
// ---------------------------------------------------------------------------

vi.mock("../api/workbenchChatApi", () => ({
  getWorkbenchChatMessages: (...args: unknown[]) => mockGetMessages(...args),
  streamWorkbenchChat: (...args: unknown[]) => mockStreamChat(...args),
}));

vi.mock("@/lib/operationSubscribe", () => ({
  cancelOperation: (...args: unknown[]) => mockCancelOperation(...args),
}));

vi.mock("@/state/useWorkbenchStore", () => ({
  useWorkbenchStore: Object.assign(() => null, {
    getState: mockStoreGetState,
  }),
}));

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------

import { useWorkbenchChat } from "./useWorkbenchChat";
import type { ChatSSEEvent } from "@/lib/sse_events";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Default streamWorkbenchChat mock that returns a controllable cancel & promise */
function setupStreamMock(operationId = "op-123") {
  const cancelFn = vi.fn();
  mockStreamChat.mockReturnValue({
    promise: Promise.resolve({ operationId, streamId: "stream-1" }),
    cancel: cancelFn,
  });
  return { cancelFn };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useWorkbenchChat", () => {
  beforeEach(() => {
    mockGetMessages.mockResolvedValue([]);
    setupStreamMock();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // -----------------------------------------------------------------------
  // 1. stop() calls cancelOperation with the stored operation ID
  // -----------------------------------------------------------------------
  describe("stop()", () => {
    it("calls cancelOperation with the stored operation ID", async () => {
      const operationId = "op-abc-123";
      const cancelFn = vi.fn();
      mockStreamChat.mockReturnValue({
        promise: Promise.resolve({ operationId, streamId: "stream-1" }),
        cancel: cancelFn,
      });

      const { result } = renderHook(() => useWorkbenchChat("exp-1", "PlasmoDB"));

      // Wait for history to load (triggers auto-send)
      await waitFor(() => {
        expect(result.current.streaming).toBe(true);
      });

      // Wait for the promise to resolve so operationIdRef is set
      await act(async () => {
        await new Promise<void>((r) => setTimeout(r, 0));
      });

      // Call stop
      act(() => {
        result.current.stop();
      });

      expect(mockCancelOperation).toHaveBeenCalledWith(operationId);
      expect(cancelFn).toHaveBeenCalled();
      expect(result.current.streaming).toBe(false);
    });

    it("does not call cancelOperation when no operation ID is stored", async () => {
      mockStreamChat.mockReturnValue({
        promise: new Promise(() => {}), // never resolves — operationId never set
        cancel: vi.fn(),
      });
      // Prevent auto-trigger by returning existing messages
      mockGetMessages.mockResolvedValue([
        { role: "user", content: "hi", messageId: "m1" },
        { role: "assistant", content: "hello", messageId: "m2" },
      ]);

      const { result } = renderHook(() => useWorkbenchChat("exp-1", "PlasmoDB"));

      await waitFor(() => {
        expect(result.current.messages.length).toBe(2);
      });

      act(() => {
        result.current.stop();
      });

      expect(mockCancelOperation).not.toHaveBeenCalled();
    });
  });

  // -----------------------------------------------------------------------
  // 2. Tool calls from loaded messages are preserved (not stripped)
  // -----------------------------------------------------------------------
  describe("tool call preservation", () => {
    it("preserves toolCalls from loaded messages", async () => {
      const toolCalls = [
        { id: "tc-1", name: "search_genes", result: "found 42 genes" },
      ];
      mockGetMessages.mockResolvedValue([
        { role: "user", content: "find genes", messageId: "m1" },
        {
          role: "assistant",
          content: "Here are the results",
          messageId: "m2",
          toolCalls,
        },
      ]);

      const { result } = renderHook(() => useWorkbenchChat("exp-1", "PlasmoDB"));

      await waitFor(() => {
        expect(result.current.messages.length).toBe(2);
      });

      const assistantMsg = result.current.messages.find((m) => m.role === "assistant");
      expect(assistantMsg?.toolCalls).toEqual(toolCalls);
    });

    it("preserves citations from loaded messages", async () => {
      const citations = [{ title: "Paper A", url: "https://example.com/a" }];
      mockGetMessages.mockResolvedValue([
        { role: "user", content: "explain", messageId: "m1" },
        {
          role: "assistant",
          content: "Explanation",
          messageId: "m2",
          citations,
        },
      ]);

      const { result } = renderHook(() => useWorkbenchChat("exp-1", "PlasmoDB"));

      await waitFor(() => {
        expect(result.current.messages.length).toBe(2);
      });

      const assistantMsg = result.current.messages.find((m) => m.role === "assistant");
      expect(assistantMsg?.citations).toEqual(citations);
    });
  });

  // -----------------------------------------------------------------------
  // 3. Auto-trigger waits for historyLoaded before firing
  // -----------------------------------------------------------------------
  describe("auto-trigger", () => {
    it("does not auto-trigger before history is loaded", async () => {
      // Make getMessages hang forever
      let resolveMessages!: (msgs: unknown[]) => void;
      mockGetMessages.mockReturnValue(
        new Promise((resolve) => {
          resolveMessages = resolve;
        }),
      );

      renderHook(() => useWorkbenchChat("exp-1", "PlasmoDB"));

      // Give effects time to run
      await act(async () => {
        await new Promise<void>((r) => setTimeout(r, 50));
      });

      // streamWorkbenchChat should NOT have been called yet
      expect(mockStreamChat).not.toHaveBeenCalled();

      // Now resolve history with empty messages — should trigger auto-send
      await act(async () => {
        resolveMessages([]);
        await new Promise<void>((r) => setTimeout(r, 0));
      });

      await waitFor(() => {
        expect(mockStreamChat).toHaveBeenCalled();
      });
    });

    it("does not auto-trigger if messages already exist", async () => {
      mockGetMessages.mockResolvedValue([
        { role: "user", content: "existing", messageId: "m1" },
        { role: "assistant", content: "response", messageId: "m2" },
      ]);

      const { result } = renderHook(() => useWorkbenchChat("exp-1", "PlasmoDB"));

      await waitFor(() => {
        expect(result.current.messages.length).toBe(2);
      });

      // Give additional time for auto-trigger effect to run
      await act(async () => {
        await new Promise<void>((r) => setTimeout(r, 50));
      });

      // Should NOT have called stream since messages exist
      expect(mockStreamChat).not.toHaveBeenCalled();
    });
  });

  // -----------------------------------------------------------------------
  // 4. Error state is set on SSE error events
  // -----------------------------------------------------------------------
  describe("error state", () => {
    it("sets error on SSE error event via handleEvent", async () => {
      // Capture the onMessage callback when streamWorkbenchChat is called
      let capturedOnMessage!: (event: ChatSSEEvent) => void;
      mockStreamChat.mockImplementation(
        (
          _experimentId: string,
          _message: string,
          _siteId: string,
          callbacks: { onMessage: (event: ChatSSEEvent) => void },
        ) => {
          capturedOnMessage = callbacks.onMessage;
          return {
            promise: Promise.resolve({
              operationId: "op-1",
              streamId: "s-1",
            }),
            cancel: vi.fn(),
          };
        },
      );

      const { result } = renderHook(() => useWorkbenchChat("exp-1", "PlasmoDB"));

      // Wait for auto-trigger to fire
      await waitFor(() => {
        expect(mockStreamChat).toHaveBeenCalled();
      });

      // Simulate an error event
      act(() => {
        capturedOnMessage({
          type: "error",
          data: { error: "Backend exploded" },
        });
      });

      expect(result.current.error).toBe("Backend exploded");
      expect(result.current.streaming).toBe(false);
    });

    it("sets error on stream onError callback", async () => {
      let capturedOnError!: (err: Error) => void;
      mockStreamChat.mockImplementation(
        (
          _experimentId: string,
          _message: string,
          _siteId: string,
          callbacks: { onError: (err: Error) => void },
        ) => {
          capturedOnError = callbacks.onError;
          return {
            promise: Promise.resolve({
              operationId: "op-1",
              streamId: "s-1",
            }),
            cancel: vi.fn(),
          };
        },
      );

      const { result } = renderHook(() => useWorkbenchChat("exp-1", "PlasmoDB"));

      // Wait for auto-trigger to fire
      await waitFor(() => {
        expect(mockStreamChat).toHaveBeenCalled();
      });

      act(() => {
        capturedOnError(new Error("Connection lost"));
      });

      expect(result.current.error).toBe("Connection lost");
      expect(result.current.streaming).toBe(false);
    });
  });

  // -----------------------------------------------------------------------
  // 5. workbench_gene_set events call addGeneSet on the store
  // -----------------------------------------------------------------------
  describe("workbench_gene_set event", () => {
    it("calls addGeneSet on the store when workbench_gene_set event is received", async () => {
      let capturedOnMessage!: (event: ChatSSEEvent) => void;
      mockStreamChat.mockImplementation(
        (
          _experimentId: string,
          _message: string,
          _siteId: string,
          callbacks: { onMessage: (event: ChatSSEEvent) => void },
        ) => {
          capturedOnMessage = callbacks.onMessage;
          return {
            promise: Promise.resolve({
              operationId: "op-1",
              streamId: "s-1",
            }),
            cancel: vi.fn(),
          };
        },
      );

      renderHook(() => useWorkbenchChat("exp-1", "PlasmoDB"));

      // Wait for auto-trigger
      await waitFor(() => {
        expect(mockStreamChat).toHaveBeenCalled();
      });

      // Simulate a workbench_gene_set event
      act(() => {
        capturedOnMessage({
          type: "workbench_gene_set",
          data: {
            geneSet: {
              id: "gs-new-1",
              name: "AI-derived set",
              geneCount: 42,
              source: "derived",
              siteId: "PlasmoDB",
            },
          },
        });
      });

      expect(mockAddGeneSet).toHaveBeenCalledWith(
        expect.objectContaining({
          id: "gs-new-1",
          name: "AI-derived set",
          geneCount: 42,
          source: "derived",
          siteId: "PlasmoDB",
          geneIds: [],
          stepCount: 1,
        }),
      );
    });

    it("maps invalid source values to 'derived'", async () => {
      let capturedOnMessage!: (event: ChatSSEEvent) => void;
      mockStreamChat.mockImplementation(
        (
          _experimentId: string,
          _message: string,
          _siteId: string,
          callbacks: { onMessage: (event: ChatSSEEvent) => void },
        ) => {
          capturedOnMessage = callbacks.onMessage;
          return {
            promise: Promise.resolve({
              operationId: "op-1",
              streamId: "s-1",
            }),
            cancel: vi.fn(),
          };
        },
      );

      renderHook(() => useWorkbenchChat("exp-1", "PlasmoDB"));

      await waitFor(() => {
        expect(mockStreamChat).toHaveBeenCalled();
      });

      act(() => {
        capturedOnMessage({
          type: "workbench_gene_set",
          data: {
            geneSet: {
              id: "gs-2",
              name: "Weird Source",
              geneCount: 10,
              source: "unknown_source",
              siteId: "ToxoDB",
            },
          },
        });
      });

      expect(mockAddGeneSet).toHaveBeenCalledWith(
        expect.objectContaining({
          source: "derived",
        }),
      );
    });

    it("does not call addGeneSet when geneSet data is missing", async () => {
      let capturedOnMessage!: (event: ChatSSEEvent) => void;
      mockStreamChat.mockImplementation(
        (
          _experimentId: string,
          _message: string,
          _siteId: string,
          callbacks: { onMessage: (event: ChatSSEEvent) => void },
        ) => {
          capturedOnMessage = callbacks.onMessage;
          return {
            promise: Promise.resolve({
              operationId: "op-1",
              streamId: "s-1",
            }),
            cancel: vi.fn(),
          };
        },
      );

      renderHook(() => useWorkbenchChat("exp-1", "PlasmoDB"));

      await waitFor(() => {
        expect(mockStreamChat).toHaveBeenCalled();
      });

      act(() => {
        capturedOnMessage({
          type: "workbench_gene_set",
          data: {},
        });
      });

      expect(mockAddGeneSet).not.toHaveBeenCalled();
    });
  });
});
