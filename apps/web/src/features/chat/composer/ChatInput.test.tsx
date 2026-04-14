// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { ChatInput } from "./ChatInput";

describe("ChatInput", () => {
  it("calls onSubmit with textarea value when the form is submitted", async () => {
    const onSubmit = vi.fn();
    const { container } = render(
      <ChatInput onSubmit={onSubmit} onStop={() => {}} disabled={false} />,
    );

    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "hello" } });
    const form = container.querySelector("form");
    if (form === null) throw new Error("form not found");
    fireEvent.submit(form);

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith("hello");
    });
  });

  it("swaps to a Stop button when disabled (streaming)", () => {
    render(<ChatInput onSubmit={() => {}} onStop={() => {}} disabled={true} />);
    expect(screen.getByRole("button", { name: /stop/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /submit/i })).not.toBeInTheDocument();
  });

  it("calls onStop when the Stop button is clicked", () => {
    const onStop = vi.fn();
    render(<ChatInput onSubmit={() => {}} onStop={onStop} disabled={true} />);
    fireEvent.click(screen.getByRole("button", { name: /stop/i }));
    expect(onStop).toHaveBeenCalledTimes(1);
  });
});
