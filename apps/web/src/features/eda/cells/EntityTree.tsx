"use client";

import type { EdaEntityCount } from "@pathfinder/shared";
import type { EdaFilter } from "@pathfinder/shared/generated/types/EdaFilter";
import type { EdaVariableResponse } from "@pathfinder/shared/generated/types/EdaVariableResponse";

import { findFilter, isHiddenFromTree, type EdaEntityNode } from "../filterDrafts";
import { VariableRow } from "./VariableRow";

export interface EntityTreeProps {
  node: EdaEntityNode;
  depth: number;
  counts: readonly EdaEntityCount[];
  variables: readonly EdaVariableResponse[];
  filters: readonly EdaFilter[];
  expanded: ReadonlySet<string>;
  openVariableId: string | null;
  onToggleEntity: (entityId: string) => void;
  onOpenVariable: (variableId: string | null) => void;
  onApply: (filter: EdaFilter) => void;
}

function countLine(counts: readonly EdaEntityCount[], entityId: string): string {
  const row = counts.find((count) => count.entityId === entityId);
  if (row === undefined) return "";
  return `${row.count.toLocaleString("en-US")} of ${row.unfilteredCount.toLocaleString("en-US")}`;
}

export function EntityTree(props: EntityTreeProps) {
  const { node, depth, counts, variables, expanded } = props;
  const isExpanded = expanded.has(node.entityId);
  const own = variables.filter(
    (variable) => variable.entityId === node.entityId && !isHiddenFromTree(variable),
  );
  const line = countLine(counts, node.entityId);
  return (
    <li style={{ paddingLeft: depth * 12 }}>
      <div
        data-testid={`eda-entity-${node.entityId}`}
        className="flex items-baseline gap-2"
      >
        <button
          type="button"
          data-testid={`eda-entity-toggle-${node.entityId}`}
          aria-expanded={isExpanded}
          onClick={() => props.onToggleEntity(node.entityId)}
          className="truncate text-xs font-medium hover:underline"
        >
          {node.displayName}
        </button>
        <span className="text-[11px] tabular-nums text-muted-foreground">{line}</span>
      </div>
      {isExpanded && own.length > 0 ? (
        <ul className="mt-1">
          {own.map((variable) => (
            <VariableRow
              key={variable.variableId}
              variable={variable}
              current={findFilter(
                props.filters,
                variable.entityId,
                variable.variableId,
              )}
              isOpen={props.openVariableId === variable.variableId}
              onOpenChange={(open) =>
                props.onOpenVariable(open ? variable.variableId : null)
              }
              onApply={props.onApply}
            />
          ))}
        </ul>
      ) : null}
      {node.children.length > 0 ? (
        <ul className="mt-1">
          {node.children.map((child) => (
            <EntityTree
              {...props}
              key={child.entityId}
              node={child}
              depth={depth + 1}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}
