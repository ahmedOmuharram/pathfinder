"use client";

import { useRouter } from "next/navigation";

import { useStrategyAutoFlush } from "./useStrategyAutoFlush";

interface FlushAwareNav {
  /**
   * Awaits any in-flight strategy push mutation, then navigates to `href`
   * via Next.js App Router. Use this whenever a click leaves the current
   * conversation (sidebar item, back button, etc.) so optimistic edits are
   * never dropped.
   */
  navigate: (href: string) => Promise<void>;
  /** True when at least one push mutation is currently in flight. */
  pending: boolean;
}

export function useFlushBeforeNav(): FlushAwareNav {
  const router = useRouter();
  const { awaitFlush, pending } = useStrategyAutoFlush();

  const navigate = async (href: string): Promise<void> => {
    await awaitFlush();
    router.push(href);
  };

  return { navigate, pending };
}
