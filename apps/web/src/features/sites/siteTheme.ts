/**
 * Per-site brand colors extracted from VEuPathDB's official CSS.
 *
 * Each entry maps a site ID to its primary brand hex color (used for
 * headings/nav on the original VEuPathDB sites).
 */

const SITE_COLORS: Record<string, string> = {
  veupathdb: "#2e537b",
  plasmodb: "#634697",
  toxodb: "#569551",
  cryptodb: "#274f94",
  giardiadb: "#3b4da0",
  amoebadb: "#5a9e83",
  microsporidiadb: "#3a7ca5",
  piroplasmadb: "#3a8c9f",
  tritrypdb: "#c06530",
  fungidb: "#0e8298",
  hostdb: "#0c7eb5",
  vectorbase: "#b74630",
  orthomcl: "#316e9f",
  schistodb: "#346079",
  trichdb: "#6e8446",
};

const DEFAULT_COLOR = "#2596b3";

function hexToHsl(hex: string): [number, number, number] {
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;

  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;

  if (max === min) return [0, 0, Math.round(l * 100)];

  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);

  let h = 0;
  if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
  else if (max === g) h = ((b - r) / d + 2) / 6;
  else h = ((r - g) / d + 4) / 6;

  return [Math.round(h * 360), Math.round(s * 100), Math.round(l * 100)];
}

/**
 * Returns the HSL CSS value string for a given site's brand color.
 *
 * :param siteId: The VEuPathDB site identifier.
 * :returns: HSL values as "H S% L%" (without the hsl() wrapper, compatible
 *     with the CSS variable format used by shadcn/tailwind).
 */
function getSiteHslParts(siteId: string): [number, number, number] {
  const hex = SITE_COLORS[siteId] ?? DEFAULT_COLOR;
  return hexToHsl(hex);
}

function hslToRgb(h: number, s: number, l: number): [number, number, number] {
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
  return [r1 + m, g1 + m, b1 + m];
}

function relativeLuminance(h: number, s: number, l: number): number {
  const channel = (v: number): number =>
    v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  const [r, g, b] = hslToRgb(h, s, l);
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function whiteTextContrast(h: number, s: number, l: number): number {
  return 1.05 / (relativeLuminance(h, s, l) + 0.05);
}

/**
 * Lowers a brand color's lightness until white foreground text meets the
 * WCAG AA 4.5:1 ratio (small margin). The raw VEuPathDB brand colors sit at
 * ~45–50% lightness — too light for the white `primary-foreground` text on
 * primary buttons. Same hue/saturation, just dark enough to be legible.
 */
function clampLightnessForWhiteText(h: number, s: number, l: number): number {
  let out = l;
  while (out > 0 && whiteTextContrast(h, s, out) < 4.6) {
    out -= 1;
  }
  return out;
}

/**
 * Applies the site's brand palette to CSS custom properties on the document
 * root. Derives a coherent secondary/accent from the primary hue so every
 * theme token (primary, secondary, accent, muted, ring) tracks the site
 * brand instead of falling back to the default neutral.
 */
export function applySiteTheme(siteId: string): void {
  const [h, s, l] = getSiteHslParts(siteId);
  const primary = `${h} ${s}% ${clampLightnessForWhiteText(h, s, l)}%`;
  // Tinted backgrounds: same hue, low saturation, near-white. The 95/93
  // lightness pair matches the default theme's secondary/accent split so
  // contrast against `secondary-foreground` (dark text) stays AA-compliant.
  const secondary = `${h} 25% 95%`;
  const accent = `${h} 25% 93%`;
  const muted = `${h} 20% 96%`;
  const root = document.documentElement;
  root.style.setProperty("--primary", primary);
  root.style.setProperty("--ring", primary);
  root.style.setProperty("--secondary", secondary);
  root.style.setProperty("--accent", accent);
  root.style.setProperty("--muted", muted);
}
