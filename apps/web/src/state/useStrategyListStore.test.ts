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

  it("removes strategy by id", () => {
    const { addStrategy, removeStrategy } = useStrategyListStore.getState();
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
      id: "s2",
      name: "B",
      title: "B",
      siteId: "plasmodb",
      recordType: "gene",
      stepCount: 0,
      createdAt: "t1",
      updatedAt: "t1",
    });
    removeStrategy("s1");
    const { strategies } = useStrategyListStore.getState();
    expect(strategies).toHaveLength(1);
    expect(strategies[0]?.id).toBe("s2");
  });

  it("updates existing executed strategy when id matches", () => {
    const { addExecutedStrategy } = useStrategyListStore.getState();
    const strategy1 = {
      id: "exec1",
      name: "Exec 1",
      siteId: "plasmodb",
      recordType: "gene",
      steps: [],
      rootStepId: null,
      createdAt: "t1",
      updatedAt: "t1",
    };
    addExecutedStrategy(strategy1);
    const strategy2 = {
      ...strategy1,
      name: "Exec 1 Updated",
    };
    addExecutedStrategy(strategy2);
    const { executedStrategies } = useStrategyListStore.getState();
    expect(executedStrategies).toHaveLength(1);
    expect(executedStrategies[0]?.name).toBe("Exec 1 Updated");
  });

  it("removes executed strategy by id", () => {
    const { addExecutedStrategy, removeExecutedStrategy } =
      useStrategyListStore.getState();
    addExecutedStrategy({
      id: "exec1",
      name: "Exec 1",
      siteId: "plasmodb",
      recordType: "gene",
      steps: [],
      rootStepId: null,
      createdAt: "t1",
      updatedAt: "t1",
    });
    addExecutedStrategy({
      id: "exec2",
      name: "Exec 2",
      siteId: "plasmodb",
      recordType: "gene",
      steps: [],
      rootStepId: null,
      createdAt: "t1",
      updatedAt: "t1",
    });
    removeExecutedStrategy("exec1");
    const { executedStrategies } = useStrategyListStore.getState();
    expect(executedStrategies).toHaveLength(1);
    expect(executedStrategies[0]?.id).toBe("exec2");
  });
});
