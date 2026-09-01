/**
 * @vitest-environment jsdom
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

const route = { pathname: "/plasmodb/conversation/abc-123" };

vi.mock("next/navigation", () => ({
  usePathname: () => route.pathname,
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/lib/api/sites", () => ({
  sitesOptions: () => ({
    queryKey: ["sites"],
    queryFn: () => [],
  }),
}));

import { AppNavRail } from "./AppNavRail";

function draw() {
  return render(
    <AppNavRail
      siteId="plasmodb"
      onSiteChange={() => undefined}
      onOpenSettings={() => undefined}
      onOpenModelSettings={() => undefined}
      onToggleSidebar={() => undefined}
      sidebarExpanded={false}
    />,
  );
}

afterEach(cleanup);

describe("AppNavRail section links", () => {
  it("does nothing on the section the reader is already in", async () => {
    route.pathname = "/plasmodb/conversation/abc-123";
    draw();
    const chat = await screen.findByRole("link", { name: "Chat" });
    expect(chat).toHaveAttribute("aria-current", "page");
    const click = fireEvent.click(chat);
    expect(click).toBe(false);
  });

  it("navigates to a section the reader is not in", async () => {
    route.pathname = "/plasmodb/conversation/abc-123";
    draw();
    const workbench = await screen.findByRole("link", { name: "Workbench" });
    expect(workbench).not.toHaveAttribute("aria-current");
    const click = fireEvent.click(workbench);
    expect(click).toBe(true);
  });
});
