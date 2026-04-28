/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { SlashPopover } from "@/features/conversation/slash/SlashPopover";
import {
  optimizeCommand,
  researchCommand,
  specialistCommands,
  validateCommand,
} from "../SlashMenu";

function ctx(stepCount: number) {
  return { conversationId: "c1", siteId: "plasmodb", stepCount };
}

describe("specialist slash commands", () => {
  it("registers /optimize, /validate, /research", () => {
    expect(specialistCommands.map((c) => c.name)).toEqual([
      "optimize",
      "validate",
      "research",
    ]);
  });

  it("classifies optimize as launcher and validate/research as specialist-enter", () => {
    expect(optimizeCommand.kind).toBe("launcher");
    expect(validateCommand.kind).toBe("specialist-enter");
    expect(researchCommand.kind).toBe("specialist-enter");
  });

  it("disables /optimize and /validate when stepCount === 0; never disables /research", () => {
    expect(optimizeCommand.disabledReason?.(ctx(0))).not.toBeNull();
    expect(validateCommand.disabledReason?.(ctx(0))).not.toBeNull();
    expect(researchCommand.disabledReason?.(ctx(0)) ?? null).toBeNull();
  });

  it("enables /optimize and /validate when stepCount >= 1", () => {
    expect(optimizeCommand.disabledReason?.(ctx(1)) ?? null).toBeNull();
    expect(validateCommand.disabledReason?.(ctx(3)) ?? null).toBeNull();
  });
});

describe("SlashPopover with specialist commands", () => {
  it("renders all 3 specialist entries", () => {
    render(
      <SlashPopover
        open
        query=""
        commands={specialistCommands}
        ctx={ctx(2)}
        onSelect={() => undefined}
        onDismiss={() => undefined}
      />,
    );
    expect(screen.getByTestId("slash-item-optimize")).toBeInTheDocument();
    expect(screen.getByTestId("slash-item-validate")).toBeInTheDocument();
    expect(screen.getByTestId("slash-item-research")).toBeInTheDocument();
  });

  it("disables /optimize and /validate when stepCount === 0", () => {
    render(
      <SlashPopover
        open
        query=""
        commands={specialistCommands}
        ctx={ctx(0)}
        onSelect={() => undefined}
        onDismiss={() => undefined}
      />,
    );
    expect(screen.getByTestId("slash-item-optimize")).toHaveAttribute(
      "data-disabled",
      "true",
    );
    expect(screen.getByTestId("slash-item-validate")).toHaveAttribute(
      "data-disabled",
      "true",
    );
    expect(screen.getByTestId("slash-item-research")).not.toHaveAttribute(
      "data-disabled",
    );
  });

  it("does not call onSelect for a disabled item on click", () => {
    const onSelect = vi.fn();
    render(
      <SlashPopover
        open
        query=""
        commands={specialistCommands}
        ctx={ctx(0)}
        onSelect={onSelect}
        onDismiss={() => undefined}
      />,
    );
    fireEvent.click(screen.getByTestId("slash-item-optimize"));
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("calls onSelect for an enabled item on click", () => {
    const onSelect = vi.fn();
    render(
      <SlashPopover
        open
        query=""
        commands={specialistCommands}
        ctx={ctx(2)}
        onSelect={onSelect}
        onDismiss={() => undefined}
      />,
    );
    fireEvent.click(screen.getByTestId("slash-item-validate"));
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect.mock.calls[0]?.[0].name).toBe("validate");
  });
});
