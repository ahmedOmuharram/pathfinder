/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";

import { Checkbox } from "@/components/ui/checkbox";

describe("Checkbox", () => {
  it("toggles on click", async () => {
    const user = userEvent.setup();
    const onCheckedChange = vi.fn();
    render(<Checkbox onCheckedChange={onCheckedChange} aria-label="A" />);

    await user.click(screen.getByLabelText("A"));

    expect(onCheckedChange).toHaveBeenCalledWith(true);
  });

  it("renders checked state", () => {
    render(<Checkbox checked aria-label="A" />);
    const cb = screen.getByLabelText("A");
    expect(cb.getAttribute("data-state")).toBe("checked");
  });

  it("renders indeterminate state", () => {
    render(<Checkbox checked="indeterminate" aria-label="A" />);
    const cb = screen.getByLabelText("A");
    expect(cb.getAttribute("data-state")).toBe("indeterminate");
  });
});
