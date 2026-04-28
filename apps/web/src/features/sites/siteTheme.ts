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

/**
 * Applies the site's brand palette to CSS custom properties on the document
 * root. Derives a coherent secondary/accent from the primary hue so every
 * theme token (primary, secondary, accent, muted, ring) tracks the site
 * brand instead of falling back to the default neutral.
 */
export function applySiteTheme(siteId: string): void {
  const [h, s, l] = getSiteHslParts(siteId);
  const primary = `${h} ${s}% ${l}%`;
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
