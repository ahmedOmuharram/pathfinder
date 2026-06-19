"use client";

import { useAuiState } from "@assistant-ui/react";
import type { PlanArtifact } from "@pathfinder/shared";
import { AnimatePresence, motion } from "motion/react";
import { Check, ChevronLeft, ChevronRight, ClipboardList } from "lucide-react";
import { useState } from "react";

import { Shimmer } from "@/components/ai-elements/shimmer";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";

import { useChatHelpersOptional } from "../../runtime/chatHelpersContext";
import {
  type PendingApprovalInfo,
  handleApprove,
  handleSuggestChanges,
} from "../../rail/planPanelActions";
import {
  PlanSlotForms,
  buildSlotAnswers,
  slotsAreFilled,
} from "../../rail/PlanSlotForm";
import { ApproveRow, ChangeRequest } from "./DecisionSlide";
import { DataPlanArtifact } from "./DataPlanArtifact";
import { ReadOnlyRecap } from "./PlanCarouselReadOnly";
import {
  type CarouselPhase,
  type Slide,
  carouselPhase,
  findPending,
  isSubmitResolved,
  planForCarousel,
} from "./planCarouselData";

export function PlanCarousel() {
  const currentId = useAuiState((s) => s.message.id);
  const statusType = useAuiState((s) => s.message.status?.type);
  const chat = useChatHelpersOptional();
  if (chat == null) return null;
  const message = chat.messages.find((m) => m.id === currentId);
  if (message?.role !== "assistant") return null;
  // Render the carousel inline in the message that carries the plan, so the
  // whole plan+questions block scrolls up with the chat like a tool card —
  // never pinned to the thread.
  const plan = planForCarousel(message, chat.messages);
  if (plan === null) return null;
  const pending = findPending(message);
  const submitted = isSubmitResolved(message);
  return (
    <PlanCarouselView
      plan={plan}
      pending={pending}
      submitted={submitted}
      phase={carouselPhase({ statusType, hasPending: pending !== null, submitted })}
      chat={chat}
    />
  );
}

const SLIDE_TRANSITION = { duration: 0.22, ease: [0.4, 0, 0.2, 1] } as const;

