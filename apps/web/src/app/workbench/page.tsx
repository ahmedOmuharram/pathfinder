"use client";

import { useEffect } from "react";
import { useWorkbenchStore } from "@/features/workbench/store";
import { WorkbenchMain } from "@/features/workbench/components/WorkbenchMain";

export default function WorkbenchPage() {
  const setActiveSet = useWorkbenchStore((s) => s.setActiveSet);

  // Landing page — clear any previously active gene set so the empty state shows.
  useEffect(() => {
    setActiveSet(null);
  }, [setActiveSet]);

  return <WorkbenchMain />;
}
