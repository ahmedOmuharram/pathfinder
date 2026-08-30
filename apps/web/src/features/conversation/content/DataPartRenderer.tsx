import { match } from "ts-pattern";
import type { DataPartPayloadMap, KnownDataPartKind } from "@pathfinder/shared";
import { createElement, type ReactElement } from "react";

import { dataPartComponents } from "./contentComponents";

function renderKind<K extends KnownDataPartKind>(kind: K, data: unknown): ReactElement {
  return createElement(dataPartComponents[kind], {
    data: data as DataPartPayloadMap[K],
  });
}

// ts-pattern exhaustive dispatch over all KnownDataPartKind literals.
// If KnownDataPartKind gains a new literal, .exhaustive() fails compilation.
export function DataPartRenderer({
  kind,
  data,
}: {
  kind: KnownDataPartKind;
  data: unknown;
}) {
  return match(kind)
    .with("data-sub-agent-call", (k) => renderKind(k, data))
    .with("data-sub-agent-step", (k) => renderKind(k, data))
    .with("data-ledger-update", (k) => renderKind(k, data))
    .with("data-background-task-started", (k) => renderKind(k, data))
    .with("data-task-progress", (k) => renderKind(k, data))
    .with("data-task-completed", (k) => renderKind(k, data))
    .with("data-enrichment-results", (k) => renderKind(k, data))
    .with("data-strategy-link", (k) => renderKind(k, data))
    .with("data-strategy-meta", (k) => renderKind(k, data))
    .with("data-graph-snapshot", (k) => renderKind(k, data))
    .with("data-graph-cleared", (k) => renderKind(k, data))
    .with("data-variant-comparison", (k) => renderKind(k, data))
    .with("data-scored-comparison", (k) => renderKind(k, data))
    .with("data-memory-retrieved", (k) => renderKind(k, data))
    .with("data-gene-set", (k) => renderKind(k, data))
    .with("data-verification-summary", (k) => renderKind(k, data))
    .with("data-conversation-title", (k) => renderKind(k, data))
    .with("data-scratchpad-updated", (k) => renderKind(k, data))
    .with("data-turn-usage", (k) => renderKind(k, data))
    .with("data-turn-status", (k) => renderKind(k, data))
    .with("data-turn-stopped", (k) => renderKind(k, data))
    .with("data-turn-failed", (k) => renderKind(k, data))
    .with("data-lead-usage", (k) => renderKind(k, data))
    .with("data-tool-summary", (k) => renderKind(k, data))
    .with("data-eda.analysis-state", (k) => renderKind(k, data))
    .with("data-eda.subset-preview", (k) => renderKind(k, data))
    .with("data-eda.viz", (k) => renderKind(k, data))
    .exhaustive();
}
