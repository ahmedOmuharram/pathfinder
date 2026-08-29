// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn(), back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/query/hooks/useAuthRefresh", () => ({
  useAuthRefresh: () => undefined,
}));
vi.mock("@/features/sites/hooks/useSiteTheme", () => ({
  useSiteTheme: () => undefined,
}));
vi.mock("@/app/hooks/useSystemConfig", () => ({
  useSystemConfig: () => ({ setupRequired: false, retry: vi.fn() }),
}));
vi.mock("@/app/hooks/useAutoCollapseSidebar", () => ({
  useAutoCollapseSidebar: () => undefined,
}));
vi.mock("@/app/hooks/useSidebarResize", () => ({
  useSidebarResize: () => ({
    layoutRef: { current: null },
    sidebarWidth: 280,
    isDragging: false,
    startDragging: vi.fn(),
  }),
}));
vi.mock("@/app/hooks/useModalState", () => ({
  useModalState: () => ({
    settingsOpen: false,
    settingsTab: null,
    openSettings: vi.fn(),
    closeSettings: vi.fn(),
  }),
}));
vi.mock("@/app/components/VeupathdbSignInGate", () => ({
  VeupathdbSignInGate: ({ onSiteChange }: { onSiteChange: (site: string) => void }) => (
    <button type="button" onClick={() => onSiteChange("toxodb")}>
      Switch site
    </button>
  ),
}));

import { authStatusOptions } from "@/lib/api/veupathdb-auth";
import { createTestWrapper } from "@/lib/query/testing";
import { chatRoot } from "@/lib/routes";
import AppShellLayout from "./layout";

/** React reads a thenable that already carries its settled value synchronously. */
function settled<T>(value: T): Promise<T> {
  return Object.assign(Promise.resolve(value), { status: "fulfilled", value });
}

describe("AppShellLayout site switch", () => {
  afterEach(() => {
    cleanup();
    pushMock.mockReset();
  });

  it("sends a site change to that site's chat root", async () => {
    const { queryClient, Wrapper } = createTestWrapper();
    queryClient.setQueryData(authStatusOptions("plasmodb").queryKey, {
      signedIn: false,
    });

    render(
      <Wrapper>
        <AppShellLayout params={settled({ siteId: "plasmodb" })}>
          <div />
        </AppShellLayout>
      </Wrapper>,
    );

    await userEvent.click(screen.getByRole("button", { name: "Switch site" }));
    expect(pushMock.mock.calls).toEqual([[chatRoot("toxodb")]]);
    expect(pushMock).toHaveBeenCalledWith("/toxodb/conversation");
  });
});
