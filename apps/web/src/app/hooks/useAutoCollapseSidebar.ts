import { useState } from "react";
import { useEventListener } from "usehooks-ts";

import { useLeftSidebarStore } from "@/state/useRightRailStore";

const COLLAPSE_BELOW_PX = 900;

export function useAutoCollapseSidebar(): void {
  const setCollapsed = useLeftSidebarStore((s) => s.setCollapsed);
  const [checkedOnMount, setCheckedOnMount] = useState(false);

  if (!checkedOnMount && typeof window !== "undefined") {
    setCheckedOnMount(true);
    if (window.innerWidth < COLLAPSE_BELOW_PX) {
      setCollapsed(true);
    }
  }

  useEventListener("resize", () => {
    if (window.innerWidth < COLLAPSE_BELOW_PX) {
      setCollapsed(true);
    }
  });
}
