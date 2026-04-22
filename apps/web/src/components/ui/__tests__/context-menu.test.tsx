/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";

import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";

describe("ContextMenu", () => {
  it("opens on right-click and closes on Escape", async () => {
    const user = userEvent.setup();
    render(
      <ContextMenu>
        <ContextMenuTrigger>Right-click target</ContextMenuTrigger>
        <ContextMenuContent>
          <ContextMenuItem>Menu item one</ContextMenuItem>
        </ContextMenuContent>
      </ContextMenu>,
    );

    expect(screen.queryByText("Menu item one")).toBeNull();

    fireEvent.contextMenu(screen.getByText("Right-click target"));

    expect(screen.getByText("Menu item one")).toBeInTheDocument();

    await user.keyboard("{Escape}");

    expect(screen.queryByText("Menu item one")).toBeNull();
  });
});
