"use client";

import { Brain, ClipboardList, Notebook, Timer, Workflow } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";

import type { Strategy } from "@pathfinder/shared";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils/cn";
import { usePlanStore } from "@/state/usePlanStore";
import {
  useRightRailStore,
  type RightRailPanel,
} from "@/state/useRightRailStore";

import { MemoriesPanel } from "./MemoriesPanel";
import { PlanPanel } from "./PlanPanel";
import { ScratchpadPanel } from "./ScratchpadPanel";
import { StrategyPanel } from "./StrategyPanel";
import { TasksPanel } from "./TasksPanel";

const PANEL_WIDTH = 360;
const PANEL_TRANSITION = { type: "spring", stiffness: 380, damping: 36 } as const;
const ACTIVE_PILL =
  "bg-primary/15 text-primary hover:bg-primary/20 hover:text-primary";

interface RightRailProps {
  conversationId: string;
  strategy: Strategy | null;
  siteId: string;
}

interface RailIconSpec {
  id: RightRailPanel;
  icon: LucideIcon;
  label: string;
}

const RAIL_ICONS: RailIconSpec[] = [
  { id: "strategy", icon: Workflow, label: "Strategy" },
  { id: "plan", icon: ClipboardList, label: "Plan" },
  { id: "tasks", icon: Timer, label: "Tasks" },
  { id: "memories", icon: Brain, label: "Memories" },
  { id: "scratchpad", icon: Notebook, label: "Scratchpad" },
];

export function RightRail({ conversationId, strategy, siteId }: RightRailProps) {
  const openPanel = useRightRailStore((s) => s.openPanel);
  const lastSeen = useRightRailStore((s) => s.lastSeen);
  const togglePanel = useRightRailStore((s) => s.togglePanel);

  const strategyStepCount = strategy?.steps.length ?? 0;
  const activePlan = usePlanStore((s) => s.activePlanArtifact);
  const activePlanId = activePlan?.planId ?? null;

  const hasUpdate: Record<RightRailPanel, boolean> = {
    strategy: strategyStepCount !== lastSeen.strategyStepCount,
    plan: activePlanId !== null && activePlanId !== lastSeen.planId,
    tasks: false,
    memories: false,
    scratchpad: false,
  };

  const markersFor = (panel: RightRailPanel) => {
    switch (panel) {
      case "strategy":
        return { strategyStepCount };
      case "plan":
        return { planId: activePlanId };
      case "tasks":
      case "memories":
      case "scratchpad":
        return {};
    }
  };

  return (
    <TooltipProvider delayDuration={150}>
      <AnimatePresence initial={false}>
        {openPanel != null && (
          <motion.div
            key="rail-panel"
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: PANEL_WIDTH, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={PANEL_TRANSITION}
            className="h-full shrink-0 overflow-hidden border-l border-border bg-background"
          >
            <div style={{ width: PANEL_WIDTH }} className="h-full">
              <AnimatePresence mode="wait" initial={false}>
                <motion.div
                  key={openPanel}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.15 }}
                  className="h-full"
                >
                  {openPanel === "strategy" && (
                    <StrategyPanel strategy={strategy} siteId={siteId} />
                  )}
                  {openPanel === "plan" && <PlanPanel />}
                  {openPanel === "tasks" && (
                    <TasksPanel conversationId={conversationId} />
                  )}
                  {openPanel === "memories" && <MemoriesPanel />}
                  {openPanel === "scratchpad" && (
                    <ScratchpadPanel conversationId={conversationId} />
                  )}
                </motion.div>
              </AnimatePresence>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      <div
        className="flex h-full w-11 shrink-0 flex-col items-center gap-1 border-l border-border bg-sidebar py-2"
        aria-label="Right rail"
      >
        {RAIL_ICONS.map(({ id, icon: Icon, label }) => {
          const isOpen = openPanel === id;
          const showDot = hasUpdate[id] && !isOpen;
          return (
            <Tooltip key={id}>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => togglePanel(id, markersFor(id))}
                  aria-label={`${isOpen ? "Close" : "Open"} ${label}`}
                  aria-pressed={isOpen}
                  className={cn("relative", isOpen && ACTIVE_PILL)}
                >
                  <Icon className="h-4 w-4" aria-hidden />
                  <AnimatePresence>
                    {showDot && (
                      <motion.span
                        key="dot"
                        initial={{ scale: 0, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        exit={{ scale: 0, opacity: 0 }}
                        transition={{ type: "spring", stiffness: 500, damping: 24 }}
                        aria-label={`${label} has updates`}
                        className="absolute right-1 top-1 h-2 w-2 rounded-full bg-primary"
                      />
                    )}
                  </AnimatePresence>
                </Button>
              </TooltipTrigger>
              <TooltipContent side="left">{label}</TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </TooltipProvider>
  );
}
