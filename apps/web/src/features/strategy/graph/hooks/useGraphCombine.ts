import { useCallback, useState } from "react";
import type { Connection } from "reactflow";
import { CombineOperator } from "@pathfinder/shared";
import type { StrategyStep } from "@/types/strategy";
import { resolveRecordType } from "@/features/strategy/domain/graph";

interface PendingCombine {
  sourceId: string;
  targetId: string;
}

interface UseGraphCombineArgs {
  steps: StrategyStep[];
  addStep: (step: StrategyStep) => void;
  failCombineMismatch: () => void;
}

const generateStepId = () => `step_${Math.random().toString(16).slice(2, 10)}`;

export function useGraphCombine({
  steps,
  addStep,
  failCombineMismatch,
}: UseGraphCombineArgs) {
  const [pendingCombine, setPendingCombine] = useState<PendingCombine | null>(null);

  const handleConnect = useCallback((connection: Connection) => {
    if (!connection.source || !connection.target) return;
    if (connection.source === connection.target) return;
    setPendingCombine({
      sourceId: connection.source,
      targetId: connection.target,
    });
  }, []);

  const handleCombineCreate = useCallback(
    async (operator: CombineOperator) => {
      if (!pendingCombine) return;
      let inferredRecordType: string | null = null;
      if (steps.length) {
        const stepsMap = new Map(steps.map((step) => [step.id, step]));
        const leftType = resolveRecordType(pendingCombine.sourceId, stepsMap);
        const rightType = resolveRecordType(pendingCombine.targetId, stepsMap);
        inferredRecordType = leftType && leftType !== "__mismatch__" ? leftType : rightType;
        if (
          leftType &&
          rightType &&
          leftType !== rightType &&
          leftType !== "__mismatch__" &&
          rightType !== "__mismatch__"
        ) {
          failCombineMismatch();
          setPendingCombine(null);
          return;
        }
      }
      const searchName =
        inferredRecordType && typeof inferredRecordType === "string"
          ? `boolean_question_${inferredRecordType}`
          : "boolean_question";
      const nextStep: StrategyStep = {
        id: generateStepId(),
        kind: "combine",
        displayName: `${operator} combine`,
        searchName,
        operator,
        recordType: inferredRecordType ?? undefined,
        primaryInputStepId: pendingCombine.sourceId,
        secondaryInputStepId: pendingCombine.targetId,
      };
      addStep(nextStep);
      setPendingCombine(null);
    },
    [pendingCombine, steps, addStep, failCombineMismatch]
  );

  const handleCombineCancel = useCallback(() => {
    setPendingCombine(null);
  }, []);

  return {
    pendingCombine,
    handleConnect,
    handleCombineCreate,
    handleCombineCancel,
  };
}
