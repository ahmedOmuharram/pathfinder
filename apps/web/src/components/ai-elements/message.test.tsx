/**
 * @vitest-environment jsdom
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MessageAction } from "./message";

describe("a message action button", () => {
  it("carries the tooltip as its accessible name", () => {
    render(
      <MessageAction tooltip="Copy response">
        <svg aria-hidden />
      </MessageAction>,
    );
    const button = screen.getByRole("button", { name: "Copy response" });
    expect(button.getAttribute("aria-label")).toBe("Copy response");
  });

  it("prefers an explicit label over the tooltip", () => {
    render(
      <MessageAction tooltip="Branch to a new chat from here" label="Branch">
        <svg aria-hidden />
      </MessageAction>,
    );
    expect(screen.getByRole("button", { name: "Branch" })).toBeDefined();
  });

  it("names a button that has no tooltip", () => {
    render(
      <MessageAction label="Regenerate">
        <svg aria-hidden />
      </MessageAction>,
    );
    expect(
      screen.getByRole("button", { name: "Regenerate" }).getAttribute("aria-label"),
    ).toBe("Regenerate");
  });
});
