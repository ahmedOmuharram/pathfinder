import { defineConfig } from "vitest/config";

import baseConfig from "./vitest.config";

/** The EDA acceptance suite. The default config never collects these files. */
export default defineConfig({
  ...baseConfig,
  test: {
    ...baseConfig.test,
    include: [
      "src/acceptance/**/*.acceptance.ts",
      "src/acceptance/**/*.acceptance.tsx",
    ],
    exclude: ["e2e/**", "node_modules/**"],
  },
});
