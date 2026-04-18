"use client";

import {
  Ban,
  BookOpen,
  Download,
  FileText,
  HelpCircle,
  LineChart,
  Plus,
  Sparkles,
  Trash,
  Upload,
  Zap,
} from "lucide-react";

import { listGeneSets } from "@/features/workbench/api/geneSets";
import { getAuthHeaders } from "@/lib/api/http";

import type { Command } from "./types";

function downloadTextFile(filename: string, text: string, mime: string) {
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

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
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

function renderChatMarkdown(
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

export const commands: Command[] = [
  {
    kind: "deterministic",
    name: "new",
    description: "Clear composer (start fresh message)",
    icon: <Plus className="size-3.5" aria-hidden />,
    params: [],
    run: () => ({
      kind: "prefill",
      text: "",
      submit: false,
    }),
  },
  {
    kind: "deterministic",
    name: "rename",
    description: "Rename this chat",
    icon: <FileText className="size-3.5" aria-hidden />,
    params: [
      {
        kind: "text",
        name: "name",
        label: "New name",
        placeholder: "Descriptive chat title",
      },
    ],
    run: async (values, ctx) => {
      const name = values["name"]?.trim() ?? "";
      if (name.length === 0) {
        return {
          kind: "toast",
          type: "error",
          message: "Name cannot be empty.",
        };
      }
      await fetchJson(`/api/v1/conversations/${ctx.chatId}`, {
        method: "PATCH",
        body: JSON.stringify({ name }),
      });
      return {
        kind: "toast",
        type: "success",
        message: `Renamed to "${name}".`,
      };
    },
  },
  {
    kind: "deterministic",
    name: "export",
    aliases: ["save", "download"],
    description: "Export strategy, chat, or gene set",
    icon: <Download className="size-3.5" aria-hidden />,
    params: [
      {
        kind: "select",
        name: "what",
        label: "What to export",
        options: [
          {
            value: "strategy",
            label: "Current strategy",
            description: "JSON dump of the active strategy",
          },
          {
            value: "chat",
            label: "This conversation",
            description: "All messages (JSON or Markdown)",
          },
          {
            value: "gene-set",
            label: "A gene set",
            description: "Your most-recent saved gene set (CSV/TXT)",
          },
        ],
      },
      {
        kind: "select",
        name: "format",
        label: "Format",
        options: [
          { value: "json", label: "JSON (strategy / chat)" },
          { value: "md", label: "Markdown (chat)" },
          { value: "csv", label: "CSV (gene set)" },
          { value: "txt", label: "TXT (gene set)" },
        ],
      },
    ],
    run: async (values, ctx) => {
      const what = values["what"];
      const format = values["format"];
      if (what === "strategy") {
        if (format !== "json") {
          return {
            kind: "toast",
            type: "error",
            message: "Strategy export supports JSON only.",
          };
        }
        const chat = await fetchJson<{ wdkStrategyId: number | null }>(
          `/api/v1/conversations/${ctx.chatId}`,
        );
        const strategies = await fetchJson<
          Array<{ id: string; wdkStrategyId: number | null }>
        >(`/api/v1/conversations?siteId=${encodeURIComponent(ctx.siteId)}`);
        const target = strategies.find(
          (s) => s.wdkStrategyId === chat.wdkStrategyId,
        );
        if (target === undefined) {
          return {
            kind: "toast",
            type: "error",
            message: "No strategy linked to this chat.",
          };
        }
        const payload = await fetchJson<Record<string, unknown>>(
          `/api/v1/conversations/${target.id}`,
        );
        downloadTextFile(
          `strategy-${target.id}.json`,
          JSON.stringify(payload, null, 2),
          "application/json",
        );
        return {
          kind: "toast",
          type: "success",
          message: "Strategy downloaded.",
        };
      }
      if (what === "chat") {
        const messages = await fetchJson<Array<Record<string, unknown>>>(
          `/api/v1/conversations/${ctx.chatId}/messages`,
        );
        if (format === "md") {
          const md = renderChatMarkdown(messages);
          downloadTextFile(`chat-${ctx.chatId}.md`, md, "text/markdown");
        } else {
          downloadTextFile(
            `chat-${ctx.chatId}.json`,
            JSON.stringify(messages, null, 2),
            "application/json",
          );
        }
        return {
          kind: "toast",
          type: "success",
          message: "Chat exported.",
        };
      }
      if (what === "gene-set") {
        const fmt = format === "txt" ? "txt" : "csv";
        const sets = await listGeneSets(ctx.siteId);
        if (sets.length === 0) {
          return {
            kind: "toast",
            type: "error",
            message: "No gene sets to export.",
          };
        }
        const target = sets[0];
        if (target === undefined) {
          return {
            kind: "toast",
            type: "error",
            message: "Gene set not found.",
          };
        }
        const resp = await fetchJson<{ url: string; filename: string }>(
          `/api/v1/gene-sets/${target.id}/export?format=${fmt}`,
          { method: "POST" },
        );
        return {
          kind: "download",
          url: resp.url,
          filename: resp.filename,
        };
      }
      return {
        kind: "toast",
        type: "error",
        message: `Unknown target: ${what}`,
      };
    },
  },
  {
    kind: "deterministic",
    name: "import",
    description: "Import a gene set from pasted IDs",
    icon: <Upload className="size-3.5" aria-hidden />,
    params: [
      {
        kind: "text",
        name: "name",
        label: "Gene set name",
        placeholder: "e.g. my uploaded list",
      },
      {
        kind: "textarea",
        name: "rawText",
        label: "Gene IDs",
        placeholder:
          "Paste gene IDs — newline, comma, tab, or space separated",
        rows: 6,
      },
    ],
    run: async (values, ctx) => {
      const name = values["name"]?.trim() ?? "";
      const rawText = values["rawText"] ?? "";
      if (name.length === 0) {
        return {
          kind: "toast",
          type: "error",
          message: "Name required.",
        };
      }
      if (rawText.trim().length === 0) {
        return {
          kind: "toast",
          type: "error",
          message: "Paste at least one gene ID.",
        };
      }
      const resp = await fetchJson<{ geneCount: number; id: string }>(
        "/api/v1/gene-sets/import",
        {
          method: "POST",
          body: JSON.stringify({ name, siteId: ctx.siteId, rawText }),
        },
      );
      return {
        kind: "toast",
        type: "success",
        message: `Imported "${name}" with ${resp.geneCount} gene IDs.`,
      };
    },
  },
  {
    kind: "deterministic",
    name: "help",
    aliases: ["?"],
    description: "List available slash commands",
    icon: <HelpCircle className="size-3.5" aria-hidden />,
    params: [],
    run: () => {
      const lines = commands.map(
        (c) => `- /${c.name} — ${c.description}`,
      );
      return {
        kind: "toast",
        type: "info",
        message: `Slash commands:\n${lines.join("\n")}`,
      };
    },
  },
  {
    kind: "llm-prefill",
    name: "clear",
    description: "Clear the current strategy",
    icon: <Trash className="size-3.5 text-destructive" aria-hidden />,
    params: [],
    prompt: () =>
      "Clear the current strategy by calling clear_strategy with confirm=true.",
    autoSubmit: true,
  },
  {
    kind: "llm-prefill",
    name: "analyze",
    description: "Analyze the current strategy and suggest next steps",
    icon: <LineChart className="size-3.5" aria-hidden />,
    params: [],
    prompt: () =>
      "Analyze my current strategy. Summarize topology and step flow, any "
      + "weak spots or redundant steps, concrete improvement suggestions, "
      + "and what I should try next.",
    autoSubmit: false,
  },
  {
    kind: "llm-prefill",
    name: "optimize",
    description: "Optimize parameters on a step",
    icon: <Zap className="size-3.5" aria-hidden />,
    params: [
      {
        kind: "text",
        name: "stepHint",
        label: "Which step? (optional)",
        placeholder: "e.g. 'last step', 'the text search step', or a step id",
      },
    ],
    prompt: (values) => {
      const hint = (values["stepHint"] ?? "").trim();
      if (hint === "") {
        return (
          "Run optimize_search_parameters on the step in my current "
          + "strategy that's most likely to benefit. Pick reasonable "
          + "objective and controls, and ask for my approval before "
          + "kicking it off."
        );
      }
      return (
        `Run optimize_search_parameters on ${hint}. Pick reasonable `
        + "objective and controls, and ask for my approval before kicking "
        + "it off."
      );
    },
    autoSubmit: false,
  },
  {
    kind: "llm-prefill",
    name: "summarize",
    description: "Summarize this conversation",
    icon: <BookOpen className="size-3.5" aria-hidden />,
    params: [],
    prompt: () =>
      "Summarize this conversation so far: the research question, the "
      + "strategy I've built, key decisions made, and anything still open.",
    autoSubmit: false,
  },
  {
    kind: "llm-prefill",
    name: "diagnose",
    description: "Diagnose why my strategy returns 0 results",
    icon: <Ban className="size-3.5" aria-hidden />,
    params: [],
    prompt: () =>
      "Diagnose my current strategy. Walk through each step, call "
      + "get_estimated_size on each, and identify where results collapse. "
      + "Suggest the likely cause and concrete fixes.",
    autoSubmit: false,
  },
  {
    kind: "llm-prefill",
    name: "explain",
    description: "Explain a specific step",
    icon: <Sparkles className="size-3.5" aria-hidden />,
    params: [
      {
        kind: "text",
        name: "stepHint",
        label: "Which step?",
        placeholder: "step id, name, or position",
      },
    ],
    prompt: (values) => {
      const hint = (values["stepHint"] ?? "").trim();
      if (hint === "") {
        return "Explain what my last step does and why it matters biologically.";
      }
      return `Explain what ${hint} does and why it matters biologically.`;
    },
    autoSubmit: false,
  },
];

export function findCommand(name: string): Command | undefined {
  const lower = name.toLowerCase();
  return commands.find((c) => {
    if (c.name.toLowerCase() === lower) return true;
    return c.aliases?.some((a) => a.toLowerCase() === lower) ?? false;
  });
}
