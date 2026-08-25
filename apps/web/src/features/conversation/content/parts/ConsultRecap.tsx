"use client";

import { HelpCircle } from "lucide-react";

import type { ConsultRecap } from "./consultData";

export function ConsultRecapView({ recap }: { recap: ConsultRecap }) {
  const answerByQuestion = new Map(recap.answers.map((a) => [a.questionId, a]));
  return (
    <div
      data-testid="consult-recap"
      className="my-2 space-y-2 rounded-lg border border-border bg-card/60 p-2"
    >
      <div className="flex items-center gap-2 px-1 text-sm font-medium">
        <HelpCircle className="size-4 text-muted-foreground" aria-hidden />
        Questions you answered
      </div>
      <ul className="space-y-1.5 rounded-md border border-border bg-background/60 p-2.5 text-xs">
        {recap.questions.map((q) => {
          const a = answerByQuestion.get(q.id);
          const chosen =
            a && a.chosenLabels.length > 0 ? a.chosenLabels.join(", ") : a?.note;
          return (
            <li key={q.id} className="leading-snug">
              <span className="font-medium text-foreground">{q.prompt}</span>
              <span className="mx-1 text-muted-foreground">→</span>
              <span className="text-foreground">
                {chosen !== undefined && chosen !== "" ? chosen : "—"}
              </span>
              {a !== undefined && a.note !== "" && a.chosenLabels.length > 0 && (
                <span className="text-muted-foreground"> ({a.note})</span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
