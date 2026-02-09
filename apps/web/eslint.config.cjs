const { FlatCompat } = require("@eslint/eslintrc");
const { defineConfig } = require("eslint/config");

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

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
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-require-imports": "error",
    },
  },
  // Tests often need flexible mocks/fixtures.
  {
    files: ["**/*.test.{ts,tsx}", "e2e/**/*.spec.ts"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
  // Node config files are intentionally CommonJS.
  {
    files: ["**/*.cjs", "next.config.js"],
    rules: {
      "@typescript-eslint/no-require-imports": "off",
    },
  },
]);
