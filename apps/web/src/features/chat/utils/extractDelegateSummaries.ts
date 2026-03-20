import { z } from "zod";
import type { ToolCall } from "@pathfinder/shared";
import { parseJsonRecord } from "@/features/chat/utils/parseJson";

export interface DelegateSummary {
  task: string;
  steps: Array<{
    stepId?: string;
    displayName?: string;
    searchName?: string;
    recordType?: string;
  }>;
  notes?: string;
  instructions?: string;
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
          instructions: z.string().optional(),
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

export function extractDelegateSummaries(toolCalls: ToolCall[]) {
  const summaries: DelegateSummary[] = [];
  const rejected: RejectedDelegateSummary[] = [];

  for (const toolCall of toolCalls) {
    if (toolCall.name !== "delegate_strategy_subtasks") continue;
    const parsed = DelegatePayloadSchema.safeParse(parseJsonRecord(toolCall.result));
    if (!parsed.success) continue;

    for (const entry of parsed.data.results ?? []) {
      const steps: DelegateSummary["steps"] = (entry.steps ?? []).map((s) => ({
        ...(s.stepId != null ? { stepId: s.stepId } : {}),
        ...(s.displayName != null ? { displayName: s.displayName } : {}),
        ...(s.searchName != null ? { searchName: s.searchName } : {}),
        ...(s.recordType != null ? { recordType: s.recordType } : {}),
      }));
      summaries.push({
        task: entry.task ?? "",
        steps,
        ...(entry.notes != null ? { notes: entry.notes } : {}),
        ...(entry.instructions != null ? { instructions: entry.instructions } : {}),
      });
    }
    for (const entry of parsed.data.rejected ?? []) {
      const rejectedEntry: RejectedDelegateSummary = {
        ...(entry.task != null ? { task: entry.task } : {}),
        ...(entry.error != null ? { error: entry.error } : {}),
        ...(entry.details != null ? { details: entry.details } : {}),
      };
      rejected.push(rejectedEntry);
    }
  }

  return { summaries, rejected };
}
