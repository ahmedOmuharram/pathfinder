import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(process.cwd());

function walk(dir) {
  const out = [];
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    if (ent.name === "node_modules" || ent.name.startsWith(".")) continue;
    const p = path.join(dir, ent.name);
    if (ent.isDirectory()) out.push(...walk(p));
    else out.push(p);
  }
  return out;
}

function read(filePath) {
  return fs.readFileSync(filePath, "utf8");
}

function isTsLike(p) {
  return (
    p.endsWith(".ts") || p.endsWith(".tsx") || p.endsWith(".mts") || p.endsWith(".cts")
  );
}

function fail(messages) {
  for (const m of messages) console.error(m);
  process.exit(1);
}

const errors = [];

// Rule 1: transport must not import state
{
  const dir = path.join(ROOT, "src", "lib", "api");
  const files = walk(dir).filter(isTsLike);
  for (const f of files) {
    const text = read(f);
    const rel = path.relative(ROOT, f);
    if (text.match(/from\s+["']@\/state\//)) {
      errors.push(`[boundary] lib/api must not import state: ${rel}`);
    }
    if (text.match(/from\s+["']\.\.\/\.\.\/state\//)) {
      errors.push(`[boundary] lib/api must not import state: ${rel}`);
    }
  }
}

// Rule 2: core must not import transport
{
  const dir = path.join(ROOT, "src", "core", "strategyGraph");
  const files = walk(dir).filter(isTsLike);
  for (const f of files) {
    const text = read(f);
    const rel = path.relative(ROOT, f);
    if (
      text.match(/from\s+["']@\/lib\/api\//) ||
      text.match(/from\s+["']@\/lib\/sse/)
    ) {
      errors.push(`[boundary] core/strategyGraph must not import transport: ${rel}`);
    }
  }
}

// Rule 3: discourage local DTOs in lib/api/client.ts (contracts must come from @pathfinder/shared)
{
  const f = path.join(ROOT, "src", "lib", "api", "client.ts");
  const text = read(f);
  const rel = path.relative(ROOT, f);
  const hasTypeDecl = /(^|\n)\s*(export\s+)?(interface|type)\s+[A-Za-z0-9_]+/m.test(
    text,
  );
  if (hasTypeDecl) {
    errors.push(
      `[contract] no local type/interface declarations in ${rel}; import DTOs from @pathfinder/shared`,
    );
  }
}

if (errors.length) fail(errors);
console.log("check-boundaries: ok");
