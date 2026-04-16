import type {
  MemoryEditRequest,
  MemoryItem,
  MemoryKind,
  MemoryListResponse,
  MemorySearchResponse,
} from "@pathfinder/shared";

import { getAuthHeaders } from "@/lib/api/http";

const BASE = "/api/v1/memories";

export async function listMemories(opts?: {
  limit?: number;
  offset?: number;
}): Promise<MemoryListResponse> {
  const params = new URLSearchParams();
  if (opts?.limit != null) params.set("limit", String(opts.limit));
  if (opts?.offset != null) params.set("offset", String(opts.offset));
  const url = params.size > 0 ? `${BASE}?${params.toString()}` : BASE;
  const res = await fetch(url, {
    credentials: "include",
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error(`listMemories: ${res.status}`);
  return (await res.json()) as MemoryListResponse;
}

export async function searchMemories(
  query: string,
): Promise<MemorySearchResponse> {
  const res = await fetch(
    `${BASE}/search?q=${encodeURIComponent(query)}`,
    { credentials: "include", headers: getAuthHeaders() },
  );
  if (!res.ok) throw new Error(`searchMemories: ${res.status}`);
  return (await res.json()) as MemorySearchResponse;
}

export async function editMemory(
  key: string,
  kind: MemoryKind,
  body: MemoryEditRequest,
): Promise<MemoryItem> {
  const res = await fetch(
    `${BASE}/${encodeURIComponent(key)}?kind=${encodeURIComponent(kind)}`,
    {
      method: "PATCH",
      credentials: "include",
      headers: getAuthHeaders({ contentType: "application/json" }),
      body: JSON.stringify(body),
    },
  );
  if (!res.ok) throw new Error(`editMemory: ${res.status}`);
  return (await res.json()) as MemoryItem;
}

export async function deleteMemory(
  key: string,
  kind: MemoryKind,
): Promise<void> {
  const res = await fetch(
    `${BASE}/${encodeURIComponent(key)}?kind=${encodeURIComponent(kind)}`,
    {
      method: "DELETE",
      credentials: "include",
      headers: getAuthHeaders(),
    },
  );
  if (!res.ok && res.status !== 204) {
    throw new Error(`deleteMemory: ${res.status}`);
  }
}
