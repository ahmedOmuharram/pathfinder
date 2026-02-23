import type { StrategyPlan } from "@pathfinder/shared";
import type { StrategyWithMeta } from "@/features/strategy/types";
import { serializeStrategyPlan } from "@/lib/strategyGraph";
import { AppError } from "@/lib/errors/AppError";

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
