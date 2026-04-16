"use client";

import {
  MessagePrimitive,
  type DataMessagePartComponent,
  type ReasoningMessagePartComponent,
  type TextMessagePartComponent,
  type ToolCallMessagePartComponent,
} from "@assistant-ui/react";
import type { DataPartKind } from "@pathfinder/shared";

import {
  Message,
  MessageContent,
  MessageResponse,
} from "@/components/ai-elements/message";
import {
  Reasoning,
  ReasoningContent,
  ReasoningTrigger,
} from "@/components/ai-elements/reasoning";
import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolInput,
  ToolOutput,
} from "@/components/ai-elements/tool";
import type { ToolUIPart } from "ai";

import { DataPartRenderer } from "./DataPartRenderer";
import { ModelBadge } from "./ModelBadge";
import { dataPartComponents } from "./contentComponents";

const Text: TextMessagePartComponent = ({ text }) => (
  <MessageResponse>{text}</MessageResponse>
);

const ReasoningPart: ReasoningMessagePartComponent = ({ text, status }) => (
  <Reasoning isStreaming={status.type === "running"}>
    <ReasoningTrigger />
    <ReasoningContent>{text}</ReasoningContent>
  </Reasoning>
);

function toolUIState(
  statusType: "running" | "complete" | "incomplete" | "requires-action",
  result: unknown,
): ToolUIPart["state"] {
  if (result !== undefined) return "output-available";
  if (statusType === "running") return "input-available";
  if (statusType === "requires-action") return "input-available";
  if (statusType === "incomplete") return "output-error";
  return "input-streaming";
}

const ToolCall: ToolCallMessagePartComponent<unknown, unknown> = ({
  toolName,
  args,
  result,
  status,
}) => {
  const state = toolUIState(status.type, result);
  const errorText =
    status.type === "incomplete" && "error" in status && status.error != null
      ? String(status.error)
      : undefined;
  return (
    <Tool data-testid="tool-call-part">
      <ToolHeader title={toolName} type={`tool-${toolName}`} state={state} />
      <ToolContent>
        <ToolInput input={args as ToolUIPart["input"]} />
        <ToolOutput output={result} errorText={errorText} />
      </ToolContent>
    </Tool>
  );
};

function DataFallback({ name, data }: { name: string; data: unknown }) {
  if (name in dataPartComponents) {
    return <DataPartRenderer kind={name as DataPartKind} data={data} />;
  }
  return (
    <div
      data-testid="data-unknown"
      className="my-1 text-xs text-muted-foreground"
    >
      [{name}]
    </div>
  );
}

const dataByName: Record<string, DataMessagePartComponent<unknown>> = {};
for (const kind of Object.keys(dataPartComponents)) {
  const kindTyped = kind as DataPartKind;
  dataByName[kindTyped] = (({ data }: { data: unknown }) => (
    <DataPartRenderer kind={kindTyped} data={data} />
  )) as DataMessagePartComponent<unknown>;
}

const contentComponents = {
  Text,
  Reasoning: ReasoningPart,
  tools: { Fallback: ToolCall },
  data: { by_name: dataByName, Fallback: DataFallback },
} as const;

export function UserMessage() {
  return (
    <Message from="user">
      <MessageContent>
        <MessagePrimitive.Content components={contentComponents} />
      </MessageContent>
    </Message>
  );
}

export function AssistantMessage() {
  return (
    <Message from="assistant">
      <MessageContent>
        <ModelBadge />
        <MessagePrimitive.Content components={contentComponents} />
      </MessageContent>
    </Message>
  );
}
