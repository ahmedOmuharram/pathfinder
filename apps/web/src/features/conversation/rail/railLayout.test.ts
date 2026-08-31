import { describe, expect, it } from "vitest";

import {
  MIN_CHAT_COLUMN_WIDTH,
  chatColumnWidth,
  shouldOverlayRailPanel,
} from "./railLayout";

describe("the rail panel overlays rather than squeezing the chat", () => {
  it("leaves the chat 54px at 866px with the list and a panel open", () => {
    expect(
      chatColumnWidth({ viewportWidth: 866, listExpanded: true, panelOpen: true }),
    ).toBe(54);
  });

  it("overlays at that width", () => {
    expect(
      shouldOverlayRailPanel({
        viewportWidth: 866,
        listExpanded: true,
        panelOpen: true,
      }),
    ).toBe(true);
  });

  it("overlays at 866px even with the list collapsed", () => {
    expect(
      chatColumnWidth({ viewportWidth: 866, listExpanded: false, panelOpen: true }),
    ).toBe(418);
    expect(
      shouldOverlayRailPanel({
        viewportWidth: 866,
        listExpanded: false,
        panelOpen: true,
      }),
    ).toBe(true);
  });

  it("squeezes on a wide screen, where the chat still reads", () => {
    expect(
      chatColumnWidth({ viewportWidth: 1440, listExpanded: true, panelOpen: true }),
    ).toBe(628);
    expect(
      shouldOverlayRailPanel({
        viewportWidth: 1440,
        listExpanded: true,
        panelOpen: true,
      }),
    ).toBe(false);
  });

  it("never overlays when no panel is open", () => {
    expect(
      shouldOverlayRailPanel({
        viewportWidth: 320,
        listExpanded: true,
        panelOpen: false,
      }),
    ).toBe(false);
  });

  it("keeps the panel in flow before the page has measured itself", () => {
    expect(
      shouldOverlayRailPanel({
        viewportWidth: Number.NaN,
        listExpanded: true,
        panelOpen: true,
      }),
    ).toBe(false);
  });

  it("switches exactly at the minimum chat width", () => {
    const viewportWidth = 44 + 44 + 360 + MIN_CHAT_COLUMN_WIDTH;
    expect(
      shouldOverlayRailPanel({ viewportWidth, listExpanded: false, panelOpen: true }),
    ).toBe(false);
    expect(
      shouldOverlayRailPanel({
        viewportWidth: viewportWidth - 1,
        listExpanded: false,
        panelOpen: true,
      }),
    ).toBe(true);
  });
});
