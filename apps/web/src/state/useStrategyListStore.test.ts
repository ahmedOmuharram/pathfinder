import { beforeEach, describe, expect, it, vi } from "vitest";
import { useStrategyListStore } from "./useStrategyListStore";

describe("state/useStrategyListStore", () => {
  beforeEach(() => {
    useStrategyListStore.setState({
      strategies: [],
      executedStrategies: [],
      graphValidationStatus: {},
    });
  });

  it("adds and updates strategies by id", () => {
    const { addStrategy } = useStrategyListStore.getState();
    addStrategy({
      id: "s1",
      name: "A",
      title: "A",
      siteId: "plasmodb",
      recordType: "gene",
      stepCount: 0,
      createdAt: "t1",
      updatedAt: "t1",
    });
    addStrategy({
      id: "s1",
      name: "A2",
      title: "A2",
      siteId: "plasmodb",
      recordType: "gene",
      stepCount: 1,
      createdAt: "t1",
      updatedAt: "t2",
    });

    const { strategies } = useStrategyListStore.getState();
    expect(strategies).toHaveLength(1);
    expect(strategies[0]).toMatchObject({ id: "s1", name: "A2", stepCount: 1 });
  });

  it("normalizes executed strategy id when missing", () => {
    const nowSpy = vi.spyOn(Date, "now").mockReturnValue(1234);
    const { addExecutedStrategy } = useStrategyListStore.getState();
    addExecutedStrategy({
      id: "",
      name: "Exec",
      siteId: "plasmodb",
      recordType: "gene",
      steps: [],
      rootStepId: null,
      createdAt: "t1",
      updatedAt: "t1",
    });

    const { executedStrategies } = useStrategyListStore.getState();
    expect(executedStrategies).toHaveLength(1);
    expect(executedStrategies[0]?.id).toBe("executed-1234");
    nowSpy.mockRestore();
  });

  it("tracks graph validation status per id", () => {
    const { setGraphValidationStatus } = useStrategyListStore.getState();
    setGraphValidationStatus("s1", true);
    expect(useStrategyListStore.getState().graphValidationStatus).toEqual({ s1: true });
  });
});
