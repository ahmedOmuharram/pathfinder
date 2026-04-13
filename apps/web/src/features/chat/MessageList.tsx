"use client";

import { GroupedVirtuoso } from "react-virtuoso";

import type { PathfinderUIMessage } from "@pathfinder/shared";

import { MessageBubble } from "./MessageBubble";
import { groupMessagesByDay } from "./messageGroups";
import { PartRenderer } from "./parts/PartRenderer";
import { StreamingIndicator } from "./StreamingIndicator";

function needsIndicator(
  messages: PathfinderUIMessage[],
  status: "ready" | "submitted" | "streaming" | "error",
): boolean {
  if (status !== "submitted" && status !== "streaming") return false;
  const last = messages[messages.length - 1];
  if (!last) return false;
  if (last.role !== "assistant") return true;
  return last.parts.length === 0;
}

export function MessageList({
  messages,
  status,
}: {
  messages: PathfinderUIMessage[];
  status: "ready" | "submitted" | "streaming" | "error";
}) {
  const lastIndex = messages.length - 1;
  const { groups, groupCounts } = groupMessagesByDay(messages);
  const streaming = status === "streaming" || status === "submitted";
  const showIndicator = needsIndicator(messages, status);
  const Footer = () =>
    showIndicator ? (
      <div className="mx-auto w-full max-w-3xl px-4">
        <StreamingIndicator />
      </div>
    ) : null;

  return (
    <div
      className="h-full w-full"
      data-testid="message-list"
      data-status={status}
    >
      <GroupedVirtuoso
        style={{ height: "100%" }}
        groupCounts={groupCounts}
        followOutput="smooth"
        initialTopMostItemIndex={Math.max(0, lastIndex)}
        components={{ Footer }}
        groupContent={(groupIndex) => (
          <div
            className="sticky top-0 z-10 mx-auto w-full max-w-3xl bg-background/90 px-4 py-2 backdrop-blur"
            data-testid="day-divider"
            data-group-index={groupIndex}
          >
            <div className="flex items-center gap-3">
              <span className="h-px flex-1 bg-border/60" />
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                {groups[groupIndex]?.label ?? ""}
              </span>
              <span className="h-px flex-1 bg-border/60" />
            </div>
          </div>
        )}
        itemContent={(index) => {
          const message = messages[index];
          if (message === undefined) return null;
          const isLatest = index === lastIndex;
          const isComplete = !isLatest || !streaming;
          return (
            <div className="mx-auto w-full max-w-3xl px-4">
              <MessageBubble
                message={message}
                isLatest={isLatest}
                isComplete={isComplete}
              >
                {message.parts.map((part, i) => (
                  <PartRenderer key={`${message.id}-${i}`} part={part} />
                ))}
              </MessageBubble>
            </div>
          );
        }}
      />
    </div>
  );
}
