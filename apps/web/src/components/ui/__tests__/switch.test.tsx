/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";

import { Switch } from "@/components/ui/switch";

describe("Switch", () => {
  it("toggles checked state when clicked", async () => {
    const user = userEvent.setup();
    render(<Switch aria-label="Wifi" />);

    const toggle = screen.getByRole("switch", { name: "Wifi" });
    expect(toggle).toHaveAttribute("data-state", "unchecked");

    await user.click(toggle);

    expect(toggle).toHaveAttribute("data-state", "checked");
  });
});
