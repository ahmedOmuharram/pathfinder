// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { applySiteTheme } from "./siteTheme";

const SITE_IDS = [
  "veupathdb",
  "plasmodb",
  "toxodb",
  "cryptodb",
  "giardiadb",
  "amoebadb",
  "microsporidiadb",
  "piroplasmadb",
  "tritrypdb",
  "fungidb",
  "hostdb",
  "vectorbase",
  "orthomcl",
  "schistodb",
  "trichdb",
];

function parseHsl(value: string): [number, number, number] {
  const match = /^(\d+(?:\.\d+)?) (\d+(?:\.\d+)?)% (\d+(?:\.\d+)?)%$/.exec(
    value.trim(),
  );
  if (match === null) throw new Error(`unexpected --primary format: "${value}"`);
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

function whiteTextContrast(h: number, s: number, l: number): number {
  const sN = s / 100;
  const lN = l / 100;
  const c = (1 - Math.abs(2 * lN - 1)) * sN;
  const hp = h / 60;
  const x = c * (1 - Math.abs((hp % 2) - 1));
  const [r1, g1, b1] =
    hp < 1
      ? [c, x, 0]
      : hp < 2
        ? [x, c, 0]
        : hp < 3
          ? [0, c, x]
          : hp < 4
            ? [0, x, c]
            : hp < 5
              ? [x, 0, c]
              : [c, 0, x];
  const m = lN - c / 2;
  const channel = (v: number): number =>
    v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  const lum =
    0.2126 * channel(r1 + m) + 0.7152 * channel(g1 + m) + 0.0722 * channel(b1 + m);
  return 1.05 / (lum + 0.05);
}

describe("applySiteTheme", () => {
  it.each(SITE_IDS)(
    "sets a --primary that meets WCAG AA white-text contrast for %s",
    (siteId) => {
      applySiteTheme(siteId);
      const primary = document.documentElement.style.getPropertyValue("--primary");
      const [h, s, l] = parseHsl(primary);
      expect(whiteTextContrast(h, s, l)).toBeGreaterThanOrEqual(4.5);
    },
  );

  it("preserves the brand hue while darkening for contrast (toxodb green)", () => {
    applySiteTheme("toxodb");
    const [h] = parseHsl(document.documentElement.style.getPropertyValue("--primary"));
    // #569551 → ~116° green; clamping only lowers lightness, hue is untouched.
    expect(h).toBeGreaterThan(90);
    expect(h).toBeLessThan(150);
  });
});
