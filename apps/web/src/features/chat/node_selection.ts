type UnknownRecord = Record<string, unknown>;

export type NodeSelection = {
  graphId?: string;
  nodeIds: string[];
  selectedNodeIds: string[];
  contextNodeIds: string[];
  nodes: UnknownRecord[];
  edges: UnknownRecord[];
};

const NODE_PREFIX = "__NODE__";

const asStringArray = (value: unknown): string[] =>
  Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];

export function normalizeNodeSelection(data: UnknownRecord): NodeSelection {
  const nodeIds = asStringArray(data.nodeIds);
  const selectedNodeIds = asStringArray(data.selectedNodeIds);
  const contextNodeIds = asStringArray(data.contextNodeIds);
  const nodes = Array.isArray(data.nodes) ? (data.nodes as UnknownRecord[]) : [];
  const edges = Array.isArray(data.edges) ? (data.edges as UnknownRecord[]) : [];

  const fallbackNodeIds =
    nodeIds.length > 0 ? nodeIds : typeof data.id === "string" ? [data.id] : [];
  const normalizedSelected =
    selectedNodeIds.length > 0 ? selectedNodeIds : fallbackNodeIds;
  const normalizedNodes =
    nodes.length > 0 ? nodes : fallbackNodeIds.map((id) => ({ id, displayName: id }));

  const withSelection = normalizedNodes.map((node) => {
    if (!node || typeof node !== "object") return node;
    const id = (node as { id?: string }).id;
    const selected =
      typeof (node as { selected?: boolean }).selected === "boolean"
        ? (node as { selected?: boolean }).selected
        : id
          ? normalizedSelected.includes(id)
          : false;
    return { ...node, selected };
  });

  return {
    graphId: typeof data.graphId === "string" ? data.graphId : undefined,
    nodeIds: fallbackNodeIds,
    selectedNodeIds: normalizedSelected,
    contextNodeIds,
    nodes: withSelection,
    edges,
  };
}

export function decodeNodeSelection(content: string): {
  selection: NodeSelection | null;
  message: string;
} {
  if (!content.startsWith(NODE_PREFIX)) {
    return { selection: null, message: content };
  }
  const raw = content.slice(NODE_PREFIX.length);
  const newlineIndex = raw.indexOf("\n");
  const jsonPart = newlineIndex === -1 ? raw.trim() : raw.slice(0, newlineIndex).trim();
  const textPart = newlineIndex === -1 ? "" : raw.slice(newlineIndex + 1).trim();

  if (!jsonPart) {
    return { selection: null, message: textPart };
  }
  try {
    const data = JSON.parse(jsonPart) as UnknownRecord;
    return { selection: normalizeNodeSelection(data), message: textPart };
  } catch {
    return { selection: null, message: content };
  }
}

export function encodeNodeSelection(
  selection: UnknownRecord | null | undefined,
  message: string,
): string {
  if (!selection) return message;
  const payload = JSON.stringify(selection);
  return message.trim().length > 0
    ? `${NODE_PREFIX}${payload}\n${message}`
    : `${NODE_PREFIX}${payload}`;
}
