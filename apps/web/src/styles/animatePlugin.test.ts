import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const globals = readFileSync(
  fileURLToPath(new URL("./globals.css", import.meta.url)),
  "utf8",
);

const plugin = readFileSync(
  join(process.cwd(), "node_modules/tw-animate-css/dist/tw-animate.css"),
  "utf8",
);

describe("the shadcn animation vocabulary", () => {
  it("is loaded by the global stylesheet right after Tailwind", () => {
    const lines = globals.split("\n");
    expect(lines.indexOf('@import "tw-animate-css";')).toBe(
      lines.indexOf('@import "tailwindcss";') + 1,
    );
  });

  it("defines every utility the vendored primitives use", () => {
    expect(plugin).toContain("--animate-in:");
    expect(plugin).toContain("--animate-out:");
    for (const utility of [
      "fade-in-*",
      "fade-out-*",
      "zoom-in-*",
      "zoom-out-*",
      "slide-in-from-top-*",
      "slide-in-from-bottom",
      "slide-in-from-left-*",
      "slide-in-from-right-*",
    ]) {
      expect(plugin).toContain(`@utility ${utility}{`);
    }
  });
});
