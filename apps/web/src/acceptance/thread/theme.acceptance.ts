/**
 * Frozen acceptance: the token layer is complete in both grounds.
 *
 * No-edit rule: implementers may not touch `src/acceptance/**`. A test that is
 * genuinely wrong is escalated to the session lead, who is the only party that
 * edits this suite.
 *
 * The module reads `globals.css` as text, the way `styles/statusTokens.test.ts`
 * does, and skips until batch 3 adds the `:root[data-theme="dark"]` block, so
 * the suite is a clean skip today rather than a red an implementer must ignore.
 *
 * Run: npx vitest run --config vitest.acceptance.config.ts
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const CSS = readFileSync(
  fileURLToPath(new URL("../../styles/globals.css", import.meta.url)),
  "utf8",
);

const CHART_THEME = readFileSync(
  fileURLToPath(new URL("../../lib/components/charts/chartTheme.ts", import.meta.url)),
  "utf8",
);

const LIGHT_OPENER = ":root {";
const DARK_OPENER = ':root[data-theme="dark"] {';

const hasDarkBlock = CSS.includes(DARK_OPENER);

const CHART_TOKENS = [
  "--chart-1",
  "--chart-2",
  "--chart-3",
  "--chart-4",
  "--chart-5",
  "--chart-6",
  "--chart-positive",
  "--chart-negative",
];

/** A value that paints: an "H S% L%" triple, an rgb(), an oklch() or a hex. */
const COLOR_VALUE =
  /^(?:[\d.]+\s+[\d.]+%\s+[\d.]+%|rgba?\(.+\)|oklch\(.+\)|#[0-9a-fA-F]{3,8})$/;

const DECLARATION = /^\s*(--[a-z0-9-]+):\s*(.+);\s*$/;

const PROPERTY_NAME = /^\s*(--[a-z0-9-]+|[a-z-]+)\s*:/gm;

const COLOR_PROPERTY =
  /color|background|border|--(chart|kind|primary|accent|muted|success|warning|destructive|foreground|card|popover|sidebar|ring|input)/;

function stripComments(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, "");
}

/** The declarations of one top-level block, comments removed. */
function block(opener: string): string {
  const source = stripComments(CSS);
  const start = source.indexOf(opener);
  if (start < 0) throw new Error(`globals.css has no ${opener} block`);
  const from = start + opener.length;
  const end = source.indexOf("\n}", from);
  if (end < 0) throw new Error(`the ${opener} block is never closed`);
  return source.slice(from, end);
}

function colorTokens(source: string): string[] {
  const names: string[] = [];
  for (const line of source.split("\n")) {
    const match = DECLARATION.exec(line);
    if (match === null) continue;
    const name = match[1];
    const value = match[2];
    if (name === undefined || value === undefined) continue;
    if (!COLOR_VALUE.test(value.trim())) continue;
    names.push(name);
  }
  return names.sort();
}

function mediaConditions(): string[] {
  const found: string[] = [];
  for (const match of stripComments(CSS).matchAll(/@media([^{]*)\{/g)) {
    const condition = match[1];
    if (condition === undefined) continue;
    found.push(condition.trim());
  }
  return found;
}

function reducedMotionBlock(): string {
  const source = stripComments(CSS);
  const start = source.indexOf("@media (prefers-reduced-motion: reduce) {");
  if (start < 0) throw new Error("globals.css has no prefers-reduced-motion block");
  const end = source.indexOf("\n}", start);
  if (end < 0) throw new Error("the prefers-reduced-motion block is never closed");
  return source.slice(start, end);
}

function propertyNames(source: string): string[] {
  const names: string[] = [];
  for (const match of source.matchAll(PROPERTY_NAME)) {
    const name = match[1];
    if (name === undefined) continue;
    names.push(name);
  }
  return names;
}

describe.skipIf(!hasDarkBlock)("the token layer covers both grounds", () => {
  it("gives every light color token a dark value, and adds none of its own", () => {
    const light = colorTokens(block(LIGHT_OPENER));
    const dark = colorTokens(block(DARK_OPENER));

    expect(light.filter((name) => !dark.includes(name))).toEqual([]);
    expect(dark.filter((name) => !light.includes(name))).toEqual([]);
    expect(light.length).toBeGreaterThan(0);
  });

  it("declares the eight chart tokens in the dark block", () => {
    const dark = colorTokens(block(DARK_OPENER));

    expect(CHART_TOKENS.filter((name) => !dark.includes(name))).toEqual([]);
  });

  it("keeps the status tokens as H S% L% triples in the light block", () => {
    const light = block(LIGHT_OPENER);

    expect(light).toMatch(/--destructive:\s*[\d.]+\s+[\d.]+%\s+[\d.]+%\s*;/);
    expect(light).toMatch(/--success:\s*[\d.]+\s+[\d.]+%\s+[\d.]+%\s*;/);
    expect(light).toMatch(/--warning:\s*[\d.]+\s+[\d.]+%\s+[\d.]+%\s*;/);
  });

  it("puts the dark block after :root, so the WCAG gate keeps reading light", () => {
    expect(CSS.indexOf(DARK_OPENER)).toBeGreaterThan(CSS.indexOf(LIGHT_OPENER));
  });

  it("has no .dark selector left", () => {
    expect(/^\s*\.dark\b/m.test(CSS)).toBe(false);
    expect(CSS).not.toContain(".dark .specialist-rail-validate");
    expect(CSS).not.toContain(".dark .specialist-rail-research");
  });

  it("binds the dark utility variant to the attribute", () => {
    const match = /@custom-variant\s+dark\s*\(([^)]*\))/.exec(CSS);
    expect(match).not.toBeNull();
    expect(match?.[1] ?? "").toContain('[data-theme="dark"]');
  });

  it("defines no color inside a media query", () => {
    expect(mediaConditions()).toEqual(["(prefers-reduced-motion: reduce)"]);
    const painted = propertyNames(reducedMotionBlock()).filter((name) =>
      COLOR_PROPERTY.test(name),
    );
    expect(painted).toEqual([]);
  });

  it("leaves no hardcoded light palette in chartTheme.ts", () => {
    expect(CHART_THEME).not.toContain("hsl(");
  });
});
