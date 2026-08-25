import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it, expect } from "vitest";

const CSS = readFileSync(
  fileURLToPath(new URL("./globals.css", import.meta.url)),
  "utf8",
);

type Rgb = readonly [number, number, number];

function readToken(name: string): Rgb {
  const match = CSS.match(
    new RegExp(`--${name}:\\s*([\\d.]+)\\s+([\\d.]+)%\\s+([\\d.]+)%\\s*;`),
  );
  const [, h, s, l] = match ?? [];
  if (h === undefined || s === undefined || l === undefined) {
    throw new Error(`token --${name} is not an "H S% L%" triple in globals.css`);
  }
  return hslToRgb(Number(h), Number(s), Number(l));
}

/** CSS Color Level 4 hsl-to-rgb, each channel in 0..1. */
function hslToRgb(h: number, s: number, l: number): Rgb {
  const sat = s / 100;
  const light = l / 100;
  const amplitude = sat * Math.min(light, 1 - light);
  const channel = (n: number): number => {
    const k = (n + h / 30) % 12;
    return light - amplitude * Math.max(-1, Math.min(k - 3, 9 - k, 1));
  };
  return [channel(0), channel(8), channel(4)];
}

function relativeLuminance(c: Rgb): number {
  const channel = (v: number): number =>
    v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  return 0.2126 * channel(c[0]) + 0.7152 * channel(c[1]) + 0.0722 * channel(c[2]);
}

function contrast(a: Rgb, b: Rgb): number {
  const la = relativeLuminance(a);
  const lb = relativeLuminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

function composite(fg: Rgb, base: Rgb, alpha: number): Rgb {
  return [
    alpha * fg[0] + (1 - alpha) * base[0],
    alpha * fg[1] + (1 - alpha) * base[1],
    alpha * fg[2] + (1 - alpha) * base[2],
  ];
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
