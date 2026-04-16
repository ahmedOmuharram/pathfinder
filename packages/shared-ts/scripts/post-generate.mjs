// Post-generation patcher for Kubb output.
//
// Two shortcuts baked in here — see memory/project_kubb_shortcuts.md for
// context and the proper fixes (deferred).
//
// 1. Pydantic `type JSONValue = JsonValue` alias emits BOTH `JSONValue` and
//    `JsonValue` schemas to OpenAPI. Kubb generates one file per schema with
//    the PascalCase filename but lowercased-acronym identifier. On macOS's
//    case-insensitive filesystem those collide onto a single physical file
//    whose contents become inconsistent with at least one consumer's import.
//    We dual-export both names so either import resolves.
//
// 2. Runs as a Kubb `hooks.done` entry after every generation. Idempotent.

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const typesDir = join(here, "..", "src", "generated", "types");
const zodDir = join(here, "..", "src", "generated", "zod");

function ensureDualExport(path, primary, alias) {
  if (!existsSync(path)) return;
  const contents = readFileSync(path, "utf8");
  if (contents.includes(`export type ${primary}`) && contents.includes(`export type ${alias}`)) {
    return;
  }
  if (contents.includes(`export type ${alias} = unknown`)) {
    const patched = contents.replace(
      `export type ${alias} = unknown;`,
      `export type ${alias} = unknown;\nexport type ${primary} = ${alias};`,
    );
    writeFileSync(path, patched, "utf8");
    return;
  }
  if (contents.includes(`export type ${primary} = unknown`)) {
    const patched = contents.replace(
      `export type ${primary} = unknown;`,
      `export type ${primary} = unknown;\nexport type ${alias} = ${primary};`,
    );
    writeFileSync(path, patched, "utf8");
  }
}

function ensureDualZodExport(path, primarySchemaName, aliasSchemaName) {
  if (!existsSync(path)) return;
  const contents = readFileSync(path, "utf8");
  if (contents.includes(`export const ${primarySchemaName}`) && contents.includes(`export const ${aliasSchemaName}`)) {
    return;
  }
  if (contents.includes(`export const ${aliasSchemaName} =`)) {
    const patched = contents.replace(
      new RegExp(`(export const ${aliasSchemaName} = [^;]+;)`),
      `$1\nexport const ${primarySchemaName} = ${aliasSchemaName};`,
    );
    writeFileSync(path, patched, "utf8");
    return;
  }
  if (contents.includes(`export const ${primarySchemaName} =`)) {
    const patched = contents.replace(
      new RegExp(`(export const ${primarySchemaName} = [^;]+;)`),
      `$1\nexport const ${aliasSchemaName} = ${primarySchemaName};`,
    );
    writeFileSync(path, patched, "utf8");
  }
}

for (const pair of [
  ["JSONValue", "JsonValue"],
  ["JSONArray", "JsonArray"],
  ["JSONObject", "JsonObject"],
]) {
  ensureDualExport(join(typesDir, `${pair[0]}.ts`), pair[0], pair[1]);
  ensureDualZodExport(
    join(zodDir, `${pair[0]}Schema.ts`),
    `${pair[0][0].toLowerCase()}${pair[0].slice(1)}Schema`,
    `${pair[1][0].toLowerCase()}${pair[1].slice(1)}Schema`,
  );
}

// `forceConsistentCasingInFileNames` treats `./JsonValue.ts` and `./JSONValue.ts`
// as distinct even though macOS's case-insensitive FS collapses them to one
// physical file. Normalize every consumer to the canonical PascalCase form.
import { readdirSync } from "node:fs";

function rewriteDirImports(dir) {
  if (!existsSync(dir)) return;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isFile() || !entry.name.endsWith(".ts")) continue;
    const full = join(dir, entry.name);
    const contents = readFileSync(full, "utf8");
    const rewritten = contents
      .replaceAll('"./JsonValue.ts"', '"./JSONValue.ts"')
      .replaceAll('"./JsonArray.ts"', '"./JSONArray.ts"')
      .replaceAll('"./JsonObject.ts"', '"./JSONObject.ts"')
      .replaceAll('"../types/JsonValue.ts"', '"../types/JSONValue.ts"')
      .replaceAll('"../types/JsonArray.ts"', '"../types/JSONArray.ts"')
      .replaceAll('"../types/JsonObject.ts"', '"../types/JSONObject.ts"');
    if (rewritten !== contents) {
      writeFileSync(full, rewritten, "utf8");
    }
  }
}

for (const sub of ["types", "zod", "hooks"]) {
  rewriteDirImports(join(here, "..", "src", "generated", sub));
}

// Outer-level index.ts also references the lowercase variants.
const outerIndex = join(here, "..", "src", "generated", "index.ts");
if (existsSync(outerIndex)) {
  const contents = readFileSync(outerIndex, "utf8");
  const rewritten = contents
    .replaceAll('"./types/JsonValue.ts"', '"./types/JSONValue.ts"')
    .replaceAll('"./types/JsonArray.ts"', '"./types/JSONArray.ts"')
    .replaceAll('"./types/JsonObject.ts"', '"./types/JSONObject.ts"')
    .replaceAll('"./zod/jsonValueSchema.ts"', '"./zod/JSONValueSchema.ts"')
    .replaceAll('"./zod/jsonArraySchema.ts"', '"./zod/JSONArraySchema.ts"')
    .replaceAll('"./zod/jsonObjectSchema.ts"', '"./zod/JSONObjectSchema.ts"');
  if (rewritten !== contents) {
    writeFileSync(outerIndex, rewritten, "utf8");
  }
}
