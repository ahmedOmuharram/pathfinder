// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

let pathnameMock = "/plasmodb/conversation/conv-1";
vi.mock("next/navigation", () => ({
  usePathname: () => pathnameMock,
}));

import { chatRoot, workbenchRoot } from "@/lib/routes";
import { EmbeddedToolbar } from "./EmbeddedToolbar";

function renderToolbar() {
  return render(<EmbeddedToolbar siteId="plasmodb" onOpenSettings={vi.fn()} />);
}

describe("EmbeddedToolbar", () => {
  afterEach(() => {
    cleanup();
    pathnameMock = "/plasmodb/conversation/conv-1";
  });

  it("points the chat link at the site's chat root", () => {
    renderToolbar();
    expect(screen.getByLabelText("Go to Chat")).toHaveAttribute(
      "href",
      chatRoot("plasmodb"),
    );
    expect(screen.getByLabelText("Go to Workbench")).toHaveAttribute(
      "href",
      workbenchRoot("plasmodb"),
    );
  });

  it("marks chat as the current page anywhere under the chat root", () => {
    renderToolbar();
    expect(screen.getByLabelText("Go to Chat")).toHaveAttribute("aria-current", "page");
    expect(screen.getByLabelText("Go to Workbench")).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("marks the workbench as the current page under the workbench root", () => {
    pathnameMock = "/plasmodb/workbench/gs-1";
    renderToolbar();
    expect(screen.getByLabelText("Go to Workbench")).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByLabelText("Go to Chat")).not.toHaveAttribute("aria-current");
  });

  it("marks neither as current on another site's chat", () => {
    pathnameMock = "/toxodb/conversation/conv-1";
    renderToolbar();
    expect(screen.getByLabelText("Go to Chat")).not.toHaveAttribute("aria-current");
    expect(screen.getByLabelText("Go to Workbench")).not.toHaveAttribute(
      "aria-current",
    );
  });
});
