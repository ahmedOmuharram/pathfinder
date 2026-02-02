"use client";

import type { InputHTMLAttributes } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export type ChatMarkdownTone = "default" | "onDark";

interface ChatMarkdownProps {
  content: string;
  tone?: ChatMarkdownTone;
  className?: string;
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
};

export function ChatMarkdown({
  content,
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
        {content}
      </ReactMarkdown>
    </div>
  );
}

