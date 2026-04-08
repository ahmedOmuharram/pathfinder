// @vitest-environment jsdom
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { ChatInputBar } from "@/features/chat/components/ChatInputBar";

// Stub MessageComposer to avoid its internal dependencies
vi.mock("@/features/chat/components/MessageComposer", () => ({
  MessageComposer: ({
    onSend,
    disabled,
  }: {
    onSend: (msg: string) => void;
    disabled?: boolean;
  }) => (
    <div data-testid="message-composer">
      <button
        data-testid="mock-send"
        disabled={disabled}
        onClick={() => onSend("hello")}
      >
        Send
      </button>
    </div>
  ),
}));

// Stub DraftSelectionBar
vi.mock("@/features/chat/components/delegation/DraftSelectionBar", () => ({
  DraftSelectionBar: ({ onRemove }: { onRemove: () => void }) => (
    <div data-testid="draft-bar">
      <button data-testid="remove-draft" onClick={onRemove}>
        Remove
      </button>
    </div>
  ),
}));

const baseProps = {
  apiError: null,
  onDismissError: vi.fn(),
  draftSelection: null,
  onRemoveDraft: vi.fn(),
  onSend: vi.fn(),
  isStreaming: false,
  onStop: vi.fn(),
  siteId: "PlasmoDB",
};

describe("ChatInputBar", () => {
  afterEach(cleanup);

  it("renders the message composer", () => {
    render(<ChatInputBar {...baseProps} />);
    expect(screen.getByTestId("message-composer")).toBeTruthy();
  });

  it("hides the error banner when apiError is null", () => {
    render(<ChatInputBar {...baseProps} />);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("shows the error banner with dismiss button when apiError is set", () => {
    const onDismiss = vi.fn();
    render(
      <ChatInputBar
        {...baseProps}
        apiError="Something went wrong"
        onDismissError={onDismiss}
      />,
    );
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("Something went wrong");

    fireEvent.click(screen.getByLabelText("Dismiss error"));
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it("hides the draft selection bar when draftSelection is null", () => {
    render(<ChatInputBar {...baseProps} />);
    expect(screen.queryByTestId("draft-bar")).toBeNull();
  });

  it("shows the draft selection bar and calls onRemoveDraft", () => {
    const onRemoveDraft = vi.fn();
    const draftSelection = {
      nodes: [{ id: "1", searchName: "GeneByTaxon", displayName: "Genes by taxon" }],
      nodeIds: ["1"],
      selectedNodeIds: ["1"],
      contextNodeIds: [],
      edges: [],
    };
    render(
      <ChatInputBar
        {...baseProps}
        draftSelection={draftSelection}
        onRemoveDraft={onRemoveDraft}
      />,
    );
    expect(screen.getByTestId("draft-bar")).toBeTruthy();

    fireEvent.click(screen.getByTestId("remove-draft"));
    expect(onRemoveDraft).toHaveBeenCalledOnce();
  });
});
