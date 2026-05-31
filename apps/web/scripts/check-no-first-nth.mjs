#!/usr/bin/env node
/**
 * Fail if any *.spec.ts file under e2e/ contains `.first(` / `.nth(` /
 * `.last(`. These calls hide strict-mode locator violations — fix by
 * using a more specific locator (getByRole+name, getByTestId, scoped
 * within(...), or a structural CSS attribute selector).
 *
 * Lines explicitly tagged with `// TODO(weak-strict-mode):` (on the
 * offending line, or the line directly above) are exempt. Add such a
 * marker only when you genuinely cannot disambiguate the locator from
 * the test alone — every entry should track to follow-up work.
 */

import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(process.cwd());
const SCAN_ROOT = path.join(ROOT, "e2e");
const PATTERN = /\.(first|nth|last)\(/;
const TODO_MARKER = "TODO(weak-strict-mode)";

function* walk(dir) {
  if (!fs.existsSync(dir)) return;
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    if (ent.name.startsWith(".") || ent.name === "node_modules") continue;
    const full = path.join(dir, ent.name);
    if (ent.isDirectory()) yield* walk(full);
    else if (ent.name.endsWith(".spec.ts")) yield full;
  }
}

function offendersInFile(file) {
  const lines = fs.readFileSync(file, "utf8").split("\n");
  const offenders = [];
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (!PATTERN.test(line)) continue;
    if (line.includes(TODO_MARKER)) continue;
    // Allow a multi-line TODO(weak-strict-mode) comment block immediately
    // above the offending line: walk back through comment lines until we
    // hit code or a non-// line. Exempt if the comment block contains the
    // TODO marker.
    let exempt = false;
    for (let j = i - 1; j >= 0; j -= 1) {
      const above = lines[j].trim();
      if (
        above === "" ||
        above.startsWith("//") ||
        above.startsWith("*") ||
        above.startsWith("/*")
      ) {
        if (above.includes(TODO_MARKER)) {
          exempt = true;
          break;
        }
        if (above === "" || above.startsWith("/*")) break;
        continue;
      }
      break;
    }
    if (exempt) continue;
    offenders.push({
      file: path.relative(ROOT, file),
      lineNumber: i + 1,
      text: line.trim(),
    });
  }
  return offenders;
}

function main() {
  const allOffenders = [];
  for (const file of walk(SCAN_ROOT)) {
    allOffenders.push(...offendersInFile(file));
  }

  if (allOffenders.length === 0) {
    console.log("check-no-first-nth: 0 offenders.");
    return 0;
  }

  console.log(
    `\n${allOffenders.length} strict-mode escape(s) (\\.first|nth|last\\() found in *.spec.ts:\n`,
  );
  for (const o of allOffenders) {
    console.log(`  ${o.file}:${o.lineNumber}  ${o.text}`);
  }
  console.log(
    "\nFix: replace with a more specific locator (getByRole+name, getByTestId, " +
      "scoped within(...), or a structural CSS attribute selector).\n" +
      "If you genuinely cannot disambiguate from the test alone, prefix the " +
      "line with `// TODO(weak-strict-mode): <reason>` and create a follow-up.",
  );
  return 1;
}

process.exit(main());
