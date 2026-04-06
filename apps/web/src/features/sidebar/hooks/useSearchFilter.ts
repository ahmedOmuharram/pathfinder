"use client";

/**
 * Search-query state and filtering for conversation items.
 */

import { useMemo, useState } from "react";
import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";

export interface SearchFilterResult {
  query: string;
  setQuery: (q: string) => void;
  filtered: ConversationItem[];
}

export function useSearchFilter(conversations: ConversationItem[]): SearchFilterResult {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter((c) => c.title.toLowerCase().includes(q));
  }, [conversations, query]);

  return { query, setQuery, filtered };
}
