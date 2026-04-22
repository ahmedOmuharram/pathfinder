/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

describe("ToggleGroup", () => {
  it("selects exclusive items with type=single", async () => {
    const user = userEvent.setup();
    render(
      <ToggleGroup type="single" defaultValue="a">
        <ToggleGroupItem value="a">Alpha</ToggleGroupItem>
        <ToggleGroupItem value="b">Beta</ToggleGroupItem>
      </ToggleGroup>,
    );

    const alpha = screen.getByRole("radio", { name: "Alpha" });
    const beta = screen.getByRole("radio", { name: "Beta" });

    expect(alpha).toHaveAttribute("data-state", "on");
    expect(beta).toHaveAttribute("data-state", "off");

    await user.click(beta);

    expect(beta).toHaveAttribute("data-state", "on");
    expect(alpha).toHaveAttribute("data-state", "off");
  });
});
