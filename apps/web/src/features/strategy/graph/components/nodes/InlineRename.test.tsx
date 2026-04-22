// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { InlineRename } from "./InlineRename";

describe("InlineRename", () => {
  it("shows the static label by default and switches to an input when clicked", async () => {
    const user = userEvent.setup();
    render(
      <InlineRename
        value="Original name"
        onCommit={() => {}}
        onCancel={() => {}}
      />,
    );
    const trigger = screen.getByText("Original name");
    expect(trigger.tagName).not.toBe("INPUT");
    await user.click(trigger);
    const input = screen.getByDisplayValue<HTMLInputElement>("Original name");
    expect(input.tagName).toBe("INPUT");
    expect(document.activeElement).toBe(input);
    expect(input.selectionStart).toBe(0);
    expect(input.selectionEnd).toBe("Original name".length);
  });

  it("commits on Enter and calls onCommit with the new value", async () => {
    const user = userEvent.setup();
    const onCommit = vi.fn();
    render(
      <InlineRename
        value="Original name"
        onCommit={onCommit}
        onCancel={() => {}}
      />,
    );
    await user.click(screen.getByText("Original name"));
    const input = screen.getByDisplayValue<HTMLInputElement>("Original name");
    fireEvent.change(input, { target: { value: "New name" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onCommit).toHaveBeenCalledWith("New name");
  });

  it("cancels on Escape and calls onCancel; does not call onCommit", async () => {
    const user = userEvent.setup();
    const onCommit = vi.fn();
    const onCancel = vi.fn();
    render(
      <InlineRename
        value="Original name"
        onCommit={onCommit}
        onCancel={onCancel}
      />,
    );
    await user.click(screen.getByText("Original name"));
    const input = screen.getByDisplayValue<HTMLInputElement>("Original name");
    fireEvent.change(input, { target: { value: "Changed" } });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onCommit).not.toHaveBeenCalled();
  });

  it("commits on blur with the current value", async () => {
    const user = userEvent.setup();
    const onCommit = vi.fn();
    render(
      <InlineRename
        value="Original name"
        onCommit={onCommit}
        onCancel={() => {}}
      />,
    );
    await user.click(screen.getByText("Original name"));
    const input = screen.getByDisplayValue<HTMLInputElement>("Original name");
    fireEvent.change(input, { target: { value: "Blurred" } });
    await act(async () => {
      input.blur();
    });
    expect(onCommit).toHaveBeenCalledWith("Blurred");
  });
});
