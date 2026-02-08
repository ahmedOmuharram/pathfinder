import type { ParamSpec } from "@/features/strategy/parameters/spec";

export type VocabOption = {
  label: string;
  value: string;
  rawLabel?: string;
  depth?: number;
  displayLabel?: string;
};

export type VocabNode = {
  value: string;
  label: string;
  children?: VocabNode[];
};

export function extractVocabOptions(vocabulary: unknown, limit = 200): VocabOption[] {
  const options: VocabOption[] = [];
  const seen = new Set<string>();
  const pushOption = (value: string, label?: string, depth = 0) => {
    const trimmedValue = value.trim();
    if (!trimmedValue || seen.has(trimmedValue)) {
      return;
    }
    const rawLabel =
      trimmedValue === "@@fake@@" ? "All" : (label || trimmedValue).trim();
    const displayLabel = depth > 0 ? `${"— ".repeat(depth)}${rawLabel}` : rawLabel;
    options.push({
      value: trimmedValue,
      label: rawLabel,
      rawLabel,
      depth,
      displayLabel,
    });
    seen.add(trimmedValue);
  };
  const walkTree = (node: Record<string, unknown>, depth = 0) => {
    if (options.length >= limit) return;
    const data = node.data as Record<string, unknown> | undefined;
    const rawValue =
      data?.value ??
      data?.id ??
      data?.term ??
      data?.name ??
      data?.display ??
      data?.displayName ??
      data?.label;
    const rawLabel =
      data?.display ??
      data?.displayName ??
      data?.label ??
      data?.name ??
      data?.value ??
      data?.term ??
      rawValue;
    const label = rawLabel ? String(rawLabel) : "";
    const valueCandidate = rawValue ? String(rawValue) : "";
    const value = valueCandidate || label;
    if (value) {
      pushOption(value, label || value, depth);
    }
    const children = node.children as Array<Record<string, unknown>> | undefined;
    if (children) {
      children.forEach((child) => walkTree(child, depth + 1));
    }
  };
  const walkArray = (entries: unknown[]) => {
    for (const entry of entries) {
      if (options.length >= limit) return;
      if (typeof entry === "string" || typeof entry === "number") {
        pushOption(String(entry));
        continue;
      }
      if (Array.isArray(entry)) {
        const [value, label] = entry;
        if (value !== undefined) {
          pushOption(String(value), label ? String(label) : undefined);
        }
        continue;
      }
      if (entry && typeof entry === "object") {
        const record = entry as Record<string, unknown>;
        const value =
          record.value ?? record.id ?? record.term ?? record.name ?? record.displayName;
        const label =
          record.display ?? record.displayName ?? record.label ?? record.name ?? value;
        if (value !== undefined) {
          pushOption(String(value), label ? String(label) : undefined);
        }
      }
    }
  };
  if (Array.isArray(vocabulary)) {
    walkArray(vocabulary);
    return options;
  }
  if (vocabulary && typeof vocabulary === "object") {
    const record = vocabulary as Record<string, unknown>;
    const values =
      record.values ||
      record.items ||
      record.terms ||
      record.options ||
      record.allowedValues;
    if (Array.isArray(values)) {
      walkArray(values);
    } else if (values && typeof values === "object") {
      Object.entries(values as Record<string, unknown>).forEach(([key, val]) => {
        if (typeof val === "string" || typeof val === "number") {
          pushOption(key, String(val));
        } else {
          pushOption(key, undefined);
        }
      });
    } else {
      walkTree(record);
    }
  }
  return options;
}

export function extractVocabTree(vocabulary: unknown): VocabNode[] | null {
  const extractNode = (entry: Record<string, unknown>): VocabNode | null => {
    const data = (entry.data as Record<string, unknown> | undefined) ?? entry;
    const rawValue =
      data?.value ??
      data?.id ??
      data?.term ??
      data?.name ??
      data?.display ??
      data?.displayName ??
      data?.label;
    if (!rawValue) return null;
    const rawLabel =
      data?.display ??
      data?.displayName ??
      data?.label ??
      data?.name ??
      data?.value ??
      data?.term ??
      rawValue;
    const children = Array.isArray(entry.children)
      ? entry.children
          .map((child) => extractNode(child as Record<string, unknown>))
          .filter((child): child is VocabNode => Boolean(child))
      : [];
    const value = String(rawValue);
    const label = value === "@@fake@@" ? "All" : String(rawLabel ?? value);
    return {
      value,
      label,
      children: children.length > 0 ? children : undefined,
    };
  };

  if (!vocabulary || typeof vocabulary !== "object") return null;
  if (Array.isArray(vocabulary)) {
    const nodes = vocabulary
      .map((entry) =>
        entry && typeof entry === "object"
          ? extractNode(entry as Record<string, unknown>)
          : null,
      )
      .filter((node): node is VocabNode => Boolean(node));
    const hasChildren = nodes.some((node) => node.children?.length);
    return hasChildren ? nodes : null;
  }

  const record = vocabulary as Record<string, unknown>;
  const values = record.values || record.items || record.terms || record.options;
  if (Array.isArray(values)) {
    const nodes = values
      .map((entry) =>
        entry && typeof entry === "object"
          ? extractNode(entry as Record<string, unknown>)
          : null,
      )
      .filter((node): node is VocabNode => Boolean(node));
    const hasChildren = nodes.some((node) => node.children?.length);
    return hasChildren ? nodes : null;
  }

  if (record.children && Array.isArray(record.children)) {
    const root = extractNode(record);
    return root ? [root] : null;
  }

  return null;
}

export function collectNodeValues(node: VocabNode): string[] {
  const values = [node.value];
  if (node.children) {
    node.children.forEach((child) => values.push(...collectNodeValues(child)));
  }
  return values;
}

export function extractSpecVocabulary(spec: ParamSpec): unknown {
  return (
    spec.vocabulary ??
    spec.values ??
    spec.items ??
    spec.terms ??
    spec.options ??
    spec.allowedValues
  );
}

export function buildContextValues(
  values: Record<string, unknown>,
  allowedKeys?: string[],
): Record<string, unknown> {
  const filtered: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(values)) {
    if (allowedKeys && !allowedKeys.includes(key)) continue;
    if (value === "@@fake@@") continue;
    if (Array.isArray(value) && value.includes("@@fake@@")) continue;
    if (value === null || value === undefined || value === "") continue;
    if (Array.isArray(value) && value.length === 0) continue;
    filtered[key] = value;
  }
  return filtered;
}
