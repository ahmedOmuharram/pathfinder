/**
 * @vitest-environment jsdom
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";

import { createTestQueryClient } from "@/lib/query/testing";
import { SitePicker } from "./SitePicker";
import { sitesOptions } from "@/lib/api/sites";

function site(id: string, displayName: string, isPortal: boolean) {
  return {
    id,
    name: displayName,
    displayName,
    baseUrl: `https://${id}.org`,
    projectId: displayName,
    isPortal,
  };
}

const SITES = [
  site("plasmodb", "PlasmoDB", false),
  site("toxodb", "ToxoDB", false),
  site("veupathdb", "VEuPathDB", true),
];

vi.mock("@/lib/api/sites", () => ({
  sitesOptions: () => ({
    queryKey: ["sites"],
    queryFn: () => Promise.resolve(SITES),
  }),
}));

const mockSetSelectedSite = vi.fn();
vi.mock("@/state/useSessionStore", () => ({
  useSessionStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({ setSelectedSite: mockSetSelectedSite }),
}));

function renderPicker(onChange = vi.fn()): { onChange: ReturnType<typeof vi.fn> } {
  const qc = createTestQueryClient();
  qc.setQueryData(sitesOptions().queryKey, SITES);
  const ui: ReactElement = (
    <QueryClientProvider client={qc}>
      <SitePicker value="plasmodb" onChange={onChange} />
    </QueryClientProvider>
  );
  render(ui);
  return { onChange };
}

afterEach(cleanup);
beforeEach(() => mockSetSelectedSite.mockClear());

describe("SitePicker", () => {
  it("groups component sites and the portal under labelled optgroups", async () => {
    renderPicker();
    const select = await screen.findByTestId<HTMLSelectElement>("site-select");

    const component = within(select).getByRole("group", { name: "Component Sites" });
    expect(
      within(component)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["PlasmoDB", "ToxoDB"]);

    const portal = within(select).getByRole("group", { name: "Portal" });
    expect(
      within(portal)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["VEuPathDB"]);
  });

  it("reflects the controlled value as the selected option", async () => {
    renderPicker();
    const select = await screen.findByTestId<HTMLSelectElement>("site-select");
    expect(select.value).toBe("plasmodb");
  });

  it("propagates a change through both onChange and the session store", async () => {
    const { onChange } = renderPicker();
    const select = await screen.findByTestId<HTMLSelectElement>("site-select");

    await userEvent.selectOptions(select, "toxodb");

    await waitFor(() => expect(onChange.mock.calls).toEqual([["toxodb"]]));
    expect(mockSetSelectedSite.mock.calls).toEqual([["toxodb"]]);
  });
});
