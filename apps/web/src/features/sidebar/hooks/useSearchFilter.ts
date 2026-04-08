"use client";

/**
 * Search-query state and filtering for conversation items.
 */

import { useState } from "react";
import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";

export interface SearchFilterResult {
  query: string;
  setQuery: (q: string) => void;
  filtered: ConversationItem[];
}

export function useSearchFilter(conversations: ConversationItem[]): SearchFilterResult {
  const [query, setQuery] = useState("");

  const q = query.trim().toLowerCase();
  const filtered = q
    ? conversations.filter((c) => c.title.toLowerCase().includes(q))
    : conversations;

  return { query, setQuery, filtered };
}