function PlanCarouselView({
  plan,
  pending,
  submitted,
  phase,
  chat,
}: {
  plan: PlanArtifact;
  pending: PendingApprovalInfo | null;
  submitted: boolean;
  phase: CarouselPhase;
  chat: NonNullable<ReturnType<typeof useChatHelpersOptional>>;
}) {
  const slots = plan.slots ?? [];
  const fillableSlots = slots.filter((s) => s.status !== "needs_discovery");
  const slides: Slide[] =
    fillableSlots.length > 0 ? [{ kind: "slots" as const, slots }] : [];

  const [planOpen, setPlanOpen] = useState(true);
  const [index, setIndex] = useState(0);
  const [direction, setDirection] = useState(1);
  const [slotValues, setSlotValues] = useState<Record<string, unknown>>({});
  const [changeOpen, setChangeOpen] = useState(false);
  const [changeText, setChangeText] = useState("");

  const slide = slides[index];
  const slideAnswered =
    slide === undefined ? true : slotsAreFilled(slide.slots, slotValues);
  const allAnswered = slotsAreFilled(slots, slotValues);
  const isLast = index >= slides.length - 1;

  const go = (next: number) => {
    setDirection(next > index ? 1 : -1);
    setIndex(Math.max(0, Math.min(next, slides.length - 1)));
  };

  const submit = () => {
    if (pending === null) return;
    handleApprove(chat, pending, buildSlotAnswers(slots, slotValues));
  };

  const requestChanges = () => {
    if (pending === null) return;
    const text = changeText.trim();
    if (text === "") return;
    handleSuggestChanges(chat, pending, text);
    setChangeText("");
    setChangeOpen(false);
  };

  return (
    <div
      data-testid="plan-carousel"
      data-phase={phase}
      className="my-2 space-y-2 rounded-lg border border-border bg-card/60 p-2"
    >
      <div
        className={cn(
          phase === "streaming" && "pointer-events-none animate-pulse opacity-60",
        )}
      >
        <button
          type="button"
          onClick={() => setPlanOpen((p) => !p)}
          className="flex w-full items-center gap-2 px-1 text-left text-sm font-medium"
        >
          <ClipboardList className="size-4 text-muted-foreground" aria-hidden />
          Proposed plan
          <span className="text-xs font-normal text-muted-foreground">
            {plan.steps.length} {plan.steps.length === 1 ? "step" : "steps"}
          </span>
          <ChevronRight
            className={cn(
              "ml-auto size-4 text-muted-foreground transition-transform",
              planOpen && "rotate-90",
            )}
            aria-hidden
          />
        </button>
        {planOpen && <DataPlanArtifact data={plan} embedded />}
      </div>

      {phase === "streaming" ? (
        <div
          data-testid="plan-carousel-streaming"
          className="rounded-md border border-border bg-background/60 px-3 py-2"
        >
          <Shimmer className="text-xs" duration={1.6}>
            Building plan…
          </Shimmer>
        </div>
      ) : phase === "interactive" ? (
        slides.length === 0 ? (
          <div className="rounded-md border border-border bg-background/60 p-2.5">
            <p className="mb-2 text-xs text-muted-foreground">
              Ready to run. Approve to execute, or request changes.
            </p>
            <ApproveRow
              submitLabel="Approve & run"
              onSubmit={submit}
              changeOpen={changeOpen}
              onToggleChange={() => setChangeOpen((p) => !p)}
              changeText={changeText}
              onChangeText={setChangeText}
              onRequestChanges={requestChanges}
            />
          </div>
        ) : (
          <div className="rounded-md border border-border bg-background/60 p-2.5">
            <div className="mb-2 flex items-center gap-1.5">
              {slides.map((_, i) => (
                <span
                  key={i}
                  className={cn(
                    "h-1.5 rounded-full transition-all",
                    i === index ? "w-5 bg-primary" : "w-1.5 bg-muted-foreground/30",
                  )}
                />
              ))}
              <span className="ml-auto text-[10px] text-muted-foreground tabular-nums">
                {index + 1} / {slides.length}
              </span>
            </div>

            <div className="relative overflow-hidden">
              <AnimatePresence mode="wait" custom={direction} initial={false}>
                <motion.div
                  key={index}
                  custom={direction}
                  initial={{ opacity: 0, x: direction * 24 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: direction * -24 }}
                  transition={SLIDE_TRANSITION}
                >
                  {slide?.kind === "slots" ? (
                    <PlanSlotForms
                      slots={slide.slots}
                      values={slotValues}
                      onChange={(key, value) =>
                        setSlotValues((prev) => ({ ...prev, [key]: value }))
                      }
                    />
                  ) : null}
                </motion.div>
              </AnimatePresence>
            </div>

            <div className="mt-2.5 flex items-center gap-2">
              <Button
                type="button"
                size="sm"
                variant="ghost"
                disabled={index === 0}
                onClick={() => go(index - 1)}
                data-testid="carousel-back"
              >
                <ChevronLeft className="size-4" aria-hidden /> Back
              </Button>
              {isLast ? (
                <Button
                  type="button"
                  size="sm"
                  className="ml-auto"
                  disabled={!allAnswered}
                  onClick={submit}
                  data-testid="carousel-submit"
                >
                  <Check className="mr-1 size-4" aria-hidden /> Submit
                </Button>
              ) : (
                <Button
                  type="button"
                  size="sm"
                  className="ml-auto"
                  disabled={!slideAnswered}
                  onClick={() => go(index + 1)}
                  data-testid="carousel-next"
                >
                  Next <ChevronRight className="ml-1 size-4" aria-hidden />
                </Button>
              )}
            </div>

            <div className="mt-2 border-t border-border/60 pt-2">
              <ChangeRequest
                open={changeOpen}
                onToggle={() => setChangeOpen((p) => !p)}
                text={changeText}
                onText={setChangeText}
                onSubmit={requestChanges}
              />
            </div>
          </div>
        )
      ) : (
        <ReadOnlyRecap slots={fillableSlots} submitted={submitted} />
      )}
    </div>
  );
}
