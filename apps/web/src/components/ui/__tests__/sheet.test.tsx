/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

function Subject() {
  return (
    <Sheet>
      <SheetTrigger>Open sheet</SheetTrigger>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Title here</SheetTitle>
          <SheetDescription>Description here</SheetDescription>
        </SheetHeader>
        <p>Body content</p>
      </SheetContent>
    </Sheet>
  );
}

describe("Sheet", () => {
  it("opens and closes on trigger click", async () => {
    const user = userEvent.setup();
    render(<Subject />);

    expect(screen.queryByText("Title here")).toBeNull();

    await user.click(screen.getByText("Open sheet"));

    expect(screen.getByText("Title here")).toBeInTheDocument();
    expect(screen.getByText("Body content")).toBeInTheDocument();

    await user.keyboard("{Escape}");

    expect(screen.queryByText("Title here")).toBeNull();
  });
});
