import { useState, useRef, useCallback } from "react";
import type { ChatMention } from "@pathfinder/shared";

interface MentionState {
  mentions: ChatMention[];
  setMentions: React.Dispatch<React.SetStateAction<ChatMention[]>>;
  mentionActive: boolean;
  setMentionActive: React.Dispatch<React.SetStateAction<boolean>>;
  mentionQuery: string;
  mentionPos: { top: number; left: number };
  mentionStartRef: React.RefObject<number | null>;
  checkMentionTrigger: (value: string, cursorPos: number) => void;
  handleMentionSelect: (
    mention: ChatMention,
    message: string,
    textareaRef: React.RefObject<HTMLTextAreaElement | null>,
    setMessage: React.Dispatch<React.SetStateAction<string>>,
  ) => void;
  removeMention: (idx: number) => void;
}

export function useMentionState(): MentionState {
  const [mentions, setMentions] = useState<ChatMention[]>([]);
  const [mentionActive, setMentionActive] = useState(false);
  const [mentionQuery, setMentionQuery] = useState("");
  const [mentionPos, setMentionPos] = useState({ top: 0, left: 0 });
  const mentionStartRef = useRef<number | null>(null);

  const checkMentionTrigger = useCallback((value: string, cursorPos: number) => {
    const before = value.slice(0, cursorPos);
    const atIdx = before.lastIndexOf("@");
    if (
      atIdx === -1 ||
      (atIdx > 0 && before[atIdx - 1] !== " " && before[atIdx - 1] !== "\n")
    ) {
      setMentionActive(false);
      return;
    }
    const query = before.slice(atIdx + 1);
    if (query.includes(" ") && query.length > 20) {
      setMentionActive(false);
      return;
    }
    mentionStartRef.current = atIdx;
    setMentionQuery(query);
    setMentionPos({ top: 36, left: 8 });
    setMentionActive(true);
  }, []);

  const handleMentionSelect = useCallback(
    (
      mention: ChatMention,
      message: string,
      textareaRef: React.RefObject<HTMLTextAreaElement | null>,
      setMessage: React.Dispatch<React.SetStateAction<string>>,
    ) => {
      const start = mentionStartRef.current ?? 0;
      const before = message.slice(0, start);
      const textarea = textareaRef.current;
      const cursorPos = textarea?.selectionStart ?? message.length;
      const after = message.slice(cursorPos);
      setMessage(before + after);
      setMentions((prev) => {
        if (prev.some((m) => m.type === mention.type && m.id === mention.id))
          return prev;
        return [...prev, mention];
      });
      setMentionActive(false);
      setTimeout(() => textareaRef.current?.focus(), 0);
    },
    [],
  );

  const removeMention = useCallback((idx: number) => {
    setMentions((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  return {
    mentions,
    setMentions,
    mentionActive,
    setMentionActive,
    mentionQuery,
    mentionPos,
    mentionStartRef,
    checkMentionTrigger,
    handleMentionSelect,
    removeMention,
  };
}
