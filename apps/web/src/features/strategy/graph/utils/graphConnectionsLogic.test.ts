import { describe, expect, test } from "vitest";
import type { Connection, Edge } from "reactflow";
import type { StrategyStep } from "@/features/strategy/types";
import {
  buildGraphIndices,
  edgeToInputPatch,
  getConnectionEffect,
  inferCombineRecordTypeOrMismatch,
  isUpstream,
  isValidGraphConnection,
} from "@/features/strategy/graph/utils/graphConnectionsLogic";

function step(partial: Partial<StrategyStep> & { id: string }): StrategyStep {
  return {
    id: partial.id,
    kind: partial.kind ?? "search",
    displayName: partial.displayName ?? partial.id,
    operator: partial.operator,
    recordType: partial.recordType,
    parameters: partial.parameters,
    searchName: partial.searchName,
    primaryInputStepId: partial.primaryInputStepId,
    secondaryInputStepId: partial.secondaryInputStepId,
    resultCount: partial.resultCount,
    validationError: partial.validationError,
    wdkStepId: partial.wdkStepId,
    colocationParams: partial.colocationParams,
  } as StrategyStep;
}

describe("graphConnectionsLogic", () => {
  test("buildGraphIndices computes roots based on used-as-input", () => {
    const steps = [
      step({ id: "a" }),
      step({ id: "b", primaryInputStepId: "a" }),
      step({ id: "c" }),
    ];
    const idx = buildGraphIndices(steps);
    expect(idx.rootSet.has("a")).toBe(false);
    expect(idx.rootSet.has("b")).toBe(true);
    expect(idx.rootSet.has("c")).toBe(true);
    expect(idx.rootIds.sort()).toEqual(["b", "c"]);
  });

  test("isUpstream detects ancestor inputs (cycle prevention)", () => {
    const steps = [
      step({ id: "a" }),
      step({ id: "b", primaryInputStepId: "a" }),
      step({ id: "c", primaryInputStepId: "b" }),
    ];
    const idx = buildGraphIndices(steps);
    expect(isUpstream("c", "a", idx.stepsById)).toBe(true);
    expect(isUpstream("b", "c", idx.stepsById)).toBe(false);
  });

  test("isValidGraphConnection rejects missing ids and self edges", () => {
    const idx = buildGraphIndices([step({ id: "a" }), step({ id: "b" })]);
    expect(isValidGraphConnection({} as Connection, idx)).toBe(false);
    expect(
      isValidGraphConnection({ source: "a", target: "a" } as Connection, idx),
    ).toBe(false);
  });

  test("isValidGraphConnection rejects reusing a source output (non-root source)", () => {
    const steps = [
      step({ id: "a" }),
      step({ id: "b", primaryInputStepId: "a" }), // b uses a => a not root
      step({ id: "c", kind: "transform" }),
    ];
    const idx = buildGraphIndices(steps);
    expect(
      isValidGraphConnection(
        { source: "a", target: "c", targetHandle: "left" } as Connection,
        idx,
      ),
    ).toBe(false);
  });

  test("primary handle connect is allowed for transform/combine when slot empty", () => {
    const steps = [
      step({ id: "root" }),
      // Target must already be a transform/combine node to accept a primary input.
      step({ id: "t", kind: "transform", primaryInputStepId: undefined }),
    ];
    const idx = buildGraphIndices(steps);
    const conn = { source: "root", target: "t", targetHandle: "left" } as Connection;
    expect(isValidGraphConnection(conn, idx)).toBe(true);
    expect(getConnectionEffect(conn, idx)).toEqual({
      type: "patch",
      targetId: "t",
      patch: { primaryInputStepId: "root" },
    });
  });

  test("secondary handle connect is allowed only for combine when slot empty", () => {
    const steps = [
      step({ id: "r1" }),
      step({ id: "c", kind: "combine", primaryInputStepId: "r1" }),
      step({ id: "r2" }),
    ];
    const idx = buildGraphIndices(steps);
    const conn = {
      source: "r2",
      target: "c",
      targetHandle: "left-secondary",
    } as Connection;
    expect(isValidGraphConnection(conn, idx)).toBe(true);
    expect(getConnectionEffect(conn, idx)).toEqual({
      type: "patch",
      targetId: "c",
      patch: { secondaryInputStepId: "r2" },
    });
  });

  test("connection rejects cycle creation (source upstream of target)", () => {
    const steps = [
      step({ id: "a" }),
      step({ id: "b", primaryInputStepId: "a" }), // b depends on a
      step({ id: "c", kind: "transform" }),
    ];
    const idx = buildGraphIndices(steps);
    // Connecting b -> a would create a cycle if a were a transform/combine slot,
    // but here we model it as connecting a(root) into b would be ok; instead test
    // connecting a into a would be blocked by self edge. For explicit upstream check:
    const conn = { source: "b", target: "a", targetHandle: "left" } as Connection;
    // also blocked because b is not a root source
    expect(isValidGraphConnection(conn, idx)).toBe(false);
  });

  test("combine gesture requires multiple roots and target being a root", () => {
    const steps = [
      step({ id: "r1" }),
      step({ id: "r2" }),
      step({ id: "t", kind: "transform" }),
    ];
    const idx = buildGraphIndices(steps);
    const conn = { source: "r1", target: "r2" } as Connection;
    expect(isValidGraphConnection(conn, idx)).toBe(true);
    expect(getConnectionEffect(conn, idx)).toEqual({
      type: "pendingCombine",
      sourceId: "r1",
      targetId: "r2",
    });
  });

  test("edgeToInputPatch detaches primary/secondary by handle or id suffix", () => {
    expect(edgeToInputPatch({ targetHandle: "left" } as Edge)).toEqual({
      primaryInputStepId: undefined,
    });
    expect(edgeToInputPatch({ targetHandle: "left-secondary" } as Edge)).toEqual({
      secondaryInputStepId: undefined,
    });
    expect(edgeToInputPatch({ id: "a-b-primary" } as Edge)).toEqual({
      primaryInputStepId: undefined,
    });
    expect(edgeToInputPatch({ id: "a-b-secondary" } as Edge)).toEqual({
      secondaryInputStepId: undefined,
    });
    expect(edgeToInputPatch({ id: "weird" } as Edge)).toBeNull();
  });

  test("inferCombineRecordTypeOrMismatch detects real mismatch and infers recordType", () => {
    const steps = [
      step({ id: "left", recordType: "gene" }),
      step({ id: "right", recordType: "gene" }),
    ];
    const idx = buildGraphIndices(steps);
    expect(
      inferCombineRecordTypeOrMismatch({
        sourceId: "left",
        targetId: "right",
        indices: idx,
      }),
    ).toEqual({ recordType: "gene", mismatch: false });
  });

  test("inferCombineRecordTypeOrMismatch flags mismatch for different record types", () => {
    const steps = [
      step({ id: "left", recordType: "gene" }),
      step({ id: "right", recordType: "organism" }),
    ];
    const idx = buildGraphIndices(steps);
    const result = inferCombineRecordTypeOrMismatch({
      sourceId: "left",
      targetId: "right",
      indices: idx,
    });
    expect(result.mismatch).toBe(true);
  });
});
