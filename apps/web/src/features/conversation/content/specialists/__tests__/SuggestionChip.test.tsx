/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import * as specialistsApi from "@/lib/api/specialists";
import { createTestWrapper } from "@/lib/query/testing";

import { SuggestionChip } from "../SuggestionChip";

vi.mock("next/navigation", () => ({
  usePathname: () => "/plasmodb/conversation/conv-1",
}));

describe("SuggestionChip", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the validate label", () => {
    const { Wrapper } = createTestWrapper();
    render(
      <Wrapper>
        <SuggestionChip kind="validate" conversationId="conv-1" />
      </Wrapper>,
    );
    const chip = screen.getByTestId("data-specialist-suggestion-chip");
    expect(chip).toBeInTheDocument();
    expect(chip.getAttribute("data-kind")).toBe("validate");
    expect(chip.textContent).toContain("/validate");
  });

  it("renders the research label", () => {
    const { Wrapper } = createTestWrapper();
    render(
      <Wrapper>
        <SuggestionChip kind="research" conversationId="conv-1" />
      </Wrapper>,
    );
    const chip = screen.getByTestId("data-specialist-suggestion-chip");
    expect(chip.getAttribute("data-kind")).toBe("research");
    expect(chip.textContent).toContain("/research");
  });

  it("calls enterSpecialist on click and invokes onEntered", async () => {
    const enterSpy = vi
      .spyOn(specialistsApi, "enterSpecialist")
      .mockResolvedValue({
        messageId: "11111111-1111-1111-1111-111111111111",
        kind: "validate",
        modelId: "",
        context: {
          kind: "validate",
          strategyName: "",
          steps: [],
          userSuccessCriteria: "",
          priorControlTestRuns: [],
          relevantMemories: [],
          recentTurns: [],
        },
      });
    const onEntered = vi.fn();
    const { Wrapper } = createTestWrapper();
    render(
      <Wrapper>
        <SuggestionChip
          kind="validate"
          conversationId="conv-1"
          onEntered={onEntered}
        />
      </Wrapper>,
    );
    const chip = screen.getByTestId("data-specialist-suggestion-chip");
    fireEvent.click(chip);
    await waitFor(() => {
      expect(enterSpy).toHaveBeenCalledWith({
        conversationId: "conv-1",
        kind: "validate",
      });
    });
    await waitFor(() => {
      expect(onEntered).toHaveBeenCalledTimes(1);
    });
  });

  it("disables the chip while the mutation is in flight", async () => {
    let resolveFn: (value: specialistsApi.SpecialistEnterResponse) => void = () => undefined;
    vi.spyOn(specialistsApi, "enterSpecialist").mockImplementation(
      () =>
        new Promise<specialistsApi.SpecialistEnterResponse>((resolve) => {
          resolveFn = resolve;
        }),
    );
    const { Wrapper } = createTestWrapper();
    render(
      <Wrapper>
        <SuggestionChip kind="research" conversationId="conv-1" />
      </Wrapper>,
    );
    const chip = screen.getByTestId<HTMLButtonElement>(
      "data-specialist-suggestion-chip",
    );
    fireEvent.click(chip);
    await waitFor(() => {
      expect(chip.disabled).toBe(true);
    });
    resolveFn({
      messageId: "11111111-1111-1111-1111-111111111111",
      kind: "research",
      modelId: "",
      context: {
        kind: "research",
        researchQuestion: "",
        currentStrategySummary: "",
        relevantMemories: [],
        recentTurns: [],
      },
    });
    await waitFor(() => {
      expect(chip.disabled).toBe(false);
    });
  });
});
