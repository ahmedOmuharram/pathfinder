"use client";

import { cn } from "@/lib/utils/cn";
import type { ToolUIPart } from "ai";
import type { ComponentProps, ReactNode } from "react";
import { isValidElement } from "react";
import { CodeBlock } from "./code-block";

export type ToolInputProps = ComponentProps<"div"> & {
  input: ToolUIPart["input"];
};

export const ToolInput = ({ className, input, ...props }: ToolInputProps) => (
  <div className={cn("space-y-2 overflow-hidden p-4", className)} {...props}>
    <h4 className="font-medium text-muted-foreground text-xs uppercase tracking-wide">
      Parameters
    </h4>
    <div className="rounded-md bg-muted/50">
      <CodeBlock code={JSON.stringify(input, null, 2)} language="json" />
    </div>
  </div>
);

export type ToolOutputProps = ComponentProps<"div"> & {
  output: ToolUIPart["output"];
  errorText: ToolUIPart["errorText"];
};

function renderOutputBody(output: ToolUIPart["output"]): ReactNode {
  if (output == null) return null;
  if (typeof output === "object" && !isValidElement(output)) {
    return <CodeBlock code={JSON.stringify(output, null, 2)} language="json" />;
  }
  if (typeof output === "string") {
    const trimmed = output.trim();
    if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
      try {
        const parsed: unknown = JSON.parse(trimmed);
        return <CodeBlock code={JSON.stringify(parsed, null, 2)} language="json" />;
      } catch {
        // JSON-shaped but unparseable (e.g. clipped server-side): colorize anyway.
        return <CodeBlock code={trimmed} language="json" />;
      }
    }
    return (
      <pre className="whitespace-pre-wrap break-words px-3 py-2 font-sans text-foreground">
        {output}
      </pre>
    );
  }
  return <div className="px-3 py-2">{output as ReactNode}</div>;
}

export const ToolOutput = ({
  className,
  output,
  errorText,
  ...props
}: ToolOutputProps) => {
  if (!(output || errorText)) {
    return null;
  }

  return (
    <div className={cn("space-y-2 p-4", className)} {...props}>
      <h4 className="font-medium text-muted-foreground text-xs uppercase tracking-wide">
        {errorText ? "Error" : "Result"}
      </h4>
      <div
        className={cn(
          "overflow-x-auto rounded-md text-xs [&_table]:w-full",
          errorText
            ? "bg-destructive/10 text-destructive"
            : "bg-muted/50 text-foreground",
        )}
      >
        {errorText ? (
          <div className="whitespace-pre-wrap break-words px-3 py-2">{errorText}</div>
        ) : (
          renderOutputBody(output)
        )}
      </div>
    </div>
  );
};
