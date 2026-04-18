import { describe, it, expect } from "vitest";

import { normalizeLatex } from "./normalizeLatex";

describe("normalizeLatex", () => {
  it("leaves text with no latex untouched", () => {
    expect(normalizeLatex("Hello world")).toBe("Hello world");
  });

  it("converts display \\[ ... \\] to $$ ... $$", () => {
    expect(normalizeLatex("\\[ x^2 \\]")).toBe("$$ x^2 $$");
  });

  it("converts inline \\( ... \\) to $ ... $", () => {
    expect(normalizeLatex("Precision is \\( p \\) here.")).toBe(
      "Precision is $ p $ here.",
    );
  });

  it("converts bare [ ... ] containing LaTeX to $$ ... $$", () => {
    const input = "[ \\text{Precision} = \\frac{a}{b} ]";
    expect(normalizeLatex(input)).toBe("$$\\text{Precision} = \\frac{a}{b}$$");
  });

  it("preserves markdown links", () => {
    expect(normalizeLatex("See [docs](https://example.com) for more.")).toBe(
      "See [docs](https://example.com) for more.",
    );
  });

  it("preserves footnote-like [1] references", () => {
    expect(normalizeLatex("See [1] and [2] for context.")).toBe(
      "See [1] and [2] for context.",
    );
  });

  it("handles multi-line display math", () => {
    const input = "[ \\frac{a}{b}\n= c ]";
    const out = normalizeLatex(input);
    expect(out).toContain("$$");
    expect(out).not.toMatch(/^\[/);
  });

  it("converts inline ( \\alpha ) to $\\alpha$", () => {
    expect(normalizeLatex("When ( \\alpha > 0 ), proceed.")).toBe(
      "When $\\alpha > 0$, proceed.",
    );
  });

  it("leaves non-math parentheses alone", () => {
    expect(normalizeLatex("(this is prose) no change")).toBe(
      "(this is prose) no change",
    );
  });
});
