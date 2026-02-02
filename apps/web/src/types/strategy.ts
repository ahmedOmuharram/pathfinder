import type { Step, Strategy } from "@pathfinder/shared";

export type StrategyStep = Step & {
  validationError?: string;
};

export type StrategyWithMeta = Strategy & {
  wdkUrl?: string | null;
};
