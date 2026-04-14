// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { useStrategyStore } from "@/state/strategy/store";
import { ChatInput } from "./ChatInput";

vi.mock("@/lib/query/hooks/useGeneSetsQuery", () => ({
  useGeneSetsQuery: () => ({
    data: [
      { id: "gs_1", name: "Drug targets", geneCount: 42 },
      { id: "gs_2", name: "Liver stage hits", geneCount: 87 },
    ],
  }),
}));

function renderInput(props: Partial<Parameters<typeof ChatInput>[0]> = {}) {
  const onSubmit = props.onSubmit ?? vi.fn();
  const onStop = props.onStop ?? vi.fn();
  const disabled = props.disabled ?? false;
  const client = new QueryClient();
  render(
    <QueryClientProvider client={client}>
      <ChatInput onSubmit={onSubmit} onStop={onStop} disabled={disabled} />
    </QueryClientProvider>,
  );
  return { onSubmit, onStop };
}

function getTextarea(): HTMLTextAreaElement {
  const el = screen.getByRole("textbox");
  if (!(el instanceof HTMLTextAreaElement)) {
    throw new Error("expected a textarea");
  }
  return el;
}

function typeChar(textarea: HTMLElement, char: string) {
  const ta = textarea as HTMLTextAreaElement;
  const cursor = ta.selectionStart;
  const next = ta.value.slice(0, cursor) + char + ta.value.slice(cursor);
  fireEvent.keyDown(ta, { key: char });
  fireEvent.change(ta, { target: { value: next } });
  ta.setSelectionRange(cursor + 1, cursor + 1);
}

function typeString(textarea: HTMLElement, str: string) {
  for (const ch of str) {
    typeChar(textarea, ch);
  }
}

beforeEach(() => {
  useStrategyStore.setState({
    strategy: {
      id: "strat_123",
      name: "My strategy",
    } as unknown as ReturnType<typeof useStrategyStore.getState>["strategy"],
    stepsById: {
      step_a: {
        id: "step_a",
        searchName: "GenesByText",
        displayName: "Find seed genes",
      } as unknown as ReturnType<typeof useStrategyStore.getState>["stepsById"]["step_a"],
    },
  });
});

afterEach(() => {
  cleanup();
  useStrategyStore.getState().clear();
});

describe("ChatInput @-mentions", () => {
  it("opens the mention dropdown when @ is typed at a word boundary", () => {
    renderInput();
    const textarea = getTextarea();
    typeChar(textarea, "@");
    expect(screen.queryByTestId("mention-dropdown")).toBeInTheDocument();
  });

  it("filters candidates as the user types after @", () => {
    renderInput();
    const textarea = getTextarea();
    typeString(textarea, "@liver");
    expect(screen.queryByTestId("mention-option-geneset-gs_2")).toBeInTheDocument();
    expect(screen.queryByTestId("mention-option-geneset-gs_1")).not.toBeInTheDocument();
  });

  it("inserts a machine-readable token when a candidate is clicked", () => {
    renderInput();
    const textarea = getTextarea();
    typeString(textarea, "use @step");
    const option = screen.getByTestId("mention-option-step-step_a");
    fireEvent.mouseDown(option);
    expect(textarea.value).toContain("@step:step_a");
  });

  it("closes the dropdown when space is typed inside the query", () => {
    renderInput();
    const textarea = getTextarea();
    typeString(textarea, "@liver hello");
    expect(screen.queryByTestId("mention-dropdown")).not.toBeInTheDocument();
  });

  it("ArrowDown then Enter inserts the active candidate", () => {
    renderInput();
    const textarea = getTextarea();
    typeChar(textarea, "@");
    fireEvent.keyDown(textarea, { key: "ArrowDown" });
    fireEvent.keyDown(textarea, { key: "Enter" });
    expect(textarea.value).toMatch(/@(step|geneset|strategy):/);
  });

  it("submits the typed text via the form", async () => {
    const onSubmit = vi.fn();
    renderInput({ onSubmit });
    const textarea = getTextarea();
    typeString(textarea, "hello world");
    const form = textarea.closest("form");
    if (form === null) throw new Error("form not found");
    fireEvent.submit(form);
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith("hello world");
    });
  });

  it("Escape closes the dropdown without inserting", () => {
    renderInput();
    const textarea = getTextarea();
    typeString(textarea, "@step");
    fireEvent.keyDown(textarea, { key: "Escape" });
    expect(screen.queryByTestId("mention-dropdown")).not.toBeInTheDocument();
  });
});
