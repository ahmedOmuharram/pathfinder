import { useCallback, useEffect, useRef, useState } from "react";

interface AutoScrollResult {
  /** Ref to attach to the sentinel element at the bottom of the message list. */
  bottomRef: React.RefObject<HTMLDivElement | null>;
  /** Whether the user is currently scrolled near the bottom. */
  isAtBottom: boolean;
  /** Programmatically scroll to the bottom. */
  scrollToBottom: () => void;
}

/**
 * Smart auto-scroll for the chat message list.
 *
 * Uses an IntersectionObserver on a sentinel element placed at the end of the
 * messages to determine whether the user is "near the bottom". Auto-scrolling
 * only fires when the sentinel is in view (i.e. the user hasn't scrolled up).
 *
 * Returns `isAtBottom` and `scrollToBottom` so the component can render a
 * floating scroll-to-bottom button when the user has scrolled away during
 * streaming.
 */
export function useChatAutoScroll(
  key: string,
): AutoScrollResult {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);

  // Track intersection state via observer.
  useEffect(() => {
    const sentinel = bottomRef.current;
    if (!sentinel) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (entry) {
          setIsAtBottom(entry.isIntersecting);
        }
      },
      { threshold: 0.1 },
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, []);

  // Auto-scroll when content changes, but only if the user is near the bottom.
  useEffect(() => {
    if (!isAtBottom) return;
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [key, isAtBottom]);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  return { bottomRef, isAtBottom, scrollToBottom };
}
