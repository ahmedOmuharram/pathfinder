import { describe, expect, it } from "vitest";
import { SOURCE_CONFIG } from "./geneSetSourceConfig";

describe("SOURCE_CONFIG", () => {
  it("badges every source from the token layer", () => {
    expect(SOURCE_CONFIG.strategy.badgeClass).toBe(
      "bg-[hsl(var(--chart-1)/0.1)] text-[hsl(var(--chart-1))] border-[hsl(var(--chart-1)/0.2)]",
    );
    expect(SOURCE_CONFIG.paste.badgeClass).toBe(
      "bg-[hsl(var(--chart-3)/0.1)] text-[hsl(var(--chart-3))] border-[hsl(var(--chart-3)/0.2)]",
    );
    expect(SOURCE_CONFIG.upload.badgeClass).toBe(
      "bg-[hsl(var(--chart-5)/0.1)] text-[hsl(var(--chart-5))] border-[hsl(var(--chart-5)/0.2)]",
    );
    expect(SOURCE_CONFIG.derived.badgeClass).toBe(
      "bg-[hsl(var(--chart-2)/0.1)] text-[hsl(var(--chart-2))] border-[hsl(var(--chart-2)/0.2)]",
    );
    expect(SOURCE_CONFIG.saved.badgeClass).toBe(
      "bg-muted text-muted-foreground border-border",
    );
  });

  it("carries no palette shade and no dark twin", () => {
    for (const config of Object.values(SOURCE_CONFIG)) {
      expect(config.badgeClass).not.toMatch(/-(?:\d{2,3})\b/);
      expect(config.badgeClass).not.toContain("dark:");
    }
  });
});
