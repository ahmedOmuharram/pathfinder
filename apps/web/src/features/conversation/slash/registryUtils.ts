"use client";

import { getAuthHeaders } from "@/lib/api/http";

export function downloadTextFile(
  filename: string, text: string, mime: string,
) {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5_000);
}

export async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: getAuthHeaders({
      ...(init?.headers as Record<string, string> | undefined),
      contentType: "application/json",
    }),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(body || `${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export function renderChatMarkdown(
  messages: Array<Record<string, unknown>>,
): string {
  const lines: string[] = ["# Pathfinder Chat Export", ""];
  for (const msg of messages) {
    const roleRaw = msg["role"];
    const role = typeof roleRaw === "string" ? roleRaw : "unknown";
    lines.push(`## ${role}`);
    const partsRaw = msg["parts"];
    if (Array.isArray(partsRaw)) {
      for (const part of partsRaw as Array<{ type?: string; text?: string }>) {
        if (part.type === "text" && typeof part.text === "string") {
          lines.push(part.text);
        }
      }
    }
    lines.push("", "---", "");
  }
  return lines.join("\n");
}
