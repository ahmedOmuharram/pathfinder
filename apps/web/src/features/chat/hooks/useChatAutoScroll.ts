import { useRef, useState } from "react";
import { useIntersectionObserver } from "usehooks-ts";

interface AutoScrollResult {
  bottomRef: (node: HTMLDivElement | null) => void;
  isAtBottom: boolean;
  scrollToBottom: () => void;
}

export function useChatAutoScroll(key: string): AutoScrollResult {
  const nodeRef = useRef<HTMLDivElement | null>(null);

  const { ref: observerRef, isIntersecting: isAtBottom } = useIntersectionObserver({
    threshold: 0.1,
  });

  const bottomRef = (node: HTMLDivElement | null) => {
    nodeRef.current = node;
    observerRef(node);
  };

  const [prevKey, setPrevKey] = useState(key);
  if (key !== prevKey) {
    setPrevKey(key);
    if (isAtBottom) {
      queueMicrotask(() => nodeRef.current?.scrollIntoView({ behavior: "smooth" }));
    }
  }

  const scrollToBottom = () => {
    nodeRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  return { bottomRef, isAtBottom, scrollToBottom };
}
