/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { LoginModal } from "./LoginModal";

describe("LoginModal", () => {
  it("shows the standing invitation and cannot be closed when the login is forced", () => {
    render(<LoginModal open selectedSite="plasmodb" onSiteChange={vi.fn()} />);
    expect(
      screen.getByText(
        "Sign in with your VEuPathDB account to build and manage search strategies.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Close" })).toBeNull();
  });

  it("shows the server's reason and closes when the prompt was requested", () => {
    const onDismiss = vi.fn();
    render(
      <LoginModal
        open
        selectedSite="plasmodb"
        onSiteChange={vi.fn()}
        reason="Sign in to VEuPathDB to use searches, strategies and gene sets."
        onDismiss={onDismiss}
      />,
    );
    expect(
      screen.getByText(
        "Sign in to VEuPathDB to use searches, strategies and gene sets.",
      ),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});
