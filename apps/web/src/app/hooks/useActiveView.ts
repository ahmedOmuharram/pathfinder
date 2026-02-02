import { useCallback, useState } from "react";

export type ActiveView = "chat" | "graph";

export function useActiveView(initial: ActiveView = "chat") {
  const [activeView, setActiveView] = useState<ActiveView>(initial);

  const toggleView = useCallback(() => {
    setActiveView((prev) => (prev === "chat" ? "graph" : "chat"));
  }, []);

  return { activeView, setActiveView, toggleView };
}
