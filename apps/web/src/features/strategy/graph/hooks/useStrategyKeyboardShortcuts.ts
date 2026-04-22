"use client";

import { useRef } from "react";
import { useReactFlow } from "@xyflow/react";
import { useRouter } from "next/navigation";
import { useEventListener } from "usehooks-ts";
import { useStrategyGraphCtx } from "@/features/strategy/graph/StrategyGraphContext";
import {
  useAddStepMutation,
  useDeleteStepMutation,
} from "@/features/strategy/mutations";

interface UseStrategyKeyboardShortcutsArgs {
  onOpenQuickSwitcher: () => void;
  onToggleShortcutsOverlay: () => void;
}

const LEADER_TIMEOUT_MS = 1000;

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (target.isContentEditable) return true;
  return false;
}

export function useStrategyKeyboardShortcuts({
  onOpenQuickSwitcher,
  onToggleShortcutsOverlay,
}: UseStrategyKeyboardShortcutsArgs): void {
  const ctx = useStrategyGraphCtx();
  const { fitView, zoomIn, zoomOut } = useReactFlow();
  const router = useRouter();
  const deleteStep = useDeleteStepMutation();
  // useAddStepMutation is held by reference for symmetry with the spec (the
  // `c` shortcut delegates to ctx.handleStartCombineFromSelection which is
  // wired through useStrategyGraphHandlers → useAddStepMutation under the
  // hood). Keep the hook call so future direct-add shortcuts can reuse it.
  useAddStepMutation();

  const leaderRef = useRef<{ key: "g"; expires: number } | null>(null);

  const handleKeyDown = (event: KeyboardEvent): void => {
    if (isTypingTarget(event.target)) return;

    const meta = event.metaKey || event.ctrlKey;
    const conversationId = ctx.strategy?.id ?? "";

    // Cmd/Ctrl+K — quick switcher
    if (meta && event.key.toLowerCase() === "k") {
      event.preventDefault();
      onOpenQuickSwitcher();
      return;
    }

    // Cmd/Ctrl+A — select all (delegate to browser-default by allowing it to bubble)
    // Cmd/Ctrl+Z handled by useStrategyGraphLayout (do not duplicate)
    if (meta) return;

    const leader = leaderRef.current;
    if (leader !== null && Date.now() <= leader.expires) {
      // Two-key sequence in flight (`g` is currently the only leader).
      if (event.key === "s") {
        event.preventDefault();
        leaderRef.current = null;
        router.push(`/conversation/${conversationId}/strategy`);
        return;
      }
      if (event.key === "c") {
        event.preventDefault();
        leaderRef.current = null;
        router.push(`/conversation/${conversationId}`);
        return;
      }
      // Any other key cancels the leader.
      leaderRef.current = null;
    }

    switch (event.key) {
      case "r": {
        event.preventDefault();
        ctx.handleRelayout();
        return;
      }
      case "f": {
        event.preventDefault();
        void fitView({ padding: 0.3, duration: 300 });
        return;
      }
      case "+":
      case "=": {
        event.preventDefault();
        void zoomIn({ duration: 150 });
        return;
      }
      case "-": {
        event.preventDefault();
        void zoomOut({ duration: 150 });
        return;
      }
      case "e": {
        event.preventDefault();
        const id = ctx.selectedNodeIds[0];
        if (id == null) return;
        const step = ctx.editableSteps.find((s) => s.id === id);
        if (step != null) ctx.setSelectedStep(step);
        return;
      }
      case "c": {
        event.preventDefault();
        if (ctx.selectedNodeIds.length >= 2) {
          ctx.handleStartCombineFromSelection();
        }
        return;
      }
      case "o": {
        event.preventDefault();
        if (ctx.selectedNodeIds.length === 1) {
          ctx.setOrthologModalOpen(true);
        }
        return;
      }
      case "@": {
        event.preventDefault();
        ctx.handleAddSelectionToChat();
        return;
      }
      case "Backspace":
      case "Delete": {
        if (ctx.selectedNodeIds.length === 0) return;
        event.preventDefault();
        for (const id of ctx.selectedNodeIds) {
          deleteStep.mutate({ stepId: id });
        }
        return;
      }
      case "?": {
        event.preventDefault();
        onToggleShortcutsOverlay();
        return;
      }
      case "Escape": {
        if (ctx.selectedStep != null) {
          event.preventDefault();
          ctx.setSelectedStep(null);
          return;
        }
        event.preventDefault();
        router.push(`/conversation/${conversationId}`);
        return;
      }
      case "g": {
        event.preventDefault();
        leaderRef.current = { key: "g", expires: Date.now() + LEADER_TIMEOUT_MS };
        return;
      }
      default:
        return;
    }
  };

  useEventListener("keydown", handleKeyDown);
}
