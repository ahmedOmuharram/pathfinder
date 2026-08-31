"use client";

import type { ToolUIPart, UIMessage } from "ai";
import type { ReactElement, ReactNode } from "react";
import {
  buildTrace,
  type MessagePart,
  type TraceRowStatus,
} from "@pathfinder/assistant-client";
import type { DataSubAgentCallPayload } from "@pathfinder/shared";
import { subAgentCallPayloadSchema } from "@pathfinder/shared/generated/zod/subAgentCallPayloadSchema";

import { Trace, type TraceRunView } from "@/lib/components/thread/Trace";
import { TraceGroup } from "@/lib/components/thread/TraceGroup";
import type { TraceGroupView, TraceRowView } from "@/lib/components/thread/traceTypes";
import { humanizeToolName } from "@/lib/utils/toolNames";

import { ToolApprovalControls } from "../content/parts/ToolApprovalControls";
import {
  useChatHelpersOptional,
  type ChatHelpers,
} from "../runtime/chatHelpersContext";
import { traceRenderingKinds } from "./traceRenderingKinds";
import { toTraceParts } from "./traceParts";
import { toolUIState } from "./toolUIState";
import { useThreadDevMode, type ThreadDevMode } from "./useThreadDevMode";

type Run = ReturnType<typeof buildTrace>[number];

const LEAD = "lead";
const SUB_AGENT_KIND = "data-sub-agent-call";
const LIVE: readonly ChatHelpers["status"][] = ["submitted", "streaming"];

const ROW_STATUS: Record<ToolUIPart["state"], TraceRowStatus> = {
  "input-streaming": "running",
  "input-available": "running",
  "approval-requested": "awaiting-approval",
  "approval-responded": "running",
  "output-available": "ok",
  "output-error": "error",
  "output-denied": "denied",
};

export interface TraceAnchorProps {
  toolCallId: string;
  toolName: string;
  args: unknown;
  result?: unknown;
  status: { type: "running" | "complete" | "incomplete" | "requires-action" };
}

/** A dispatch payload the wire's own schema accepts, or null. */
function readSubAgentCall(data: unknown): DataSubAgentCallPayload | null {
  const parsed = subAgentCallPayloadSchema.safeParse(data);
  return parsed.success ? parsed.data : null;
}

/** The id a part anchors, or null when the part bears no row of its own. */
function anchorIdOf(part: MessagePart): string | null {
  if ("toolCallId" in part) return part.toolCallId;
  if (part.type === SUB_AGENT_KIND)
    return readSubAgentCall(part.data)?.toolCallId ?? null;
  return null;
}

function idsOf(run: Run): Set<string> {
  const ids = new Set<string>();
  for (const group of run.groups) {
    if (group.key !== LEAD) ids.add(group.key);
    for (const row of group.rows) ids.add(row.toolCallId);
  }
  return ids;
}

function firstAnchorOf(
  parts: readonly MessagePart[],
  ids: ReadonlySet<string>,
): string | null {
  for (const part of parts) {
    const id = anchorIdOf(part);
    if (id !== null && ids.has(id)) return id;
  }
  return null;
}

/** Every approval the run carries. A row with none renders nothing. */
function approvalsOf(run: TraceRunView): ReactNode {
  return run.groups
    .flatMap((group) => group.rows)
    .map((row) => (
      <ToolApprovalControls key={row.toolCallId} toolCallId={row.toolCallId} />
    ));
}

function drawRun(run: TraceRunView, dev: ThreadDevMode): ReactElement {
  return (
    <Trace
      run={run}
      showRaw={dev.showRaw}
      showUsage={dev.showUsage}
      nameFor={humanizeToolName}
      approval={approvalsOf(run)}
    />
  );
}

/** Every turn is over but the live one, which is the thread's last message. */
function turnEnded(chat: ChatHelpers, message: UIMessage): boolean {
  if (!LIVE.includes(chat.status)) return true;
  return chat.messages.at(-1) !== message;
}

/**
 * Draw the whole run the anchored part belongs to, and only at the run's first
 * row-bearing part, so a turn's calls read as one block wherever they arrived.
 */
function anchored(
  chat: ChatHelpers,
  anchorId: string,
  dev: ThreadDevMode,
): ReactElement | null {
  for (const message of chat.messages) {
    const parts = toTraceParts(message.parts);
    if (!parts.some((part) => anchorIdOf(part) === anchorId)) continue;
    const run = buildTrace(parts, {
      renderingKinds: traceRenderingKinds(),
      turnEnded: turnEnded(chat, message),
    }).find((each) => idsOf(each).has(anchorId));
    if (run === undefined) return null;
    if (firstAnchorOf(parts, idsOf(run)) !== anchorId) return null;
    return drawRun(run, dev);
  }
  return null;
}

/** One row for one call, for a thread rendered outside a chat runtime. */
function loneRun(props: TraceAnchorProps): TraceRunView {
  const status = ROW_STATUS[toolUIState(props.status.type, props.result)];
  const row: TraceRowView = {
    key: props.toolCallId,
    toolCallId: props.toolCallId,
    toolName: props.toolName,
    summary: null,
    status,
    input: props.args,
    output: props.result ?? null,
    errorText: null,
  };
  return {
    groups: [
      {
        key: LEAD,
        phase: LEAD,
        rows: [row],
        tokens: 0,
        costUsd: "0",
        state: "started",
      },
    ],
    rowCount: 1,
    running: status === "running" || status === "awaiting-approval",
  };
}

function loneGroup(data: DataSubAgentCallPayload): TraceGroupView {
  return {
    key: data.toolCallId,
    phase: data.phase,
    rows: [],
    tokens: data.tokens ?? 0,
    costUsd: data.costUsd ?? "0",
    state: data.state,
  };
}

export function TraceAnchor(props: TraceAnchorProps): ReactElement | null {
  const chat = useChatHelpersOptional();
  const dev = useThreadDevMode();
  if (chat === null) return drawRun(loneRun(props), dev);
  return anchored(chat, props.toolCallId, dev);
}

export function SubAgentTraceAnchor({
  data,
}: {
  data: DataSubAgentCallPayload;
}): ReactElement | null {
  const chat = useChatHelpersOptional();
  const dev = useThreadDevMode();
  const call = readSubAgentCall(data);
  if (call === null) return null;
  if (chat === null) {
    return (
      <TraceGroup
        group={loneGroup(call)}
        bare={false}
        showRaw={dev.showRaw}
        showUsage={dev.showUsage}
        nameFor={humanizeToolName}
      />
    );
  }
  return anchored(chat, call.toolCallId, dev);
}
