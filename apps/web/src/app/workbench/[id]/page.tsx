"use client";

import { useEffect } from "react";
import { useParams } from "next/navigation";
import { useWorkbenchStore } from "@/state/useWorkbenchStore";
import { WorkbenchMain } from "@/features/workbench/components/WorkbenchMain";

export default function WorkbenchGeneSetPage() {
  const { id } = useParams<{ id: string }>();
  const setActiveSet = useWorkbenchStore((s) => s.setActiveSet);
  const geneSets = useWorkbenchStore((s) => s.geneSets);

  // Activate the URL-specified gene set once it's loaded.
  useEffect(() => {
    if (id && geneSets.some((gs) => gs.id === id)) {
      setActiveSet(id);
    }
  }, [id, geneSets, setActiveSet]);

  return <WorkbenchMain />;
}
