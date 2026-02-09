const { defineConfig } = require("eslint/config");
const nextConfig = require("eslint-config-next/core-web-vitals");

const tsBlock = nextConfig.find((b) => b.name === "next/typescript");
const tsPlugin = tsBlock?.plugins?.["@typescript-eslint"];

module.exports = defineConfig([
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "playwright-report/**",
      "test-results/**",
      "coverage/**",
    ],
  },
  ...nextConfig,
  // TypeScript rule overrides (plugin must be in same config object).
  ...(tsPlugin
    ? [
        {
          files: ["**/*.ts", "**/*.tsx"],
          plugins: { "@typescript-eslint": tsPlugin },
          rules: {
            "@typescript-eslint/no-explicit-any": "error",
            "@typescript-eslint/no-require-imports": "error",
          },
        },
        {
          files: ["**/*.test.{ts,tsx}", "e2e/**/*.spec.ts"],
          plugins: { "@typescript-eslint": tsPlugin },
          rules: { "@typescript-eslint/no-explicit-any": "off" },
        },
        {
          files: ["**/*.cjs", "next.config.js"],
          plugins: { "@typescript-eslint": tsPlugin },
          rules: { "@typescript-eslint/no-require-imports": "off" },
        },
      ]
    : []),
]);
