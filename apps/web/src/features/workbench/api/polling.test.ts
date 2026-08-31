import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { getMyQuotaQueryOptions } from "@pathfinder/shared/generated/hooks/useGetMyQuota";
import { authStatusOptions } from "@/lib/api/veupathdb-auth";
import { __makeQueryClientForTests } from "@/lib/query/client";

import { controlSetsOptions } from "./controlSets";
import { geneSetsListOptions } from "./geneSets";

/** No query the workbench keeps open may re-fetch faster than this. */
const SLOWEST_ACCEPTABLE_REFETCH_MS = 30_000;

const client = __makeQueryClientForTests();

interface Schedule {
  staleTime?: unknown;
  refetchInterval?: unknown;
}

const WORKBENCH_QUERIES: readonly (readonly [string, () => Schedule])[] = [
  ["gene-sets", () => client.defaultQueryOptions(geneSetsListOptions("plasmodb"))],
  ["control-sets", () => client.defaultQueryOptions(controlSetsOptions("plasmodb"))],
  ["me/quota", () => client.defaultQueryOptions(getMyQuotaQueryOptions())],
  [
    "veupathdb/auth/status",
    () => client.defaultQueryOptions(authStatusOptions("plasmodb")),
  ],
];

describe("the workbench does not poll", () => {
  for (const [name, schedule] of WORKBENCH_QUERIES) {
    it(`${name} keeps its answer for at least 30 s`, () => {
      expect(schedule().staleTime).toBeGreaterThanOrEqual(
        SLOWEST_ACCEPTABLE_REFETCH_MS,
      );
    });

    it(`${name} asks for no interval re-fetch`, () => {
      expect(schedule().refetchInterval).toBeUndefined();
    });
  }
});

describe("the workbench schedules its re-fetches through the query client", () => {
  it("runs no timer of its own", () => {
    const root = fileURLToPath(new URL("..", import.meta.url));
    const offenders: string[] = [];
    const walk = (dir: string): void => {
      for (const entry of readdirSync(dir, { withFileTypes: true })) {
        const full = join(dir, entry.name);
        if (entry.isDirectory()) {
          walk(full);
          continue;
        }
        if (!/\.tsx?$/.test(entry.name) || /\.test\.tsx?$/.test(entry.name)) continue;
        const source = readFileSync(full, "utf8");
        if (/\bsetInterval\(|\buseInterval\(/.test(source)) offenders.push(full);
      }
    };
    walk(root);
    expect(offenders).toEqual([]);
  });
});
