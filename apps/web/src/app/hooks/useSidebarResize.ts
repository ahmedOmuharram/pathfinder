import { useEffect, useRef, useState } from "react";

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

  useEffect(() => {
    if (!dragging) return;
    const handleMove = (event: MouseEvent) => {
      const container = layoutRef.current;
      if (!container) return;
      const rect = container.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const maxAllowed = rect.width - minMain;
      const next = Math.min(
        Math.max(x, minSidebar),
        Math.max(minSidebar, Math.min(maxSidebar, maxAllowed))
      );
      setSidebarWidth(next);
    };

    const handleUp = () => setDragging(false);
    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, [dragging, minSidebar, maxSidebar, minMain]);

  return {
    layoutRef,
    sidebarWidth,
    startDragging: () => setDragging(true),
  };
}
