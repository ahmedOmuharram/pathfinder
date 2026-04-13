// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { ChatInput } from "./ChatInput";

describe("ChatInput", () => {
  it("calls onSubmit with textarea value when the Send button is clicked", () => {
    const onSubmit = vi.fn();
    render(<ChatInput onSubmit={onSubmit} onStop={() => {}} disabled={false} />);

    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "hello" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith("hello");
  });

  it("swaps to a Stop button when disabled (streaming)", () => {
    render(<ChatInput onSubmit={() => {}} onStop={() => {}} disabled={true} />);
    expect(screen.getByRole("button", { name: /stop/i })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /send/i })).toBeNull();
  });

  it("calls onStop when the Stop button is clicked", () => {
    const onStop = vi.fn();
    render(<ChatInput onSubmit={() => {}} onStop={onStop} disabled={true} />);
    fireEvent.click(screen.getByRole("button", { name: /stop/i }));
    expect(onStop).toHaveBeenCalledTimes(1);
  });
});
