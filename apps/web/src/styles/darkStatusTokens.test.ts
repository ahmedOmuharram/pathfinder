import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, it, expect } from "vitest";

import { composite, contrast, hslToRgb, type Rgb } from "@/lib/color/contrast";

const CSS = readFileSync(
  fileURLToPath(new URL("./globals.css", import.meta.url)),
  "utf8",
);

const DARK_OPENER = ':root[data-theme="dark"] {';

/**
 * Only the dark block. `statusTokens.test.ts` takes the first match in the
 * whole file, so the two suites can never read each other's palette.
 */
const DARK_BLOCK = ((): string => {
  const start = CSS.indexOf(DARK_OPENER);
  if (start < 0) throw new Error("globals.css has no dark block");
  const end = CSS.indexOf("\n}", start);
  if (end < 0) throw new Error("the dark block is never closed");
  return CSS.slice(start, end);
})();

function readToken(name: string): Rgb {
  const match = DARK_BLOCK.match(
    new RegExp(`--${name}:\\s*([\\d.]+)\\s+([\\d.]+)%\\s+([\\d.]+)%\\s*;`),
  );
  const [, h, s, l] = match ?? [];
  if (h === undefined || s === undefined || l === undefined) {
    throw new Error(`token --${name} is not an "H S% L%" triple in the dark block`);
  }
  return hslToRgb(Number(h), Number(s), Number(l));
}

const AA_NORMAL_TEXT = 4.5;

/** Surfaces a status-tone chip or message can sit on. */
const SURFACES = ["card", "background", "sidebar", "muted", "accent"] as const;

/** Highest tint alpha used with same-token text (`bg-success/15 text-success`). */
const TINT_ALPHA = 0.15;

const STATUS_TOKENS = ["destructive", "success", "warning"] as const;

describe("dark status color tokens meet WCAG AA as text", () => {
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

      it("carries its own foreground when used as a solid fill", () => {
        const foreground = readToken(`${token}-foreground`);
        expect(contrast(foreground, color)).toBeGreaterThanOrEqual(AA_NORMAL_TEXT);
      });
    });
  }
});

describe("the dark foregrounds are dark, not white", () => {
  it.each(STATUS_TOKENS)("--%s-foreground is darker than its token", (token) => {
    const foreground = readToken(`${token}-foreground`);
    const white: Rgb = [1, 1, 1];
    expect(contrast(foreground, white)).toBeGreaterThan(
      contrast(readToken(token), white),
    );
  });
});
