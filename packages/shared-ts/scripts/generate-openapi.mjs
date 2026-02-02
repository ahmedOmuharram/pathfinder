import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import openapiTS from "openapi-typescript";
import ts from "typescript";

const repoRoot = path.resolve(new URL(".", import.meta.url).pathname, "../../../");
const openapiPath = path.join(repoRoot, "packages", "spec", "openapi.yaml");
const outPath = path.join(repoRoot, "packages", "shared-ts", "src", "openapi.generated.ts");

const checkOnly = process.argv.includes("--check");

async function main() {
  const specText = fs.readFileSync(openapiPath, "utf8");
  const nodes = await openapiTS(specText, {
    // Keep output stable and compact.
    alphabetize: false,
    exportType: true,
  });

  const sourceFile = ts.createSourceFile(
    "openapi.generated.ts",
    "",
    ts.ScriptTarget.Latest,
    false,
    ts.ScriptKind.TS
  );
  const printer = ts.createPrinter({ newLine: ts.NewLineKind.LineFeed });
  const rendered = nodes
    .map((node) => printer.printNode(ts.EmitHint.Unspecified, node, sourceFile))
    .join("\n\n");

  const banner =
    `/**\n` +
    ` * AUTO-GENERATED FILE — DO NOT EDIT.\n` +
    ` *\n` +
    ` * Source: packages/spec/openapi.yaml\n` +
    ` * Generator: packages/shared-ts/scripts/generate-openapi.mjs\n` +
    ` */\n\n`;

  const next = banner + rendered + "\n";

  if (checkOnly) {
    const current = fs.existsSync(outPath) ? fs.readFileSync(outPath, "utf8") : "";
    if (current !== next) {
      console.error(
        `OpenAPI types are out of date.\nRun: (cd packages/shared-ts && npm run generate:openapi)`
      );
      process.exit(1);
    }
    return;
  }

  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, next, "utf8");
  console.log(`Wrote ${outPath}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

