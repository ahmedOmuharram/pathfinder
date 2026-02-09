import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

const srcDir = fileURLToPath(new URL("./src", import.meta.url));

export default defineConfig({
  resolve: {
    alias: {
      "@": srcDir,
    },
  },
  test: {
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["e2e/**", "node_modules/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      all: true,
      // Unit coverage focuses on app "logic layers"; UI is covered by Playwright E2E.
      include: [
        "src/lib/**/*.{ts,tsx}",
        "src/features/chat/**/*.{ts,tsx}",
        // ReactFlow graph interaction logic (unit-tested).
        "src/features/strategy/graph/utils/**/*.{ts,tsx}",
        // Strategy pure helpers (unit-tested).
        "src/features/strategy/services/openAndHydrateDraftStrategy.ts",
        "src/features/strategy/utils/draftSummary.ts",
        // Sidebar pure list logic.
        "src/features/sidebar/utils/**/*.{ts,tsx}",
        "src/features/sidebar/services/**/*.{ts,tsx}",
        "src/state/**/*.{ts,tsx}",
        "src/shared/**/*.{ts,tsx}",
        // Pure strategy graph logic (unit-tested).
        "src/core/strategyGraph/{kind,serialize,validate,types,deserialize}.ts",
      ],
      exclude: [
        // UI rendering is primarily covered by Playwright E2E.
        "src/app/**",
        "src/**/components/**",
        "src/features/**/graph/components/**",
        "src/features/**/graph/hooks/**",
        "src/features/**/editor/**",
        "src/features/results/**",
        "src/features/sites/**",
        // React hooks are primarily tested via E2E; unit coverage focuses on pure logic.
        "src/features/chat/hooks/**",
        "src/shared/hooks/**",
        "src/shared/types/**",
        "src/core/**",
        "src/types/**",
        "**/*.d.ts",
        "**/*.config.*",
        "**/e2e/**",
        "**/node_modules/**",
        "**/.next/**",
      ],
      thresholds: {
        statements: 80,
        lines: 80,
        branches: 70,
        functions: 60,
      },
    },
  },
});
