import { fileURLToPath } from "node:url";
import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

const WEB_ROOT = fileURLToPath(new URL("..", import.meta.url));

const eslint = new ESLint({ cwd: WEB_ROOT });

const GENERATED_TREES = [
  ".stryker-tmp/sandbox-abcdef/src/state/strategy/reducer.ts",
  ".stryker-tmp/incremental.json",
  ".next/types/routes.ts",
  "coverage/lcov-report/index.html",
  "playwright-report/index.html",
  "test-results/results.json",
  "reports/mutation/index.html",
];

const LINTED_TREES = [
  "src/lib/utils/cn.ts",
  "e2e/feature/durable-verification.spec.ts",
  "scripts/check-boundaries.mjs",
];

describe("the whole-directory lint program", () => {
  it.each(GENERATED_TREES)("ignores %s", async (path) => {
    expect(await eslint.isPathIgnored(path)).toBe(true);
  });

  it.each(LINTED_TREES)("lints %s", async (path) => {
    expect(await eslint.isPathIgnored(path)).toBe(false);
  });
});
