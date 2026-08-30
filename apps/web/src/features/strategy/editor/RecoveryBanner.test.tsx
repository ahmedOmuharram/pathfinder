// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RecoveryBanner } from "./RecoveryBanner";

describe("RecoveryBanner", () => {
  it("paints the banner from the warning token", () => {
    render(<RecoveryBanner onRestore={() => {}} onDismiss={() => {}} />);
    const banner = screen.getByTestId("step-editor-recovery-banner");
    expect(banner).toHaveClass("border-warning/40", "bg-warning/10", "text-warning");
    expect(banner.className).not.toContain("amber");
  });

  it("restores on demand", async () => {
    const onRestore = vi.fn();
    render(<RecoveryBanner onRestore={onRestore} onDismiss={() => {}} />);
    await userEvent.click(screen.getByTestId("step-editor-recovery-restore"));
    expect(onRestore).toHaveBeenCalledTimes(1);
  });
});
