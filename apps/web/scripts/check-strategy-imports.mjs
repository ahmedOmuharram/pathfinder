/**
 * Strategy import allowlist for the web app.
 *
 * Rule:
 *   Files under src/features/strategy/ (excluding *.test.* / *.spec.*) MUST NOT
 *   import from the legacy primitive paths:
 *     - @/lib/components/ui/...
 *     - @/lib/components/Modal
 *
 *   The strategy feature should use the new shadcn primitives in
 *   @/components/ui/* instead.
 *
 * Exit code 1 on violations, 0 if clean.
 */

import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(process.cwd());
const STRATEGY_DIR = path.join(ROOT, "src", "features", "strategy");

const BANNED_PATTERNS = [
  /from\s+["']@\/lib\/components\/ui\//,
  /from\s+["']@\/lib\/components\/Modal["']/,
];

function walk(dir) {
  const out = [];
  if (!fs.existsSync(dir)) return out;
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    if (ent.name === "node_modules" || ent.name.startsWith(".")) continue;
    const full = path.join(dir, ent.name);
    if (ent.isDirectory()) {
      out.push(...walk(full));
    } else {
      out.push(full);
    }
  }
  return out;
}

function isTsLike(filePath) {
  return /\.(ts|tsx|mts|cts)$/.test(filePath);
}

function isTestOrSpec(filePath) {
  return /\.(test|spec)\.(ts|tsx|mts|cts)$/.test(filePath);
}

const files = walk(STRATEGY_DIR)
  .filter(isTsLike)
  .filter((f) => !isTestOrSpec(f));

const violations = [];

for (const file of files) {
  const source = fs.readFileSync(file, "utf8");
  const lines = source.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    for (const pattern of BANNED_PATTERNS) {
      if (pattern.test(line)) {
        violations.push({
          file: path.relative(ROOT, file),
          line: i + 1,
          source: line.trim(),
        });
      }
    }
  }
}

if (violations.length > 0) {
  console.error(
    `\ncheck-strategy-imports: found ${violations.length} banned import(s) under features/strategy/\n`,
  );
  for (const v of violations) {
    console.error(`  ${v.file}:${v.line}  ${v.source}`);
  }
  console.error(
    "\nReplace these legacy primitives with the new shadcn primitives under @/components/ui/.",
  );
  process.exit(1);
} else {
  console.log("OK — no banned imports under features/strategy/");
}
