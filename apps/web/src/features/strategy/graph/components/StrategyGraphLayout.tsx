"use client";

import {
  ReactFlow,
  Background,
  ConnectionMode,
  Controls,
  MiniMap,
  Panel,
  SelectionMode,
  type NodeTypes,
} from "@xyflow/react";
import type { Step, StepKind } from "@pathfinder/shared";
import { StepNode } from "@/features/strategy/graph/components/StepNode";
import {
  WarningGroupNode,
  WarningIconNode,
} from "@/features/strategy/graph/components/WarningNodes";
import { GraphToolbar } from "@/features/strategy/graph/components/GraphToolbar";
import { GraphWdkBadge } from "@/features/strategy/graph/components/GraphWdkBadge";
import { StrategyGraphActionButtons } from "@/features/strategy/graph/components/StrategyGraphActionButtons";
import { StrategyGraphDetailsHeader } from "@/features/strategy/graph/components/StrategyGraphDetailsHeader";
import { useStrategyGraphCtx } from "@/features/strategy/graph/StrategyGraphContext";

const NODE_TYPES: NodeTypes = {
  step: StepNode,
  warningGroup: WarningGroupNode,
  warningIcon: WarningIconNode,
};
const FIT_VIEW_OPTIONS = { padding: 0.3 } as const;

const MINIMAP_NODE_COLOR: Record<StepKind, string> = {
  search: "#10b981",
  combine: "#0ea5e9",
  transform: "#8b5cf6",
};

function minimapNodeColor(node: { data?: { step?: { kind?: string } } }): string {
  const kind = node.data?.step?.kind;
  if (kind === "search" || kind === "combine" || kind === "transform") {
    return MINIMAP_NODE_COLOR[kind];
  }
  return "#94a3b8";
}
const SNAP_GRID: [number, number] = [28, 28];

export function StrategyGraphLayout() {
  const g = useStrategyGraphCtx();

  return (
    <div className="flex h-full w-full flex-col">
      {!g.isCompact && <StrategyGraphDetailsHeader />}
      <div className="relative flex-1">
        {!g.isCompact && <StrategyGraphActionButtons />}
        <ReactFlow
          nodes={g.nodes}
          edges={g.edges}
          onNodesChange={g.onNodesChange}
          onEdgesChange={g.onEdgesChange}
          onNodesDelete={g.handleNodesDelete}
          onNodeDragStop={g.handleNodeDragStop}
          onConnect={g.handleConnect}
          isValidConnection={g.isValidConnection}
          nodeTypes={NODE_TYPES}
          defaultEdgeOptions={{ type: "step" }}
          onMoveStart={g.handleMoveStart}
          onPaneClick={() => g.setEdgeMenu(null)}
          onEdgeClick={
            g.isCompact
              ? () => {}
              : (event, edge) => {
                  event.stopPropagation();
                  g.setEdgeMenu({ edge, x: event.clientX, y: event.clientY });
                }
          }
          selectionOnDrag={!g.isCompact && g.interactionMode === "select"}
          selectionMode={SelectionMode.Partial}
          onSelectionChange={({ nodes: selectedNodes }) =>
            g.handleSelectionChange(selectedNodes)
          }
          panOnDrag={g.interactionMode === "pan"}
          connectionMode={ConnectionMode.Loose}
          onNodeClick={
            g.isCompact
              ? () => {}
              : (_, node) => {
                  const data = node.data as { step?: Step } | undefined;
                  const step = data?.step;
                  if (step != null) g.setSelectedStep(step);
                }
          }
          fitView
          fitViewOptions={FIT_VIEW_OPTIONS}
          snapToGrid
          snapGrid={SNAP_GRID}
          minZoom={0.1}
          maxZoom={2}
          colorMode="light"
          connectionRadius={20}
          nodesFocusable={!g.isCompact}
          edgesFocusable={!g.isCompact}
          className="bg-muted"
        >
          <Panel position="top-left">
            <GraphWdkBadge />
          </Panel>
          <Panel position="top-right">
            <GraphToolbar />
          </Panel>
          <Background color="#e2e8f0" gap={28} size={1} />
          {!g.isCompact && (
            <Controls className="bg-card border-border text-muted-foreground" />
          )}
          {!g.isCompact && (
            <MiniMap
              nodeColor={minimapNodeColor}
              maskColor="rgba(0,0,0,0.1)"
              className="rounded-lg border border-border bg-card"
            />
          )}
        </ReactFlow>
      </div>
    </div>
  );
}
