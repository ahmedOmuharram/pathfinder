/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";

import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

describe("Popover", () => {
  it("toggles content visibility when trigger is clicked", async () => {
    const user = userEvent.setup();
    render(
      <Popover>
        <PopoverTrigger>Open popover</PopoverTrigger>
        <PopoverContent>Popover body</PopoverContent>
      </Popover>,
    );

    expect(screen.queryByText("Popover body")).toBeNull();

    await user.click(screen.getByText("Open popover"));

    expect(screen.getByText("Popover body")).toBeInTheDocument();

    await user.keyboard("{Escape}");

    expect(screen.queryByText("Popover body")).toBeNull();
  });
});
