import type { AssistantMessage, PlanningArtifact } from "@pathfinder/shared";
import { ChatMarkdown } from "@/lib/components/ChatMarkdown";
import { Card } from "@/lib/components/ui/Card";

interface ResponsePartProps {
  message: AssistantMessage;
  isApplyingArtifact?: boolean;
  onApplyPlanningArtifact?: (artifact: PlanningArtifact) => void;
}

function CompactList({
  title,
  items,
}: {
  title: string;
  items?: string[] | undefined;
}) {
  const filtered = items?.filter(Boolean) ?? [];
  if (filtered.length === 0) return null;
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </div>
      <ul className="mt-1 list-disc space-y-1 pl-4 text-xs">
        {filtered.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function ProblemFrameCard({ message }: { message: AssistantMessage }) {
  const frame = message.problemFrame;
  if (frame == null) return null;
  const questions = frame.blockingQuestions ?? [];
  return (
    <Card className="mt-2 rounded-md border-amber-200 bg-amber-50/70 px-3 py-2 text-sm text-amber-950">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-semibold text-amber-950">Problem frame</div>
          <div className="mt-1 text-xs leading-relaxed text-amber-900">
            {frame.interpretedGoal}
          </div>
        </div>
        <span className="shrink-0 rounded-full border border-amber-300 bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-900">
          {frame.readyForWdkDiscovery ? "Ready" : "Needs input"}
        </span>
      </div>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        <CompactList title="Scope" items={[
          frame.organismScope ?? "",
          frame.recordType != null && frame.recordType !== ""
            ? `Record type: ${frame.recordType}`
            : "",
        ]} />
        <CompactList title="Success Criteria" items={frame.successCriteria} />
        <CompactList title="Assumptions" items={frame.assumptions} />
        <CompactList title="Likely Data" items={frame.likelyDataSources} />
      </div>
      {questions.length > 0 && (
        <div className="mt-2 rounded-md border border-amber-200 bg-white/60 px-2 py-2">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-amber-800">
            Blocking questions
          </div>
          <ul className="mt-1 list-disc space-y-1 pl-4 text-xs">
            {questions.map((q) => (
              <li key={q.question}>{q.question}</li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

export function ResponsePart({ message, isApplyingArtifact = false, onApplyPlanningArtifact }: ResponsePartProps) {
  return (
    <div className="rounded-lg px-3 py-2 border border-border bg-muted text-foreground">
      <ChatMarkdown
        content={message.content}
        {...(message.citations != null ? { citations: message.citations } : {})}
        tone="default"
      />
      <ProblemFrameCard message={message} />
      {Array.isArray(message.planningArtifacts) &&
        message.planningArtifacts.length > 0 && (
          <Card className="mt-2 rounded-md px-2 py-2 text-sm">
            <div className="mb-1 font-medium text-foreground">
              Saved planning artifacts
            </div>
            <ul className="list-disc space-y-1 pl-4">
              {message.planningArtifacts.map((a) => (
                <li key={a.id}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{a.title}</span>
                    {a.proposedStrategyPlan && onApplyPlanningArtifact ? (
                      <button
                        type="button"
                        disabled={isApplyingArtifact}
                        onClick={() => onApplyPlanningArtifact(a)}
                        className="rounded-md border border-border bg-card px-2 py-1 text-xs text-foreground transition-colors duration-150 hover:bg-accent disabled:pointer-events-none disabled:opacity-50"
                      >
                        {isApplyingArtifact ? "Applying..." : "Apply to strategy"}
                      </button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        )}
    </div>
  );
}
