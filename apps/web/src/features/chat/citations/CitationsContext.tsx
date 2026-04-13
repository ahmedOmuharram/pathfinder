"use client";

/**
 * Provides the per-message citation numbering to deeply nested part renderers.
 *
 * `TextPart` uses the context to produce a remark plugin that rewrites
 * `[@sourceId]` tokens into numbered superscripts; `SourcePart` uses it to
 * hide its inline rendering (the Sources footer on the bubble is the single
 * visible home for sources). Outside a provider both components fall back to
 * their pre-context behavior, so they still work on their own.
 */

import { createContext, useContext, type ReactNode } from "react";

import type { CitationIndex } from "./types";

const CitationsContext = createContext<CitationIndex | null>(null);

export function CitationsProvider({
  index,
  children,
}: {
  index: CitationIndex;
  children: ReactNode;
}) {
  return (
    <CitationsContext.Provider value={index}>
      {children}
    </CitationsContext.Provider>
  );
}

/** Returns the citation index if inside a CitationsProvider, else `null`. */
export function useCitations(): CitationIndex | null {
  return useContext(CitationsContext);
}
