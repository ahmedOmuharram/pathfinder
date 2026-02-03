"use client";

import { Handle, Position } from "reactflow";
import type { StrategyStep } from "@/types/strategy";
import { inferStepKind } from "@/core/strategyGraph";
import { OpBadge } from "./OpBadge";
import { AlertTriangle, MessageSquarePlus } from "lucide-react";
import { getZeroResultSuggestions } from "@/features/strategy/validation/zeroResultAdvisor";

interface StepNodeProps {
  data: {
    step: StrategyStep;
    onOperatorChange?: (stepId: string, operator: string) => void;
    onAddToChat?: (stepId: string) => void;
    isUnsaved?: boolean;
    onOpenDetails?: (stepId: string) => void;
  };
  selected?: boolean;
}

const TYPE_STYLES: Record<
  string,
  { container: string }
> = {
  search: {
    container:
      "rounded-xl border-2 border-emerald-200 bg-emerald-50/70 shadow-sm",
  },
  combine: {
    container:
      "rounded-[16px] border-2 border-sky-200 bg-sky-50/80 shadow-sm",
  },
  transform: {
    container:
      "rounded-lg border-2 border-violet-300 bg-violet-50/80 shadow-sm",
  },
  default: {
    container: "rounded-lg border-2 border-slate-200 bg-white shadow-sm",
  },
};

export function StepNode({ data, selected }: StepNodeProps) {
  const { step, onOperatorChange, onAddToChat, isUnsaved, onOpenDetails } = data;

  const handleAddToChat = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    onAddToChat?.(step.id);
  };
  const kind = inferStepKind(step);
  const typeStyle = TYPE_STYLES[kind] || TYPE_STYLES.default;
  const isTransform = kind === "transform";

  const validationError = step.validationError;
  const isZeroResults = step.resultCount === 0;
  const resultLabel = step.recordType
    ? `${step.recordType}${step.resultCount === 1 ? "" : "s"}`
    : "results";

  const transformFrameFill = validationError
    ? "rgba(254, 226, 226, 0.6)"
    : "rgba(237, 233, 254, 0.8)";
  const transformFrameStroke = validationError ? "#f87171" : "#c4b5fd";

  return (
    <div
      className={`relative h-28 w-56 px-2 py-2 transition ${
        isTransform
          ? "rounded-lg border-0 bg-transparent shadow-none"
          : typeStyle.container
      } ${selected ? "ring-2 ring-slate-300" : ""} ${
        validationError && !isTransform
          ? "border-red-400 bg-red-50/60 ring-2 ring-red-200"
          : ""
      } ${
        isZeroResults && !validationError && !isTransform
          ? "border-amber-400 bg-amber-50/60 ring-2 ring-amber-200"
          : ""
      }`}
    >
      {isTransform && (
        <svg
          className="pointer-events-none absolute inset-0"
          viewBox="0 0 224 112"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <polygon
            points="2,10 196,10 222,56 196,102 2,102 16,56"
            fill={transformFrameFill}
            stroke={transformFrameStroke}
            strokeWidth={2}
            strokeLinejoin="round"
          />
        </svg>
      )}
      {/* Input handles */}
      {(kind === "combine" || kind === "transform") && (
        <>
          <Handle
            type="target"
            position={Position.Left}
            id="left"
            className="h-3 w-3 border-2 border-white bg-slate-700 z-10"
          />
          {kind === "combine" && (
            <Handle
              type="target"
              position={Position.Left}
              id="left-secondary"
              style={{ top: "70%" }}
              className="h-3 w-3 border-2 border-white bg-slate-500 z-10"
            />
          )}
        </>
      )}

      {/* Output handle */}
      <Handle
        type="source"
        position={Position.Right}
        id="right"
        style={{ top: "50%" }}
        className="h-3 w-3 border-2 border-slate-400 bg-white z-10"
      />

      {/* Content */}
      {isUnsaved && (
        <span
          className="absolute -left-1 -top-1 h-2.5 w-2.5 rounded-full bg-red-400 ring-2 ring-white z-10"
          aria-label="Unsaved changes"
        />
      )}
      <button
        type="button"
        onClick={handleAddToChat}
        className="absolute -right-2 -top-2 inline-flex h-7 w-7 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 shadow-sm transition hover:border-slate-300 hover:text-slate-700 z-10"
        title="Add to chat"
      >
        <MessageSquarePlus className="h-4 w-4" />
        <span className="sr-only">Add to chat</span>
      </button>
      <div className="relative z-10 flex h-full flex-col items-center justify-center gap-1">
        <div
          className="w-full text-center text-sm font-medium leading-tight text-slate-900"
          style={{
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
            textOverflow: "ellipsis",
            overflowWrap: "anywhere",
            wordBreak: "break-word",
          }}
        >
          {step.displayName}
        </div>
        {kind === "search" && step.searchName && (
          <div
            className="w-full text-center text-[11px] leading-tight text-slate-500"
            style={{
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
              textOverflow: "ellipsis",
              overflowWrap: "anywhere",
              wordBreak: "break-word",
            }}
          >
            {step.searchName}
          </div>
        )}
        {kind === "transform" && step.searchName && (
          <div
            className="w-full text-center text-[11px] font-medium leading-tight text-violet-700"
            style={{
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
              textOverflow: "ellipsis",
              overflowWrap: "anywhere",
              wordBreak: "break-word",
            }}
          >
            {step.searchName}
          </div>
        )}
        {kind === "combine" && step.operator && (
          <div className="mt-1 flex items-center gap-2">
            <OpBadge operator={step.operator} size="sm" />
          </div>
        )}
        <div className="mt-1 text-[11px] font-mono text-slate-600">
          {typeof step.resultCount === "number"
            ? `${step.resultCount.toLocaleString()} ${resultLabel}`
            : step.resultCount === null
              ? `? ${resultLabel}`
              : "Loading..."}
        </div>
        {isZeroResults && !validationError && (
          <div className="group relative -mt-1 flex items-center gap-1 text-[10px] font-semibold text-amber-700">
            <AlertTriangle className="h-3.5 w-3.5" />
            <span>0 results</span>
            <div className="pointer-events-none absolute left-1/2 top-full z-50 mt-1 w-56 -translate-x-1/2 rounded-md border border-amber-200 bg-white px-2 py-2 text-[11px] font-medium text-amber-800 opacity-0 shadow-sm transition group-hover:opacity-100">
              <div className="mb-1 font-semibold">Suggestions</div>
              <ul className="list-disc space-y-1 pl-4">
                {getZeroResultSuggestions(step).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </div>
        )}
        {validationError && (
          <div className="mt-1 text-center text-[10px] font-semibold text-red-600">
            {validationError}
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                onOpenDetails?.(step.id);
              }}
              className="ml-1 text-[10px] font-semibold text-red-700 underline decoration-red-300 underline-offset-2 hover:text-red-800"
            >
              View details
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

