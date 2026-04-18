"use client";

import {
  ComposerPrimitive,
  useComposer,
  useComposerRuntime,
} from "@assistant-ui/react";
import { Send } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { ParamStepper } from "@/features/conversation/slash/ParamStepper";
import { SlashPopover } from "@/features/conversation/slash/SlashPopover";
import { commands, findCommand } from "@/features/conversation/slash/registry";
import type { Command, CommandResult } from "@/features/conversation/slash/types";
import { parseSlashInput } from "@/features/conversation/slash/parser";
import { useSessionStore } from "@/state/useSessionStore";

export function Composer() {
  const runtime = useComposerRuntime();
  const text = useComposer((s) => s.text);
  const siteId = useSessionStore((s) => s.selectedSite);

  const [pendingCommand, setPendingCommand] = useState<Command | null>(null);

  const parsed = parseSlashInput(text);
  const showPopover =
    pendingCommand === null && parsed !== null && parsed.rest === "";

  function chatIdFromLocation(): string | null {
    if (typeof window === "undefined") return null;
    const match = window.location.pathname.match(/\/conversation\/([^/]+)/);
    return match?.[1] ?? null;
  }

  async function runCommand(command: Command, values: Record<string, string>) {
    const chatId = chatIdFromLocation();
    if (chatId === null) {
      toast.error("Slash commands require an active chat.");
      return;
    }
    const ctx = { chatId, siteId };

    if (command.kind === "llm-prefill") {
      runtime.setText(command.prompt(values, ctx));
      if (command.autoSubmit === true) {
        runtime.send();
      }
      setPendingCommand(null);
      return;
    }

    try {
      const result: CommandResult = await command.run(values, ctx);
      runtime.setText("");
      setPendingCommand(null);
      handleResult(result);
    } catch (err) {
      runtime.setText("");
      setPendingCommand(null);
      const msg = err instanceof Error ? err.message : "Command failed";
      toast.error(msg);
    }
  }

  function handleResult(result: CommandResult) {
    if (result.kind === "toast") {
      if (result.type === "success") toast.success(result.message);
      else if (result.type === "error") toast.error(result.message);
      else toast.info(result.message);
      return;
    }
    if (result.kind === "download") {
      const a = document.createElement("a");
      a.href = result.url;
      a.download = result.filename;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      document.body.appendChild(a);
      a.click();
      a.remove();
      toast.success(`Downloading ${result.filename}`);
      return;
    }
    if (result.kind === "prefill") {
      runtime.setText(result.text);
      if (result.submit === true) runtime.send();
    }
  }

  function selectCommand(command: Command) {
    if (command.params.length === 0) {
      void runCommand(command, {});
      return;
    }
    setPendingCommand(command);
  }

  function dismissPopover() {
    runtime.setText("");
  }

  const exactMatch =
    parsed !== null && parsed.token !== "" ? findCommand(parsed.token) : null;
  const wantsDirectRun =
    exactMatch !== null
      && exactMatch !== undefined
      && parsed !== null
      && parsed.rest === "";

  return (
    <ComposerPrimitive.Root className="relative flex flex-col gap-2 border-t bg-card px-4 py-3">
      <SlashPopover
        open={showPopover}
        query={parsed?.token ?? ""}
        commands={commands}
        onSelect={selectCommand}
        onDismiss={dismissPopover}
      />
      <ParamStepper
        open={pendingCommand !== null}
        command={pendingCommand}
        ctx={{
          chatId: chatIdFromLocation() ?? "",
          siteId,
        }}
        onComplete={(values) => {
          if (pendingCommand !== null) void runCommand(pendingCommand, values);
        }}
        onCancel={() => {
          setPendingCommand(null);
          runtime.setText("");
        }}
      />
      <div className="focus-within:shadow-[var(--shadow-composer-focus)] flex flex-col gap-2 rounded-lg border bg-background shadow-[var(--shadow-composer)] transition-shadow">
        <ComposerPrimitive.Input
          placeholder="Ask about strategies, genes, or data… (try /help)"
          className="w-full resize-none bg-transparent p-3 text-sm outline-none"
          autoFocus
          onKeyDown={(e) => {
            if (
              e.key === "Enter"
              && !e.shiftKey
              && wantsDirectRun
              && exactMatch !== null
              && exactMatch !== undefined
            ) {
              e.preventDefault();
              selectCommand(exactMatch);
            }
          }}
        />
        <div className="flex justify-end p-2">
          <ComposerPrimitive.Send
            aria-label="Send"
            className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground shadow-[var(--shadow-card)] transition-transform hover:-translate-y-px disabled:opacity-50 disabled:hover:translate-y-0"
          >
            <Send className="h-4 w-4" /> Send
          </ComposerPrimitive.Send>
        </div>
      </div>
    </ComposerPrimitive.Root>
  );
}
