import { beforeEach, describe, expect, it } from "vitest";
import fc from "fast-check";
import { useTaskStore } from "./useTaskStore";

type Cmd =
  | { kind: "start"; taskId: string; toolName: string }
  | { kind: "progress"; taskId: string; percent: number }
  | { kind: "complete"; taskId: string; status: "success" | "failed" }
  | { kind: "reset" };

const taskIdArb = fc.string({ minLength: 1, maxLength: 8 });
const toolNameArb = fc.constantFrom(
  "run_control_tests_on_step",
  "optimize_search_parameters",
  "run_gene_set_enrichment",
);

const cmdArb: fc.Arbitrary<Cmd> = fc.oneof(
  fc.record({
    kind: fc.constant("start" as const),
    taskId: taskIdArb,
    toolName: toolNameArb,
  }),
  fc.record({
    kind: fc.constant("progress" as const),
    taskId: taskIdArb,
    percent: fc.float({ min: 0, max: 1, noNaN: true }),
  }),
  fc.record({
    kind: fc.constant("complete" as const),
    taskId: taskIdArb,
    status: fc.constantFrom("success" as const, "failed" as const),
  }),
  fc.constant({ kind: "reset" as const }),
);

describe("useTaskStore — properties", () => {
  beforeEach(() => {
    useTaskStore.getState().reset();
  });

  it("task keys equal the set of started ids since the last reset, and unknown progress/complete are no-ops", () => {
    fc.assert(
      fc.property(fc.array(cmdArb, { minLength: 0, maxLength: 80 }), (cmds) => {
        useTaskStore.getState().reset();
        const startedSinceReset = new Set<string>();
        for (const cmd of cmds) {
          const api = useTaskStore.getState();
          if (cmd.kind === "reset") {
            api.reset();
            startedSinceReset.clear();
          } else if (cmd.kind === "start") {
            api.startTask({
              taskId: cmd.taskId,
              toolName: cmd.toolName,
              startedAt: "2026-04-14T00:00:00Z",
              estimatedDurationSeconds: 30,
            });
            startedSinceReset.add(cmd.taskId);
          } else if (cmd.kind === "progress") {
            api.setProgress(cmd.taskId, { percent: cmd.percent, message: "p" });
            // Invariant: setProgress never adds a new key.
            expect(Object.keys(useTaskStore.getState().tasks).sort()).toEqual(
              [...startedSinceReset].sort(),
            );
          } else {
            api.completeTask(cmd.taskId, cmd.status);
            // Invariant: completeTask never adds a new key.
            expect(Object.keys(useTaskStore.getState().tasks).sort()).toEqual(
              [...startedSinceReset].sort(),
            );
          }
          // Across all commands: the task map's keys exactly equal the
          // started-since-reset set.
          expect(Object.keys(useTaskStore.getState().tasks).sort()).toEqual(
            [...startedSinceReset].sort(),
          );
        }
      }),
      { numRuns: 75 },
    );
  });
});
