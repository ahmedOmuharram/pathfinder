"use client";

import { useState } from "react";
import { useWorkbenchStore } from "@/state/useWorkbenchStore";
import { WorkbenchMain } from "@/features/workbench/components/WorkbenchMain";

export default function WorkbenchPage() {
  const setActiveSet = useWorkbenchStore((s) => s.setActiveSet);

  useState(() => setActiveSet(null));

  return <WorkbenchMain />;
}
