// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { UNRESOLVED_SERIES_COLOR } from "@/lib/components/charts/unresolved";
import { readChartRoleColors } from "./chartTheme";

afterEach(() => document.documentElement.removeAttribute("style"));

function setSeries(): void {
  const root = document.documentElement;
  root.style.setProperty("--chart-1", "215 75% 45%");
  root.style.setProperty("--chart-2", "160 65% 33%");
  root.style.setProperty("--chart-3", "28 85% 42%");
  root.style.setProperty("--chart-4", "355 70% 45%");
  root.style.setProperty("--chart-5", "275 55% 50%");
  root.style.setProperty("--chart-6", "192 80% 33%");
  root.style.setProperty("--chart-positive", "160 65% 33%");
  root.style.setProperty("--chart-negative", "355 70% 45%");
}

describe("readChartRoleColors", () => {
  it("maps every role onto the resolved chart token", () => {
    setSeries();
    expect(readChartRoleColors()).toEqual({
      positive: "hsl(160 65% 33%)",
      negative: "hsl(355 70% 45%)",
      primary: "hsl(215 75% 45%)",
      secondary: "hsl(160 65% 33%)",
      warning: "hsl(28 85% 42%)",
      destructive: "hsl(355 70% 45%)",
      purple: "hsl(275 55% 50%)",
      cyan: "hsl(192 80% 33%)",
    });
  });

  it("follows the ground the document is on", () => {
    setSeries();
    const light = readChartRoleColors().primary;
    document.documentElement.style.setProperty("--chart-1", "210 90% 70%");
    expect(readChartRoleColors().primary).toBe("hsl(210 90% 70%)");
    expect(readChartRoleColors().primary).not.toBe(light);
  });

  it("paints the unresolved neutral when the stylesheet defines nothing", () => {
    const colors = readChartRoleColors();
    expect(colors.primary).toBe(UNRESOLVED_SERIES_COLOR);
    expect(colors.positive).toBe(UNRESOLVED_SERIES_COLOR);
  });
});
