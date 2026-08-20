import type { DataSubAgentStepPayload } from "@pathfinder/shared";

export interface StepResult {
  tone: "bad" | "neutral";
  text: string;
}

const QUOTED = (field: string): RegExp =>
  new RegExp(`"${field}"\\s*:\\s*"((?:[^"\\\\]|\\\\.)*)"`);

/**
 * Turn a backend ``resultSummary`` (often a truncated JSON error payload or a
 * coded error string) into a clean one-liner for the sub-agent step row, so
 * the rail shows a readable result instead of raw JSON.
 */
export function formatStepResult(raw: string): StepResult {
  const text = raw.trim();

  // Error payloads (``{"ok": false, "message": ..., "details": {"detail": ...}}``),
  // matched by regex so even a truncated payload still yields the message.
  const message = QUOTED("message").exec(text)?.[1];
  if (message !== undefined) {
    const detail = QUOTED("detail").exec(text)?.[1];
    const hasDetail = detail !== undefined && detail !== "" && detail !== message;
    return {
      tone: "bad",
      text: hasDetail ? `${message} — ${detail}` : message,
    };
  }

  // Prefix-coded retries: ``DISCOVERY_ERROR: ...`` / ``TOPOLOGY_ERROR: ...``.
  const codedBody = /^[A-Z][A-Z_]*ERROR:\s*([\s\S]+)$/.exec(text)?.[1];
  if (codedBody !== undefined) return { tone: "bad", text: codedBody.trim() };

  if (text.toLowerCase() === "retry requested") {
    return { tone: "bad", text: "retry requested" };
  }

  return { tone: "neutral", text };
}

interface MessageWithParts {
  parts: readonly { type: string }[];
}

/**
 * Gather a sub-agent's step parts (``data-sub-agent-step``) from the persisted
 * message stream by ``parentToolCallId``. Reading from the message parts — not
 * a transient store — means the steps survive a page refresh.
 */
export function collectSubAgentSteps(
  messages: readonly MessageWithParts[],
  parentToolCallId: string,
): DataSubAgentStepPayload[] {
  const steps: DataSubAgentStepPayload[] = [];
  for (const message of messages) {
    for (const part of message.parts) {
      if (part.type !== "data-sub-agent-step") continue;
      const data = (part as { data?: DataSubAgentStepPayload }).data;
      if (data?.parentToolCallId === parentToolCallId) {
        steps.push(data);
      }
    }
  }
  return steps;
}

export type SubAgentItem =
  | {
      type: "tool";
      key: string;
      toolName: string;
      args: Record<string, unknown> | null;
      result: string | null;
      state: DataSubAgentStepPayload["state"];
    }
  | { type: "reasoning" | "text"; key: string; text: string };

/**
 * Collapse a sub-agent's raw step stream into render-ready items. A tool call
 * arrives as a ``started`` step (carrying ``args``) and a later terminal step
 * (``completed``, ``failed`` or ``denied``, carrying ``resultSummary``); both
 * share a ``toolCallId``. We merge them into one item so each tool call renders
 * as a single expandable card, with input, output and final state, like the
 * Lead's.
 */
export function mergeSubAgentSteps(steps: DataSubAgentStepPayload[]): SubAgentItem[] {
  const items: SubAgentItem[] = [];
  const toolIndex = new Map<string, number>();
  steps.forEach((step, i) => {
    if (step.kind !== "tool") {
      items.push({ type: step.kind, key: `${step.kind}-${i}`, text: step.text ?? "" });
      return;
    }
    const id = step.toolCallId ?? `${step.toolName ?? "tool"}-${i}`;
    const at = toolIndex.get(id);
    if (at === undefined) {
      items.push({
        type: "tool",
        key: id,
        toolName: step.toolName ?? "unknown",
        args: step.args ?? null,
        result: step.resultSummary ?? null,
        state: step.state,
      });
      toolIndex.set(id, items.length - 1);
      return;
    }
    const existing = items[at];
    if (existing?.type !== "tool") return;
    if (step.args !== undefined && step.args !== null) {
      existing.args = step.args;
    }
    if (
      step.resultSummary !== undefined &&
      step.resultSummary !== null &&
      step.resultSummary !== ""
    ) {
      existing.result = step.resultSummary;
    }
    existing.state = step.state;
  });
  return items;
}
