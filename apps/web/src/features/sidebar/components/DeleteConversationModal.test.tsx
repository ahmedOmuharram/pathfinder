// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import type { ConversationItem } from "./conversationSidebarTypes";
import { DeleteConversationModal } from "./DeleteConversationModal";

const TARGET: ConversationItem = {
  id: "conv_1",
  kind: "strategy",
  title: "My research thread",
  updatedAt: "2026-04-01T12:00:00Z",
};

afterEach(() => cleanup());

describe("DeleteConversationModal", () => {
  it("does not render when there is no target", () => {
    render(
      <DeleteConversationModal
        target={null}
        isDeleting={false}
        onClose={() => {}}
        onConfirmDelete={() => {}}
      />,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders the conversation title in the confirmation prompt", () => {
    render(
      <DeleteConversationModal
        target={TARGET}
        isDeleting={false}
        onClose={() => {}}
        onConfirmDelete={() => {}}
      />,
    );
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("My research thread");
    expect(dialog).toHaveTextContent(/cannot be undone/i);
  });

  it("calls onClose when Cancel is clicked", () => {
    const onClose = vi.fn();
    render(
      <DeleteConversationModal
        target={TARGET}
        isDeleting={false}
        onClose={onClose}
        onConfirmDelete={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onConfirmDelete when Delete is clicked", () => {
    const onConfirmDelete = vi.fn();
    render(
      <DeleteConversationModal
        target={TARGET}
        isDeleting={false}
        onClose={() => {}}
        onConfirmDelete={onConfirmDelete}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /^delete$/i }));
    expect(onConfirmDelete).toHaveBeenCalledTimes(1);
  });

  it("disables both action buttons and shows in-progress label while deleting", () => {
    render(
      <DeleteConversationModal
        target={TARGET}
        isDeleting={true}
        onClose={() => {}}
        onConfirmDelete={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: /cancel/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /deleting/i })).toBeDisabled();
  });
});
