// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type * as SitesApi from "@/lib/api/sites";
import { createTestWrapper } from "@/lib/query/testing";

vi.mock("@/lib/api/sites", async () => {
  const actual = await vi.importActual<typeof SitesApi>("@/lib/api/sites");
  return {
    ...actual,
    searchesOptions: () => ({
      queryKey: ["sites", "x", "searches", "gene"],
      queryFn: async () => [],
      enabled: true,
    }),
  };
});

vi.mock("@/features/strategy/mutations", () => ({
  useAddStepMutation: () => ({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
  }),
}));

import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  afterEach(() => cleanup());

  it("renders heading + description + add button", () => {
    const { Wrapper } = createTestWrapper();
    render(
      <Wrapper>
        <EmptyState siteId="plasmodb" recordType="gene" conversationId="strategy-1" />
      </Wrapper>,
    );
    expect(screen.getByTestId("strategy-empty-state")).toBeTruthy();
    expect(screen.getByText(/Your strategy is empty/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /add step/i })).toBeTruthy();
  });

  it("Add button opens the AddStepSheet", () => {
    const { Wrapper } = createTestWrapper();
    render(
      <Wrapper>
        <EmptyState siteId="plasmodb" recordType="gene" conversationId="strategy-1" />
      </Wrapper>,
    );
    fireEvent.click(screen.getByRole("button", { name: /add step/i }));
    expect(screen.getByTestId("add-step-sheet")).toBeTruthy();
  });
});
