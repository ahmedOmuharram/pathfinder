/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";

import { Toggle } from "@/components/ui/toggle";

describe("Toggle", () => {
  it("toggles pressed state when clicked", async () => {
    const user = userEvent.setup();
    render(<Toggle aria-label="Toggle bold">Bold</Toggle>);

    const button = screen.getByRole("button", { name: "Toggle bold" });
    expect(button).toHaveAttribute("data-state", "off");

    await user.click(button);

    expect(button).toHaveAttribute("data-state", "on");
  });
});
