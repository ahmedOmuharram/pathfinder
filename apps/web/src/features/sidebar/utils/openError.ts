import { APIError } from "@/lib/api/client";

export type OpenStrategyErrorDisposition = {
  message: string;
  removeStrategyId?: string;
  refresh: boolean;
};

export function classifyOpenStrategyError(args: {
  err: unknown;
  payload: { strategyId?: string; wdkStrategyId?: number };
}): OpenStrategyErrorDisposition {
  const { err, payload } = args;

  if (err instanceof APIError && err.status === 403) {
    if (payload.wdkStrategyId) {
      return {
        message:
          "Access denied by VEuPathDB. Sign in to the site before opening WDK strategies.",
        refresh: true,
      };
    }
    if (payload.strategyId) {
      return {
        message:
          "This strategy belongs to a different session. Create a new draft or duplicate it.",
        removeStrategyId: payload.strategyId,
        refresh: true,
      };
    }
    return {
      message: "Access denied. Please refresh and try again.",
      refresh: true,
    };
  }

  return { message: "Failed to open strategy.", refresh: false };
}
