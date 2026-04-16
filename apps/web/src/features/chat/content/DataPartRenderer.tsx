import { match } from "ts-pattern";
import type { DataPartKind, DataPartPayloadMap } from "@pathfinder/shared";
import { createElement, type ReactElement } from "react";

import { dataPartComponents } from "./contentComponents";

function renderKind<K extends DataPartKind>(
  kind: K,
  data: unknown,
): ReactElement {
  return createElement(dataPartComponents[kind], {
    data: data as DataPartPayloadMap[K],
  });
}

// ts-pattern exhaustive dispatch over all 15 data-part kinds.
// If DataPartKind gains a new literal, .exhaustive() fails compilation.
export function DataPartRenderer({
  kind,
  data,
}: {
  kind: DataPartKind;
  data: unknown;
}) {
  return match(kind)
    .with("data-phase-start", (k) => renderKind(k, data))
    .with("data-phase-finish", (k) => renderKind(k, data))
    .with("data-phase-change", (k) => renderKind(k, data))
    .with("data-background-task-started", (k) => renderKind(k, data))
    .with("data-task-progress", (k) => renderKind(k, data))
    .with("data-task-completed", (k) => renderKind(k, data))
    .with("data-strategy-link", (k) => renderKind(k, data))
    .with("data-problem-frame", (k) => renderKind(k, data))
    .with("data-plan-artifact", (k) => renderKind(k, data))
    .with("data-tool-approval-request", (k) => renderKind(k, data))
    .with("data-tool-approval-result", (k) => renderKind(k, data))
    .with("data-memory-retrieved", (k) => renderKind(k, data))
    .with("data-gene-set-created", (k) => renderKind(k, data))
    .with("data-verification-summary", (k) => renderKind(k, data))
    .with("data-conversation-title", (k) => renderKind(k, data))
    .exhaustive();
}
