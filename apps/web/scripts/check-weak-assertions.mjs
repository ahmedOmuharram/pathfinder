/**
 * Flag Vitest / Playwright tests whose only `expect(...)` chains are weak.
 *
 * Weak matchers — survive almost any mutation to the function under test:
 *   toBeTruthy, toBeFalsy, toBeDefined, toBeUndefined, toBeNull, toBeNaN,
 *   toBeInstanceOf
 * Plus tests with no expect at all.
 *
 * Strong matchers (any in the chain → test passes) — pin a value, error, or
 * structural shape:
 *   toBe, toEqual, toStrictEqual, toMatch, toMatchObject, toMatchSnapshot,
 *   toMatchInlineSnapshot, toHaveLength, toThrow, toThrowError,
 *   toHaveBeenCalled*, toContain*, toHaveProperty, toHaveTextContent,
 *   toBeVisible/Hidden, toHaveValue, toHaveAttribute, toHaveClass,
 *   toBeChecked, toBeDisabled, toBeEnabled, toBeFocused, toBeInTheDocument,
 *   toBeGreater/Less*, toBeCloseTo, toBeOneOf, toContainText, toHaveURL,
 *   toHaveTitle, toHaveCount, rejects/resolves chains.
 *
 * Ratchet baseline: existing offenders in apps/web/scripts/.weak-baseline.txt
 * are ignored. Only NEW offenders fail. Trim the baseline as tests get fixed.
 *
 * Usage:
 *   node scripts/check-weak-assertions.mjs
 *   node scripts/check-weak-assertions.mjs --write-baseline
 */

import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const ROOT = path.resolve(process.cwd());
const SCAN_ROOTS = [path.join(ROOT, "src"), path.join(ROOT, "e2e")];
const BASELINE = path.join(ROOT, "scripts", ".weak-baseline.txt");

const WEAK_MATCHERS = new Set([
  "toBeTruthy",
  "toBeFalsy",
  "toBeDefined",
  "toBeUndefined",
  "toBeNull",
  "toBeNaN",
  "toBeInstanceOf",
]);

const STRONG_MATCHERS = new Set([
  "toBe",
  "toEqual",
  "toStrictEqual",
  "toMatch",
  "toMatchObject",
  "toMatchSnapshot",
  "toMatchInlineSnapshot",
  "toMatchFileSnapshot",
  "toHaveLength",
  "toThrow",
  "toThrowError",
  "toHaveBeenCalled",
  "toHaveBeenCalledTimes",
  "toHaveBeenCalledWith",
  "toHaveBeenLastCalledWith",
  "toHaveBeenNthCalledWith",
  "toContain",
  "toContainEqual",
  "toContainText",
  "toHaveProperty",
  "toHaveTextContent",
  "toBeVisible",
  "toBeHidden",
  "toBeAttached",
  "toHaveValue",
  "toHaveAttribute",
  "toHaveClass",
  "toBeChecked",
  "toBeDisabled",
  "toBeEnabled",
  "toBeFocused",
  "toBeInTheDocument",
  "toBeGreaterThan",
  "toBeGreaterThanOrEqual",
  "toBeLessThan",
  "toBeLessThanOrEqual",
  "toBeCloseTo",
  "toBeOneOf",
  "toHaveURL",
  "toHaveTitle",
  "toHaveCount",
  "toHaveScreenshot",
]);

const TEST_FN_NAMES = new Set(["it", "test"]);

function* walkFiles(dir) {
  if (!fs.existsSync(dir)) return;
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    if (ent.name === "node_modules" || ent.name.startsWith(".")) continue;
    const full = path.join(dir, ent.name);
    if (ent.isDirectory()) {
      yield* walkFiles(full);
    } else if (/\.(test|spec)\.(ts|tsx|mts)$/.test(ent.name)) {
      yield full;
    }
  }
}

/** Pull the matcher name off an `expect(x).chain.<matcher>(...)` call. */
function classifyExpectCall(expr) {
  // expr: CallExpression at the tail of an expect chain
  let node = expr.expression;
  let lastMatcher = null;
  let sawStrong = false;
  let sawWeak = false;
  let chainDepth = 0;

  while (ts.isPropertyAccessExpression(node) || ts.isCallExpression(node)) {
    if (ts.isPropertyAccessExpression(node)) {
      const name = node.name.escapedText?.toString() ?? "";
      if (name === "rejects" || name === "resolves") {
        sawStrong = true;
      } else if (name && name !== "not") {
        if (lastMatcher === null) lastMatcher = name;
        if (STRONG_MATCHERS.has(name)) sawStrong = true;
        if (WEAK_MATCHERS.has(name)) sawWeak = true;
      }
      node = node.expression;
    } else if (ts.isCallExpression(node)) {
      node = node.expression;
      chainDepth++;
      if (chainDepth > 50) break;
    }
  }

  if (
    !ts.isIdentifier(node) ||
    (node.escapedText !== "expect" && node.escapedText !== "expectAsync")
  ) {
    return null;
  }
  return { sawStrong, sawWeak, lastMatcher };
}

