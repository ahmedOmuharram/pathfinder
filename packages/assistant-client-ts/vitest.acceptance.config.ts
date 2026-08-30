import { defineConfig } from "vitest/config";

/** The frozen acceptance suites. The default config never collects these files. */
export default defineConfig({
  test: {
    include: ["tests/acceptance/**/*.acceptance.ts"],
    environment: "node",
  },
});
