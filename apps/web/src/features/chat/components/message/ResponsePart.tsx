import type { Message, PlanningArtifact } from "@pathfinder/shared";
import { ChatMarkdown } from "@/lib/components/ChatMarkdown";
import { Card } from "@/lib/components/ui/Card";

interface ResponsePartProps {
  message: Message;
  onApplyPlanningArtifact?: (artifact: PlanningArtifact) => void;
}

export function ResponsePart({ message, onApplyPlanningArtifact }: ResponsePartProps) {
  return (
    <div className="rounded-lg px-3 py-2 border border-border bg-muted text-foreground">
      <ChatMarkdown
        content={message.content}
        citations={message.citations}
        tone="default"
      />
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
                        onClick={() => onApplyPlanningArtifact(a)}
                        className="rounded-md border border-border bg-card px-2 py-1 text-xs text-foreground transition-colors duration-150 hover:bg-accent"
                      >
                        Apply to strategy
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
