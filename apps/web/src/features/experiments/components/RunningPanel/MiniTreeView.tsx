import {
  DEFAULT_COMBINE_OPERATOR,
  type PlanStepNode,
  type StepKind,
} from "@pathfinder/shared";
import {
  NODE_W,
  NODE_H,
  COL_GAP,
  ROW_GAP,
  NODE_STYLES,
  MUTATED_STROKE,
  OP_FILL,
  OP_TEXT,
} from "./constants";

interface LayoutNode {
  node: PlanStepNode;
  kind: StepKind;
  label: string;
  x: number;
  y: number;
  subtreeH: number;
  children: LayoutNode[];
}

function getNodeKind(node: PlanStepNode): StepKind {
  if (node.primaryInput && node.secondaryInput) return "combine";
  if (node.primaryInput) return "transform";
  return "search";
}

function truncLabel(s: string, max: number): string {
  return s.length > max ? s.slice(0, max - 1) + "\u2026" : s;
}

function measureSubtree(node: PlanStepNode): { height: number; depth: number } {
  const kind = getNodeKind(node);
  if (kind === "search") return { height: NODE_H, depth: 0 };
  if (kind === "transform") {
    const child = measureSubtree(node.primaryInput!);
    return { height: Math.max(child.height, NODE_H), depth: child.depth + 1 };
  }
  const left = measureSubtree(node.primaryInput!);
  const right = measureSubtree(node.secondaryInput!);
  return {
    height: left.height + right.height + ROW_GAP,
    depth: Math.max(left.depth, right.depth) + 1,
  };
}

function layoutTree(node: PlanStepNode, x: number, yStart: number): LayoutNode {
  const kind = getNodeKind(node);
  const label = node.displayName || node.searchName;

  if (kind === "search") {
    return { node, kind, label, x, y: yStart, subtreeH: NODE_H, children: [] };
  }
  if (kind === "transform") {
    const child = layoutTree(node.primaryInput!, x - NODE_W - COL_GAP, yStart);
    const selfY = child.y + child.subtreeH / 2 - NODE_H / 2;
    return {
      node,
      kind,
      label,
      x,
      y: selfY,
      subtreeH: child.subtreeH,
      children: [child],
    };
  }
  const leftM = measureSubtree(node.primaryInput!);
  const leftChild = layoutTree(node.primaryInput!, x - NODE_W - COL_GAP, yStart);
  const rightChild = layoutTree(
    node.secondaryInput!,
    x - NODE_W - COL_GAP,
    yStart + leftM.height + ROW_GAP,
  );
  const totalH = leftM.height + measureSubtree(node.secondaryInput!).height + ROW_GAP;
  const selfY = yStart + totalH / 2 - NODE_H / 2;
  return {
    node,
    kind,
    label,
    x,
    y: selfY,
    subtreeH: totalH,
    children: [leftChild, rightChild],
  };
}

function flattenLayout(ln: LayoutNode): LayoutNode[] {
  const out: LayoutNode[] = [ln];
  for (const c of ln.children) out.push(...flattenLayout(c));
  return out;
}

interface MiniTreeProps {
  tree: PlanStepNode;
  mutatedNodeIds?: Set<string>;
}

export function MiniTreeView({ tree, mutatedNodeIds }: MiniTreeProps) {
  const measure = measureSubtree(tree);
  const rootX = measure.depth * (NODE_W + COL_GAP);
  const PAD = 12;

  const root = layoutTree(tree, rootX, PAD);
  const allNodes = flattenLayout(root);

  const minX = Math.min(...allNodes.map((n) => n.x));
  const offsetX = -minX + PAD;
  for (const n of allNodes) n.x += offsetX;

  const svgW = rootX + offsetX + NODE_W + PAD;
  const svgH = measure.height + PAD * 2;

  const edges: { x1: number; y1: number; x2: number; y2: number }[] = [];
  function collectEdges(ln: LayoutNode) {
    for (const child of ln.children) {
      edges.push({
        x1: child.x + NODE_W,
        y1: child.y + NODE_H / 2,
        x2: ln.x,
        y2: ln.y + NODE_H / 2,
      });
      collectEdges(child);
    }
  }
  collectEdges(root);

  return (
    <div className="w-full overflow-auto rounded-lg border border-border bg-muted/20 p-2">
      <svg
        viewBox={`0 0 ${svgW} ${svgH}`}
        className="mx-auto block"
        style={{ width: svgW, height: svgH, maxWidth: "100%" }}
        preserveAspectRatio="xMidYMid meet"
      >
        {edges.map((e, i) => (
          <path
            key={i}
            d={`M${e.x1},${e.y1} C${e.x1 + 18},${e.y1} ${e.x2 - 18},${e.y2} ${e.x2},${e.y2}`}
            fill="none"
            stroke="hsl(var(--border))"
            strokeWidth={1.5}
          />
        ))}
        {allNodes.map((ln, i) => {
          const style = NODE_STYLES[ln.kind];
          const rx = ln.kind === "combine" ? 12 : ln.kind === "search" ? 10 : 5;
          const op =
            ln.kind === "combine"
              ? (ln.node.operator ?? DEFAULT_COMBINE_OPERATOR)
              : null;
          const isMutated = mutatedNodeIds?.has(ln.node.id ?? "");
          const stroke = isMutated ? MUTATED_STROKE : style.stroke;
          const sw = isMutated ? 2.5 : 1.5;

          return (
            <g key={i}>
              <rect
                x={ln.x}
                y={ln.y}
                width={NODE_W}
                height={NODE_H}
                rx={rx}
                fill={style.fill}
                stroke={stroke}
                strokeWidth={sw}
              />
              {isMutated && (
                <circle
                  cx={ln.x + NODE_W - 4}
                  cy={ln.y + 4}
                  r={3.5}
                  fill="hsl(var(--chart-3))"
                  stroke="hsl(var(--card))"
                  strokeWidth={1}
                />
              )}
              <text
                x={ln.x + NODE_W / 2}
                y={ln.y + (op ? 13 : NODE_H / 2 + 1)}
                textAnchor="middle"
                dominantBaseline="middle"
                fill={style.textFill}
                style={{ fontSize: 9, fontWeight: 600, fontFamily: "system-ui" }}
              >
                {truncLabel(ln.label, 16)}
              </text>
              {op && (
                <g>
                  <rect
                    x={ln.x + NODE_W / 2 - 20}
                    y={ln.y + NODE_H - 13}
                    width={40}
                    height={12}
                    rx={4}
                    fill={OP_FILL[op] ?? "hsl(var(--muted))"}
                    stroke={OP_TEXT[op] ?? "hsl(var(--muted-foreground))"}
                    strokeWidth={0.8}
                  />
                  <text
                    x={ln.x + NODE_W / 2}
                    y={ln.y + NODE_H - 6.5}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill={OP_TEXT[op] ?? "hsl(var(--muted-foreground))"}
                    style={{ fontSize: 7.5, fontWeight: 700, fontFamily: "monospace" }}
                  >
                    {op}
                  </text>
                </g>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
