export interface ParsedSlash {
  token: string;
  rest: string;
}

export function parseSlashInput(value: string): ParsedSlash | null {
  if (!value.startsWith("/")) return null;
  const after = value.slice(1);
  const spaceIdx = after.indexOf(" ");
  if (spaceIdx === -1) return { token: after, rest: "" };
  return { token: after.slice(0, spaceIdx), rest: after.slice(spaceIdx + 1) };
}

export function matchCommandName(
  token: string,
  candidate: { name: string; aliases?: string[] },
): boolean {
  const lower = token.toLowerCase();
  if (candidate.name.toLowerCase() === lower) return true;
  if (candidate.aliases?.some((a) => a.toLowerCase() === lower)) return true;
  return false;
}

export function fuzzyPrefix(
  token: string,
  candidate: { name: string; aliases?: string[] },
): boolean {
  const lower = token.toLowerCase();
  if (candidate.name.toLowerCase().startsWith(lower)) return true;
  if (candidate.aliases?.some((a) => a.toLowerCase().startsWith(lower))) {
    return true;
  }
  return false;
}
