"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";
import type { ToolUIPart } from "ai";

import type {
  DataSubAgentCallPayload,
  DataSubAgentStepPayload,
} from "@pathfinder/shared";
import { cn } from "@/lib/utils/cn";
import { formatUsage } from "@/lib/utils/usageFormat";
import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolInput,
  ToolOutput,
} from "@/components/ai-elements/tool";
import {
  type SubAgentItem,
  collectSubAgentSteps,
  formatStepResult,
  mergeSubAgentSteps,
} from "@/lib/utils/subAgentStep";
import { humanizeToolName } from "@/lib/utils/toolNames";

import { useChatHelpersOptional } from "../../runtime/chatHelpersContext";

const PHASE_LABELS: Record<string, string> = {
  lead: "Lead",
  frame: "Frame",
  execution: "Execution",
  verification: "Verification",
  recover_failed_steps: "Recovery",
};

const STATE_STYLES: Record<DataSubAgentCallPayload["state"], string> = {
  started: "border-primary/30 bg-primary/10",
  completed: "border-success/30 bg-success/10",
  failed: "border-destructive/30 bg-destructive/10",
};

const STATE_DOT: Record<DataSubAgentCallPayload["state"], string> = {
  started: "animate-pulse bg-primary",
  completed: "bg-success",
  failed: "bg-destructive",
};

export function SubAgentCallCard({ data }: { data: DataSubAgentCallPayload }) {
  const label = PHASE_LABELS[data.phase] ?? data.phase;
  const chat = useChatHelpersOptional();
  const steps = collectSubAgentSteps(chat?.messages ?? [], data.toolCallId);
  const [expanded, setExpanded] = useState(false);
  const stepCount = steps.length;
  const showToggle = stepCount > 0 || data.modelId !== "";

  return (
    <div
      data-testid="data-sub-agent-call"
      className={`my-2 rounded-md border text-xs ${STATE_STYLES[data.state]}`}
    >
      <button
        type="button"
        onClick={() => setExpanded((p) => !p)}
        disabled={!showToggle}
        className="flex w-full items-center gap-2 px-3 py-2 text-left disabled:cursor-default"
      >
        {showToggle ? (
          expanded ? (
            <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
          )
        ) : (
          <span className="w-3 shrink-0" />
        )}
        <span
          className={`inline-block size-2 shrink-0 rounded-full ${STATE_DOT[data.state]}`}
        />
        <span className="font-medium text-foreground">{label}</span>
        <span className="text-muted-foreground">· {data.state}</span>
        <div className="ml-auto flex items-center gap-1.5">
          {(data.tokens ?? 0) > 0 && (
            <span className="font-mono text-[10px] text-muted-foreground tabular-nums">
              {formatUsage(data.tokens ?? 0, data.costUsd ?? "0")}
            </span>
          )}
          {data.modelId !== "" && (
            <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
              {data.modelId}
            </span>
          )}
        </div>
      </button>
      {data.summary !== "" && (
        <div className="px-3 pb-2 text-muted-foreground">{data.summary}</div>
      )}
      {expanded && stepCount > 0 && (
        <div className="space-y-1.5 border-t border-border/60 bg-background/50 px-3 py-2">
          {mergeSubAgentSteps(steps).map((item) => (
            <SubAgentStepItem key={item.key} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}

function subAgentToolState(
  state: DataSubAgentStepPayload["state"],
): ToolUIPart["state"] {
  if (state === "completed") return "output-available";
  if (state === "failed") return "output-error";
  if (state === "denied") return "output-denied";
  return "input-available";
}

function SubAgentStepItem({ item }: { item: SubAgentItem }) {
  if (item.type !== "tool") {
    const isReasoning = item.type === "reasoning";
    return (
      <div className="flex items-start gap-2 text-[11px]">
        <span
          className={cn(
            "mt-1 inline-block size-1.5 shrink-0 rounded-full",
            isReasoning ? "bg-warning" : "bg-foreground/40",
          )}
        />
        <div
          className={cn(
            "min-w-0 flex-1",
            isReasoning ? "italic text-muted-foreground" : "text-foreground",
          )}
        >
          {item.text}
        </div>
      </div>
    );
  }
  const isError = item.state === "failed";
  const result = meaningfulResult(item.result);
  const formatted = result !== null ? formatStepResult(result) : null;
  return (
    <Tool className="mb-0 bg-card/40">
      <ToolHeader
        title={humanizeToolName(item.toolName)}
        type={`tool-${item.toolName}`}
        state={subAgentToolState(item.state)}
      />
      <ToolContent>
        {item.args !== null && <ToolInput input={item.args} />}
        <ToolOutput
          output={isError ? null : result}
          errorText={isError ? (formatted?.text ?? "Failed") : undefined}
        />
      </ToolContent>
    </Tool>
  );
}

const EMPTY_RESULTS = new Set(["null", "none", "undefined", ""]);

function meaningfulResult(raw: string | null): string | null {
  if (raw === null) return null;
  const trimmed = raw.trim();
  return EMPTY_RESULTS.has(trimmed.toLowerCase()) ? null : trimmed;
}
