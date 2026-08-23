import type { PrivacySettings, PrivacyUpdate } from "@pathfinder/shared";

import { getAuthHeaders } from "@/lib/api/http";

const BASE = "/api/v1/me/privacy";

export async function getPrivacySettings(): Promise<PrivacySettings> {
  const res = await fetch(BASE, {
    credentials: "include",
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error(`getPrivacySettings: ${res.status}`);
  return (await res.json()) as PrivacySettings;
}

export async function updatePrivacySettings(
  body: PrivacyUpdate,
): Promise<PrivacySettings> {
  const res = await fetch(BASE, {
    method: "PATCH",
    credentials: "include",
    headers: getAuthHeaders({ contentType: "application/json" }),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`updatePrivacySettings: ${res.status}`);
  return (await res.json()) as PrivacySettings;
}
