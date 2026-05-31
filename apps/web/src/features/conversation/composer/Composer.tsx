"use client";

import { ComposerPrimitive, useAui, useAuiState } from "@assistant-ui/react";
import { useQuery } from "@tanstack/react-query";
import { Send, Square } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { ParamStepper } from "@/features/conversation/slash/ParamStepper";
import { SlashPopover } from "@/features/conversation/slash/SlashPopover";
import { commands, findCommand } from "@/features/conversation/slash/registry";
import type { Command, CommandResult } from "@/features/conversation/slash/types";
import { parseSlashInput } from "@/features/conversation/slash/parser";
import { beginStrategy } from "@pathfinder/shared/generated/hooks/useBeginStrategy";
import { getAuthHeaders } from "@/lib/api/http";
import { strategyQueryOptions } from "@/lib/api/strategy";
import { useSessionStore } from "@/state/useSessionStore";

import { QuotaExhaustedBanner, useQuotaExhausted } from "./QuotaExhaustedBanner";

const tokensCompact = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 1,
});

const costFmt = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const costSubCentFmt = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
});

function formatCost(cost: number): string {
  if (cost <= 0) return costFmt.format(0);
  if (cost < 0.01) return costSubCentFmt.format(cost);
  return costFmt.format(cost);
}

function ConversationUsageFooter({ conversationId }: { conversationId: string }) {
  const { data } = useQuery(strategyQueryOptions(conversationId));
  const tokens = data?.totalTokens ?? 0;
  const cost = Number(data?.totalCostUsd ?? 0);
  if (tokens === 0 && cost === 0) return null;
  return (
    <div className="flex items-center gap-2 px-1 pt-1">
      <span className="text-[11px] text-muted-foreground">
        {tokensCompact.format(tokens)} tokens · {formatCost(cost)}
      </span>
    </div>
  );
}

export function Composer({ conversationId }: { conversationId: string }) {
  const aui = useAui();
  const text = useAuiState((s) => s.composer.text);
  const siteId = useSessionStore((s) => s.selectedSite);
  const quotaExhausted = useQuotaExhausted();
  const isRunning = useAuiState((s) => s.thread.isRunning);
  const requestServerCancel = (): void => {
    void fetch(`/api/v1/conversations/${conversationId}/cancel`, {
      method: "POST",
      headers: getAuthHeaders(),
    }).catch(() => {});
  };
  const { data: conversationDetail } = useQuery(strategyQueryOptions(conversationId));
  const stepCount = conversationDetail?.steps.length ?? 0;

  const [pendingCommand, setPendingCommand] = useState<Command | null>(null);

  const parsed = parseSlashInput(text);
  const showPopover = pendingCommand === null && parsed !== null && parsed.rest === "";

  async function runCommand(command: Command, values: Record<string, string>) {
    const ctx = { conversationId, siteId, stepCount };

    try {
      await beginStrategy(conversationId, { siteId });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to start conversation";
      toast.error(msg);
      return;
    }

    if (command.kind === "llm-prefill") {
      aui.composer().setText(command.prompt(values, ctx));
      if (command.autoSubmit === true) {
        aui.composer().send();
      }
      setPendingCommand(null);
      return;
    }

    try {
      const result: CommandResult = await command.run(values, ctx);
      aui.composer().setText("");
      setPendingCommand(null);
      handleResult(result);
    } catch (err) {
      aui.composer().setText("");
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
      aui.composer().setText(result.text);
      if (result.submit === true) aui.composer().send();
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
    aui.composer().setText("");
  }

  const exactMatch =
    parsed !== null && parsed.token !== "" ? findCommand(parsed.token) : null;
  const wantsDirectRun =
    exactMatch !== null &&
    exactMatch !== undefined &&
    parsed !== null &&
    parsed.rest === "";

  return (
    <ComposerPrimitive.Root
      data-testid="message-composer"
      className="relative mx-auto flex w-full max-w-3xl flex-col gap-1 border-t bg-card px-4 pb-2 pt-3"
    >
      <SlashPopover
        open={showPopover}
        query={parsed?.token ?? ""}
        commands={commands}
        ctx={{ conversationId, siteId, stepCount }}
        onSelect={selectCommand}
        onDismiss={dismissPopover}
      />
      <ParamStepper
        open={pendingCommand !== null}
        command={pendingCommand}
        ctx={{ conversationId, siteId, stepCount }}
        onComplete={(values) => {
          if (pendingCommand !== null) void runCommand(pendingCommand, values);
        }}
        onCancel={() => {
          setPendingCommand(null);
          aui.composer().setText("");
        }}
      />
      <QuotaExhaustedBanner />
      <div
        className="focus-within:shadow-[var(--shadow-composer-focus)] flex flex-col gap-2 rounded-lg border bg-background shadow-[var(--shadow-composer)] transition-shadow aria-disabled:opacity-60"
        aria-disabled={quotaExhausted}
      >
        <ComposerPrimitive.Input
          data-testid="message-input"
          placeholder={
            quotaExhausted
              ? "Monthly quota reached — try again after the reset date."
              : "Ask about strategies, genes, or data... (try /help)"
          }
          className="w-full resize-none bg-transparent p-3 text-sm outline-none disabled:cursor-not-allowed"
          autoFocus
          disabled={quotaExhausted}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && wantsDirectRun) {
              e.preventDefault();
              selectCommand(exactMatch);
            }
          }}
        />
        <div className="flex justify-end p-2">
          {isRunning ? (
            <ComposerPrimitive.Cancel
              data-testid="stop-button"
              aria-label="Stop"
              onClick={requestServerCancel}
              className="inline-flex items-center gap-2 rounded-md bg-destructive px-3 py-2 text-sm text-destructive-foreground shadow-[var(--shadow-card)] transition-transform hover:-translate-y-px"
            >
              <Square className="h-4 w-4" /> Stop
            </ComposerPrimitive.Cancel>
          ) : (
            <ComposerPrimitive.Send
              data-testid="send-button"
              aria-label="Send"
              disabled={quotaExhausted}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground shadow-[var(--shadow-card)] transition-transform hover:-translate-y-px disabled:opacity-50 disabled:hover:translate-y-0"
            >
              <Send className="h-4 w-4" /> Send
            </ComposerPrimitive.Send>
          )}
        </div>
      </div>
      <ConversationUsageFooter conversationId={conversationId} />
    </ComposerPrimitive.Root>
  );
}
