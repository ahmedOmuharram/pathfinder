import type { StrategyPlan } from "@pathfinder/shared";
import type { StrategyWithMeta } from "@/types/strategy";
import { serializeStrategyPlan } from "@/core/strategyGraph";
import { AppError } from "@/shared/errors/AppError";

export function buildDuplicatePlan(args: {
  baseStrategy: StrategyWithMeta;
  name: string;
  description: string;
}): StrategyPlan {
  const { baseStrategy, name, description } = args;
  const stepsById = Object.fromEntries(
    baseStrategy.steps.map((step) => [step.id, step]),
  );
  const serialized = serializeStrategyPlan(stepsById, {
    ...baseStrategy,
    name,
    description,
  });
  if (!serialized) {
    throw new AppError(
      "Failed to serialize strategy for duplication.",
      "SERIALIZE_FAILED",
    );
  }
  return serialized.plan;
}
