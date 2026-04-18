/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { Toaster } from "sonner";

import { toast } from "./toast";

describe("toast wrapper", () => {
  beforeEach(() => {
    render(<Toaster />);
  });
  afterEach(() => cleanup());

  it("renders a success toast with check icon and description", async () => {
    toast({ type: "success", description: "Saved." });
    const toastEl = await screen.findByTestId("toast");
    expect(toastEl).toBeInTheDocument();
    expect(toastEl).toHaveTextContent("Saved.");
  });

  it("renders an error toast with warning icon and description", async () => {
    toast({ type: "error", description: "Failed." });
    const toastEl = await screen.findByTestId("toast");
    expect(toastEl).toHaveTextContent("Failed.");
  });

  it("single-line descriptions get items-center alignment", async () => {
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        disconnect() {}
      },
    );
    Object.defineProperty(HTMLElement.prototype, "scrollHeight", {
      configurable: true,
      get() {
        return 20;
      },
    });
    vi.spyOn(window, "getComputedStyle").mockReturnValue({
      lineHeight: "20",
    } as unknown as CSSStyleDeclaration);

    toast({ type: "info", description: "One line." });
    const toastEl = await screen.findByTestId("toast");
    await waitFor(() => {
      expect(toastEl.className).toMatch(/items-center/);
    });
  });

  it("multi-line descriptions get items-start alignment", async () => {
    vi.stubGlobal(
      "ResizeObserver",
      class {
        cb: () => void;
        constructor(cb: () => void) {
          this.cb = cb;
          this.cb();
        }
        observe() {}
        disconnect() {}
      },
    );
    Object.defineProperty(HTMLElement.prototype, "scrollHeight", {
      configurable: true,
      get() {
        return 60;
      },
    });
    vi.spyOn(window, "getComputedStyle").mockReturnValue({
      lineHeight: "20",
    } as unknown as CSSStyleDeclaration);

    toast({
      type: "error",
      description:
        "This is a very long error that should wrap across multiple lines.",
    });
    const toastEl = await screen.findByTestId("toast");
    await waitFor(() => {
      expect(toastEl.className).toMatch(/items-start/);
    });
  });
});
