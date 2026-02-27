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
export function getSiteHsl(siteId: string): string {
  const hex = SITE_COLORS[siteId] ?? DEFAULT_COLOR;
  const [h, s, l] = hexToHsl(hex);
  return `${h} ${s}% ${l}%`;
}

/**
 * Applies the site's brand color to CSS custom properties on the document root.
 *
 * Sets `--primary` and `--ring` to the site's brand color so the entire
 * design system (buttons, focus rings, active states, links) adapts.
 */
export function applySiteTheme(siteId: string): void {
  const hsl = getSiteHsl(siteId);
  const root = document.documentElement;
  root.style.setProperty("--primary", hsl);
  root.style.setProperty("--ring", hsl);
}
