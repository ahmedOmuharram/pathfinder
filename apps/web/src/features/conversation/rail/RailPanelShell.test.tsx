// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { RailPanelShell } from "./RailPanelShell";

afterEach(() => {
  cleanup();
});

describe("RailPanelShell", () => {
  it("gives the scrolling body a tab stop named after the panel", () => {
    render(
      <RailPanelShell title="Tasks">
        <p>no focusable content</p>
      </RailPanelShell>,
    );

    const body = screen.getByRole("region", { name: "Tasks detail" });
    expect(body).toHaveAttribute("tabindex", "0");
    expect(body).toHaveTextContent("no focusable content");
  });
});
