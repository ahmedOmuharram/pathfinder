import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it, expect } from "vitest";

import { composite, contrast, hslToRgb } from "@/lib/color/contrast";

const CSS = readFileSync(
  fileURLToPath(new URL("./globals.css", import.meta.url)),
  "utf8",
);

type Rgb = readonly [number, number, number];

function readTokenFrom(source: string, name: string): Rgb {
  const match = source.match(
    new RegExp(`--${name}:\\s*([\\d.]+)\\s+([\\d.]+)%\\s+([\\d.]+)%\\s*;`),
  );
  const [, h, s, l] = match ?? [];
  if (h === undefined || s === undefined || l === undefined) {
    throw new Error(`token --${name} is not an "H S% L%" triple in globals.css`);
  }
  return hslToRgb(Number(h), Number(s), Number(l));
}

const DARK_OPENER = ':root[data-theme="dark"] {';

/** The dark ground's declarations, which follow the light ones in the file. */
const DARK_CSS = CSS.slice(CSS.indexOf(DARK_OPENER));

function readToken(name: string): Rgb {
  return readTokenFrom(CSS, name);
}

function readDarkToken(name: string): Rgb {
  return readTokenFrom(DARK_CSS, name);
}

const WHITE: Rgb = [1, 1, 1];
const AA_NORMAL_TEXT = 4.5;

/** Surfaces a status-tone chip or message can sit on. */
const SURFACES = ["card", "background", "sidebar", "muted", "accent"] as const;

/** Highest tint alpha used with same-token text (`bg-success/15 text-success`). */
const TINT_ALPHA = 0.15;

const STATUS_TOKENS = ["destructive", "success", "warning"] as const;

describe("status color tokens meet WCAG AA as text", () => {
  const surfaces = SURFACES.map((name) => [name, readToken(name)] as const);

  for (const token of STATUS_TOKENS) {
    describe(`--${token}`, () => {
      const color = readToken(token);

      for (const [surfaceName, surface] of surfaces) {
        it(`reads on --${surfaceName}`, () => {
          expect(contrast(color, surface)).toBeGreaterThanOrEqual(AA_NORMAL_TEXT);
        });

        it(`reads on its own tint over --${surfaceName}`, () => {
          const tint = composite(color, surface, TINT_ALPHA);
          expect(contrast(color, tint)).toBeGreaterThanOrEqual(AA_NORMAL_TEXT);
        });
      }

      it("carries white foreground when used as a solid fill", () => {
        expect(contrast(WHITE, color)).toBeGreaterThanOrEqual(AA_NORMAL_TEXT);
      });
    });
  }
});

describe("status text is never alpha-faded", () => {
  it("no source file fades a status text token with an alpha suffix", () => {
    const root = fileURLToPath(new URL("..", import.meta.url));
    const offenders: string[] = [];
    const walk = (dir: string): void => {
      for (const entry of readdirSync(dir, { withFileTypes: true })) {
        const full = join(dir, entry.name);
        if (entry.isDirectory()) {
          if (entry.name === "generated" || entry.name === "node_modules") continue;
          walk(full);
          continue;
        }
        if (!/\.(ts|tsx)$/.test(entry.name)) continue;
        const source = readFileSync(full, "utf8");
        for (const line of source.split("\n")) {
          if (/text-(destructive|warning|success|muted-foreground)\/\d+/.test(line)) {
            offenders.push(`${full}: ${line.trim()}`);
          }
        }
      }
    };
    walk(root);
    expect(offenders).toEqual([]);
  });
});

/**
 * Tokens `geneSetSourceConfig` paints as badge text over a tint of themselves.
 * A chart series is a fill elsewhere; here it has to read as words.
 */
const BADGE_TOKENS = ["chart-1", "chart-2", "chart-3", "chart-5"] as const;

/** The grounds a gene-set badge sits on: the page, a card and the sidebar. */
const BADGE_SURFACES = ["background", "card", "sidebar"] as const;

/** The tint alpha `geneSetSourceConfig` gives a badge background. */
const BADGE_TINT_ALPHA = 0.1;

describe("gene-set source badges meet WCAG AA as text", () => {
  for (const ground of ["light", "dark"] as const) {
    const token = ground === "light" ? readToken : readDarkToken;
    describe(ground, () => {
      for (const name of BADGE_TOKENS) {
        const color = token(name);
        for (const surfaceName of BADGE_SURFACES) {
          const surface = token(surfaceName);

          it(`--${name} reads on --${surfaceName}`, () => {
            expect(contrast(color, surface)).toBeGreaterThanOrEqual(AA_NORMAL_TEXT);
          });

          it(`--${name} reads on its own tint over --${surfaceName}`, () => {
            const tint = composite(color, surface, BADGE_TINT_ALPHA);
            expect(contrast(color, tint)).toBeGreaterThanOrEqual(AA_NORMAL_TEXT);
          });
        }
      }
    });
  }
});
