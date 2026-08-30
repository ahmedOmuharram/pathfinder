import type { ToolUIPart } from "ai";

/** The call state assistant-ui's status and result describe together. */
export function toolUIState(
  statusType: "running" | "complete" | "incomplete" | "requires-action",
  result: unknown,
): ToolUIPart["state"] {
  if (result !== undefined) return "output-available";
  if (statusType === "requires-action") return "approval-requested";
  if (statusType === "running") return "input-available";
  if (statusType === "incomplete") return "output-error";
  return "input-streaming";
}
