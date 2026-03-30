/**
 * Pure async function for undoing a chat turn.
 *
 * Extracted from useChatPanelState for testability — all dependencies
 * are explicit parameters, no closure captures.
 */

import type { Dispatch, SetStateAction } from "react";
import type { Message, Strategy, UserMessage } from "@pathfinder/shared";
import { getStrategy, undoTurn } from "@/lib/api/strategies";

export interface UndoTurnDeps {
  setMessages: Dispatch<SetStateAction<Message[]>>;
  setUndoSnapshots: Dispatch<SetStateAction<Record<number, Strategy>>>;
  setStrategy: (s: Strategy | null) => void;
  setStrategyMeta: (u: Partial<Strategy>) => void;
  setComposerPrefill: (v: { message: string }) => void;
}

/**
 * Undo a user turn: remove messages from the index onward, restore strategy
 * state, and prefill the composer with the undone message text.
 *
 * Returns true if the undo succeeded, false otherwise.
 */
export async function undoTurnAction(
  strategyId: string,
  userMessage: UserMessage,
  userMessageIndex: number,
  deps: UndoTurnDeps,
): Promise<boolean> {
  if (userMessage.entryId == null || userMessage.entryId === "") return false;

  const result = await undoTurn(strategyId, userMessage.entryId);

  deps.setMessages((prev) => prev.slice(0, userMessageIndex));

  deps.setUndoSnapshots((prev) => {
    const kept: Record<number, Strategy> = {};
    for (const [k, v] of Object.entries(prev)) {
      if (Number(k) < userMessageIndex) kept[Number(k)] = v;
    }
    return kept;
  });

  if (result.strategy != null) {
    const full = await getStrategy(strategyId);
    deps.setStrategy(full);
    deps.setStrategyMeta({
      name: full.name,
      ...(full.description != null ? { description: full.description } : {}),
      ...(full.recordType != null ? { recordType: full.recordType } : {}),
    });
  } else {
    deps.setStrategy(null);
    deps.setStrategyMeta({});
  }

  deps.setComposerPrefill({ message: userMessage.content });
  return true;
}
