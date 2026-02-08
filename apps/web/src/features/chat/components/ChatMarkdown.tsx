"use client";

import type { AnchorHTMLAttributes, InputHTMLAttributes } from "react";
import type { Citation } from "@pathfinder/shared";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export type ChatMarkdownTone = "default" | "onDark";

interface ChatMarkdownProps {
  content: string;
  citations?: Citation[] | null;
  tone?: ChatMarkdownTone;
  className?: string;
}

function renderInlineCitationsMarkdown(
  content: string,
  citations?: Citation[] | null,
): string {
  if (!citations || citations.length === 0) return content;

  const tagToNumber = new Map<string, number>();
  for (let i = 0; i < citations.length; i++) {
    const tag = citations[i]?.tag;
    if (typeof tag === "string" && tag.trim()) {
      tagToNumber.set(tag.trim(), i + 1);
    }
  }
  if (tagToNumber.size === 0) return content;

  const normalizeTag = (t: string) => t.trim().replace(/^@+/, "");

  const renderTagList = (raw: string, originalToken: string) => {
    const tags = raw
      .split(/[,\s;]+/g)
      .map((t) => t.trim())
      .filter(Boolean);
    if (tags.length === 0) return originalToken;
    // Render known tags to numbers; keep unknown tags visible (so it's obvious why it didn't resolve).
    return tags
      .map((tag) => {
        const normalized = normalizeTag(tag);
        const n = tagToNumber.get(normalized);
        // If it doesn't resolve, preserve the user's original token (including leading @ if present).
        return n ? `[[${n}]](#cite-${n})` : `\\cite{${tag}}`;
      })
      .join(", ");
  };

  // Support both \\cite{tag} and [@tag] syntaxes.
  // Also support variants like \\citep{...}, \\citet{...}, etc.
  let out = content.replace(/\\cite[a-zA-Z]*\{([^}]+)\}/g, (_m, inner) =>
    renderTagList(String(inner ?? ""), _m),
  );
  out = out.replace(/\[@([^\]]+)\]/g, (_m, inner) =>
    renderTagList(String(inner ?? ""), _m),
  );
  return out;
}

function renderVerbatimBlocks(content: string): string {
  // Minimal "verbatim" support for models: wrap exact text blocks in
  // <verbatim>...</verbatim> and we render them as fenced code blocks.
  // This avoids markdown list parsing and preserves whitespace/newlines.
  return (content || "").replace(
    /<verbatim>\s*([\s\S]*?)\s*<\/verbatim>/g,
    (_m, inner) => `\n\n\`\`\`text\n${String(inner ?? "").replace(/\n{3,}/g, "\n\n")}\n\`\`\`\n\n`,
  );
}

const markdownComponents = {
  input: (props: InputHTMLAttributes<HTMLInputElement>) => (
    <input
      {...props}
      type="checkbox"
      checked={Boolean(props.checked)}
      readOnly
      disabled
      className="mr-2 align-middle"
    />
  ),
  a: (props: AnchorHTMLAttributes<HTMLAnchorElement>) => {
    const href = typeof props.href === "string" ? props.href : "";
    const isCitation = href.startsWith("#cite-");
    const a = (
      <a
        {...props}
        className={
          isCitation
            ? "no-underline hover:underline decoration-slate-400 underline-offset-2"
            : "underline decoration-slate-300 underline-offset-2 hover:decoration-slate-500"
        }
      />
    );
    return isCitation ? <sup className="ml-0.5">{a}</sup> : a;
  },
};

export function ChatMarkdown({
  content,
  citations,
  tone = "default",
  className,
}: ChatMarkdownProps) {
  const toneClassName =
    tone === "onDark"
      ? "text-white [&_h1]:text-white [&_h2]:text-white [&_a]:text-white [&_code]:text-white [&_code]:bg-slate-800/60"
      : "";

  return (
    <div className={`markdown-content whitespace-normal ${toneClassName} ${className || ""}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {renderInlineCitationsMarkdown(renderVerbatimBlocks(content), citations)}
      </ReactMarkdown>
    </div>
  );
}

