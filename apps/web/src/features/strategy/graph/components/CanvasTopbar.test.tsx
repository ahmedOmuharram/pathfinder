// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { Strategy } from "@pathfinder/shared";
import type * as ConvApi from "@/lib/api/conversations";
import { createTestWrapper } from "@/lib/query/testing";
import { CanvasTopbar } from "./CanvasTopbar";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn(), back: vi.fn() }),
  usePathname: () => "/conversation/conv-1/strategy",
}));

vi.mock("@/lib/api/conversations", async (importOriginal) => {
  const actual = await importOriginal<typeof ConvApi>();
  return {
    ...actual,
    pushConversation: vi.fn(async (_id: string, body: { name: string }) => ({
      ...STRATEGY,
      name: body.name,
    })),
    computeStepCounts: vi.fn(async () => ({ counts: {} })),
  };
});

const STRATEGY: Strategy = {
  id: "conv-1",
  name: "My strategy",
  siteId: "plasmodb",
  recordType: "gene",
  steps: [
    {
      id: "step_1",
      kind: "search",
      displayName: "Genes by taxon",
      searchName: "GenesByTaxon",
      recordType: "gene",
      parameters: {},
      isBuilt: false,
      isFiltered: false,
    },
  ],
  rootStepId: "step_1",
  isSaved: false,
  createdAt: "2026-01-01T00:00:00.000Z",
  updatedAt: "2026-01-01T00:00:00.000Z",
};

describe("CanvasTopbar", () => {
  afterEach(() => {
    cleanup();
    pushMock.mockReset();
  });

  it("renders strategy name in an editable input", () => {
    const { Wrapper } = createTestWrapper();
    render(
      <Wrapper>
        <CanvasTopbar
          strategy={STRATEGY}
          conversationId="conv-1"
          syncState="idle"
          onRetry={() => {}}
        />
      </Wrapper>,
    );
    const input = screen.getByLabelText<HTMLInputElement>("Strategy name");
    expect(input.value).toBe("My strategy");
  });

  it("Back button routes to conversation parent", () => {
    const { Wrapper } = createTestWrapper();
    render(
      <Wrapper>
        <CanvasTopbar
          strategy={STRATEGY}
          conversationId="conv-1"
          syncState="idle"
          onRetry={() => {}}
        />
      </Wrapper>,
    );
    fireEvent.click(screen.getByRole("button", { name: /back to chat/i }));
    expect(pushMock).toHaveBeenCalledWith("/plasmodb/conversation/conv-1");
  });

  it("renders sync status reflecting saving / error / paused / idle", () => {
    const { Wrapper } = createTestWrapper();
    const { rerender } = render(
      <Wrapper>
        <CanvasTopbar
          strategy={STRATEGY}
          conversationId="conv-1"
          syncState="saving"
          onRetry={() => {}}
        />
      </Wrapper>,
    );
    expect(screen.getByText(/Saving/i)).toBeTruthy();

    rerender(
      <Wrapper>
        <CanvasTopbar
          strategy={STRATEGY}
          conversationId="conv-1"
          syncState="error"
          onRetry={() => {}}
        />
      </Wrapper>,
    );
    expect(screen.getByRole("button", { name: /failed.*retry/i })).toBeTruthy();

    rerender(
      <Wrapper>
        <CanvasTopbar
          strategy={STRATEGY}
          conversationId="conv-1"
          syncState="paused"
          onRetry={() => {}}
        />
      </Wrapper>,
    );
    expect(screen.getByText(/Sync paused/i)).toBeTruthy();

    rerender(
      <Wrapper>
        <CanvasTopbar
          strategy={STRATEGY}
          conversationId="conv-1"
          syncState="idle"
          onRetry={() => {}}
        />
      </Wrapper>,
    );
    expect(screen.getByText(/^Saved$/i)).toBeTruthy();
  });
});
