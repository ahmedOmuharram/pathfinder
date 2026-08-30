// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OrphanNotice } from "./OrphanNotice";

describe("OrphanNotice", () => {
  it("renders nothing when count <= 0", () => {
    const { container } = render(<OrphanNotice count={0} firstOrphanId={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("shows the count and singular/plural form", () => {
    render(<OrphanNotice count={1} firstOrphanId="o1" />);
    expect(screen.getByText(/1 disconnected step/)).toBeTruthy();

    render(<OrphanNotice count={3} firstOrphanId="o1" />);
    expect(screen.getByText(/3 disconnected steps/)).toBeTruthy();
  });

  it("paints the notice from the warning token with no alpha on its text", () => {
    render(<OrphanNotice count={2} firstOrphanId="o1" />);
    const notice = screen.getByTestId("orphan-notice");
    expect(notice).toHaveClass("border-warning/40", "bg-warning/10", "text-warning");
    expect(notice.className).not.toContain("amber");
    expect(notice.className).not.toContain("text-warning/");
  });

  it("calls onClickFirst when View is clicked", async () => {
    const onClickFirst = vi.fn();
    render(
      <OrphanNotice count={2} firstOrphanId="step-7" onClickFirst={onClickFirst} />,
    );
    const view = screen.getByRole("button", { name: /View/i });
    await userEvent.click(view);
    expect(onClickFirst).toHaveBeenCalledWith("step-7");
  });

  it("calls onRemoveAll when Remove all is clicked", async () => {
    const onRemoveAll = vi.fn();
    render(<OrphanNotice count={2} firstOrphanId={null} onRemoveAll={onRemoveAll} />);
    const remove = screen.getByRole("button", { name: /Remove all/i });
    await userEvent.click(remove);
    expect(onRemoveAll).toHaveBeenCalledTimes(1);
  });
});
