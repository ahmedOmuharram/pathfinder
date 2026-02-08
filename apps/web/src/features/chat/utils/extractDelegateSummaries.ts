import { z } from "zod";
import type { ToolCall } from "@pathfinder/shared";

export interface DelegateSummary {
  task: string;
  steps: Array<{
    stepId?: string;
    displayName?: string;
    searchName?: string;
    recordType?: string;
  }>;
  notes?: string;
}

export interface RejectedDelegateSummary {
  task?: string;
  error?: string;
  details?: string;
}

const DelegatePayloadSchema = z
  .object({
    results: z
      .array(
        z.object({
          task: z.string().optional(),
          steps: z
            .array(
              z.object({
                stepId: z.string().optional(),
                displayName: z.string().optional(),
                searchName: z.string().optional(),
                recordType: z.string().optional(),
              }),
            )
            .optional(),
          notes: z.string().optional(),
        }),
      )
      .optional(),
    rejected: z
      .array(
        z.object({
          task: z.string().optional(),
          error: z.string().optional(),
          details: z.string().optional(),
        }),
      )
      .optional(),
  })
  .passthrough();

const tryParseJson = (value: unknown): Record<string, unknown> | null => {
  if (typeof value !== "string") return null;
  try {
    const parsed = JSON.parse(value);
    return typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
};

export function extractDelegateSummaries(toolCalls: ToolCall[]) {
  const summaries: DelegateSummary[] = [];
  const rejected: RejectedDelegateSummary[] = [];

  for (const toolCall of toolCalls) {
    if (toolCall.name !== "delegate_strategy_subtasks") continue;
    const parsed = DelegatePayloadSchema.safeParse(tryParseJson(toolCall.result));
    if (!parsed.success) continue;

    for (const entry of parsed.data.results ?? []) {
      summaries.push({
        task: entry.task ?? "",
        steps: entry.steps ?? [],
        notes: entry.notes,
      });
    }
    for (const entry of parsed.data.rejected ?? []) {
      rejected.push(entry);
    }
  }

  return { summaries, rejected };
}
