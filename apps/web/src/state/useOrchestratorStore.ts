import { create } from "zustand";
import { z } from "zod";

export const supervisorEventSchema = z.object({
  kind: z.enum([
    "phase_enter",
    "phase_exit",
    "ejection",
    "approval",
    "deny",
    "plan_event",
    "build_outcome",
    "supervisor_note",
    "route",
    "summary",
  ]),
  summary: z.string(),
  detail: z.string().nullable(),
  phase: z.string().nullable(),
  refs: z.array(z.string()),
  at: z.string(),
});

export type SupervisorEventKind = z.infer<
  typeof supervisorEventSchema
>["kind"];
export type SupervisorEvent = z.infer<typeof supervisorEventSchema>;

interface OrchestratorState {
  events: SupervisorEvent[];
  appendEvent: (event: SupervisorEvent) => void;
  reset: () => void;
}

export const useOrchestratorStore = create<OrchestratorState>((set) => ({
  events: [],
  appendEvent: (event) =>
    set((s) => ({ events: [...s.events, event] })),
  reset: () => set({ events: [] }),
}));
