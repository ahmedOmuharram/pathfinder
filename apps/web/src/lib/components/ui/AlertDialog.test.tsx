/**
 * @vitest-environment jsdom
 */
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { AlertDialog, AlertDialogContent } from "./AlertDialog";

describe("AlertDialog", () => {
  it("scrims with the foreground token at the shared opacity", () => {
    render(
      <AlertDialog open>
        <AlertDialogContent>body</AlertDialogContent>
      </AlertDialog>,
    );
    const overlay = document.querySelector('[data-state="open"].fixed.inset-0');
    expect(overlay).toHaveClass("bg-foreground/50");
    expect(overlay?.className).not.toContain("bg-black");
  });
});
