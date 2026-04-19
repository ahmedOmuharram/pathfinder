import { defineConfig } from "@kubb/core";
import { pluginOas } from "@kubb/plugin-oas";
import { pluginTs } from "@kubb/plugin-ts";
import { pluginZod } from "@kubb/plugin-zod";
import { pluginReactQuery } from "@kubb/plugin-react-query";

export default defineConfig({
  root: ".",
  input: { path: "../spec/openapi.json" },
  output: { path: "./src/generated", clean: true },
  plugins: [
    pluginOas({ validate: true, generators: [] }),
    pluginTs({
      output: { path: "types" },
      enumType: "asConst",
      dateType: "string",
      unknownType: "unknown",
      transformers: {
        name: (name) => name,
      },
    }),
    pluginZod({
      output: { path: "zod" },
      typed: true,
      dateType: "string",
      unknownType: "unknown",
      inferred: true,
      coercion: false,
    }),
    pluginReactQuery({
      output: { path: "hooks" },
      client: { importPath: "@/lib/api/client" },
      query: {
        methods: ["get"],
        importPath: "@tanstack/react-query",
      },
      suspense: {},
      mutation: {
        methods: ["post", "put", "patch", "delete"],
      },
      parser: "zod",
    }),
  ],
});
