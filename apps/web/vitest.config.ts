import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

const srcDir = fileURLToPath(new URL("./src", import.meta.url));
const sharedDir = fileURLToPath(
  new URL("../../packages/shared-ts/src", import.meta.url),
);
const webNodeModules = fileURLToPath(new URL("./node_modules", import.meta.url));

export default defineConfig({
  resolve: {
    alias: [
      { find: "@/", replacement: `${srcDir}/` },
      {
        find: /^@pathfinder\/shared\/generated\/(.*)$/,
        replacement: `${sharedDir}/generated/$1`,
      },
      { find: "@pathfinder/shared", replacement: sharedDir },
      {
        find: "@tanstack/react-query",
        replacement: `${webNodeModules}/@tanstack/react-query`,
      },
      { find: /^react$/, replacement: `${webNodeModules}/react` },
      { find: /^react-dom$/, replacement: `${webNodeModules}/react-dom` },
    ],
  },
  test: {
    setupFiles: ["./vitest.setup.ts", "./vitest.msw-setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["e2e/**", "node_modules/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      // Unit coverage focuses on app "logic layers"; UI is covered by Playwright E2E.
      include: [
        "src/lib/**/*.{ts,tsx}",
        // Conversation logic modules (unit-tested); its React renderers,
        // transport and hooks are covered by Playwright E2E.
        "src/features/conversation/content/parts/{consultData,taskCompletionResume,taskLiveState}.ts",
        "src/features/conversation/rail/{consultActions,normalizeLedger,railActivity}.ts",
        "src/features/conversation/runtime/{buildRequestBody,feedbackAdapter,geneIdAttachmentAdapter,replayChunks,traceId}.ts",
        "src/features/conversation/slash/{parser,registryUtils}.ts",
        // ReactFlow graph interaction logic (unit-tested).
        "src/features/strategy/graph/utils/**/*.{ts,tsx}",
        // Strategy pure helpers (unit-tested).
        "src/features/strategy/services/openAndHydrateDraftStrategy.ts",
        "src/features/strategy/utils/draftSummary.ts",
        // Sidebar pure list logic.
        "src/features/sidebar/utils/**/*.{ts,tsx}",
        "src/features/sidebar/services/**/*.{ts,tsx}",
        "src/state/**/*.{ts,tsx}",
        // Experiment store logic.
        "src/features/experiments/store/**/*.{ts,tsx}",
        "src/features/experiments/utils/**/*.{ts,tsx}",
        "src/shared/**/*.{ts,tsx}",
        // Pure strategy graph logic (unit-tested).
        "src/lib/strategyGraph/{kind,serialize,validate,types,deserialize}.ts",
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