function findTestFunctions(sourceFile) {
  const tests = [];
  function visit(node) {
    if (
      ts.isCallExpression(node) &&
      ts.isIdentifier(node.expression) &&
      TEST_FN_NAMES.has(node.expression.escapedText?.toString()) &&
      node.arguments.length >= 2
    ) {
      const titleArg = node.arguments[0];
      const bodyArg = node.arguments[node.arguments.length - 1];
      if (
        ts.isStringLiteralLike(titleArg) &&
        (ts.isFunctionExpression(bodyArg) || ts.isArrowFunction(bodyArg))
      ) {
        tests.push({ title: titleArg.text, body: bodyArg, node });
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
  return tests;
}

const HELPER_PREFIX = /^(expect|assert|verify|check)([A-Z_]|$)/;

function isDelegatedAssertion(callExpr) {
  // Calls like `chatPage.expectSendDisabled()` or `helpers.assertX(...)` —
  // method name signals an assertion the helper performs internally.
  const fn = callExpr.expression;
  if (ts.isPropertyAccessExpression(fn)) {
    const name = fn.name.escapedText?.toString() ?? "";
    if (HELPER_PREFIX.test(name)) return true;
  }
  if (ts.isIdentifier(fn) && HELPER_PREFIX.test(fn.escapedText?.toString() ?? "")) {
    return true;
  }
  return false;
}

function classifyTest(testNode) {
  let strong = 0;
  let weak = 0;
  let expects = 0;
  function visit(node) {
    if (ts.isCallExpression(node)) {
      const result = classifyExpectCall(node);
      if (result) {
        expects++;
        if (result.sawStrong) strong++;
        else if (result.sawWeak) weak++;
      } else if (isDelegatedAssertion(node)) {
        expects++;
        strong++;
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(testNode.body);
  if (expects === 0) return "no_assertions";
  if (strong === 0) return "only_weak_assertions";
  return null;
}

function scanFile(filePath) {
  const source = fs.readFileSync(filePath, "utf8");
  const sf = ts.createSourceFile(filePath, source, ts.ScriptTarget.Latest, true);
  const offenders = [];
  for (const t of findTestFunctions(sf)) {
    const verdict = classifyTest(t);
    if (verdict) {
      const { line } = sf.getLineAndCharacterOfPosition(t.node.getStart());
      offenders.push({
        file: path.relative(ROOT, filePath),
        line: line + 1,
        title: t.title,
        verdict,
      });
    }
  }
  return offenders;
}

function loadBaseline() {
  if (!fs.existsSync(BASELINE)) return new Set();
  return new Set(
    fs
      .readFileSync(BASELINE, "utf8")
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l && !l.startsWith("#")),
  );
}

function offenderKey(o) {
  return `${o.file}::${o.title}`;
}

function main() {
  const writeBaseline = process.argv.includes("--write-baseline");

  const offenders = [];
  for (const root of SCAN_ROOTS) {
    for (const file of walkFiles(root)) {
      offenders.push(...scanFile(file));
    }
  }

  if (writeBaseline) {
    const keys = [...new Set(offenders.map(offenderKey))].sort();
    fs.mkdirSync(path.dirname(BASELINE), { recursive: true });
    fs.writeFileSync(
      BASELINE,
      "# Existing weak-assertion offenders; trim as tests get fixed.\n" +
        "# Each line: <relative_path>::<test_title>\n" +
        keys.join("\n") +
        (keys.length ? "\n" : ""),
    );
    console.log(`Wrote ${keys.length} entries to ${path.relative(ROOT, BASELINE)}`);
    return 0;
  }

  const baseline = loadBaseline();
  const newOnes = offenders.filter((o) => !baseline.has(offenderKey(o)));

  if (newOnes.length > 0) {
    console.log(
      `\n${newOnes.length} test(s) with weak-only or missing expectations:\n`,
    );
    for (const o of newOnes) {
      console.log(`  ${o.file}:${o.line}  "${o.title}"  [${o.verdict}]`);
    }
    console.log(
      "\nFix by adding at least one strong matcher: toEqual, toBe (with a literal), " +
        "toMatchObject, toThrow, toHaveBeenCalledWith, toBeVisible, toHaveValue, " +
        "toHaveTextContent, toHaveLength, etc.",
    );
    if (baseline.size > 0) {
      console.log(
        `\nBaseline at ${path.relative(ROOT, BASELINE)} suppresses ${baseline.size} pre-existing offender(s).`,
      );
    }
    return 1;
  }

  console.log(
    `weak-assertion check passed: ${offenders.length} pre-existing offender(s) ignored via baseline.`,
  );
  return 0;
}

process.exit(main());
