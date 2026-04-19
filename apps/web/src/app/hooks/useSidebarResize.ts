import { useRef, useState } from "react";
import { useEventListener } from "usehooks-ts";

interface UseSidebarResizeArgs {
  initialWidth?: number;
  minSidebar?: number;
  maxSidebar?: number;
  minMain?: number;
}

export function useSidebarResize({
  initialWidth = 360,
  minSidebar = 220,
  maxSidebar = 360,
  minMain = 520,
}: UseSidebarResizeArgs = {}) {
  const [sidebarWidth, setSidebarWidth] = useState(initialWidth);
  const [dragging, setDragging] = useState(false);
  const layoutRef = useRef<HTMLDivElement>(null);

  const handleMove = (event: MouseEvent) => {
    if (!dragging) return;
    const container = layoutRef.current;
    if (!container) return;
    const rect = container.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const maxAllowed = rect.width - minMain;
    const next = Math.min(
      Math.max(x, minSidebar),
      Math.max(minSidebar, Math.min(maxSidebar, maxAllowed)),
    );
    setSidebarWidth(next);
  };

  const handleUp = () => setDragging(false);

  useEventListener("mousemove", handleMove);
  useEventListener("mouseup", handleUp);

  return {
    layoutRef,
    sidebarWidth,
    isDragging: dragging,
    startDragging: () => setDragging(true),
  };
}
