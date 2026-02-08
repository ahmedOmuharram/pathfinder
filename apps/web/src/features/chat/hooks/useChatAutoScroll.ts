import { useEffect } from "react";

export function useChatAutoScroll(
  ref: React.RefObject<HTMLElement | null>,
  key: string,
) {
  useEffect(() => {
    ref.current?.scrollIntoView({ behavior: "smooth" });
  }, [ref, key]);
}
