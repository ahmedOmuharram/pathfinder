import type { ProblemFramePart } from "@pathfinder/shared";

export function DataProblemFrame({ data }: { data: ProblemFramePart }) {
  return (
    <div
      data-testid="data-problem-frame"
      className="my-2 rounded-md border border-border bg-card px-3 py-2 text-xs"
    >
      <p className="font-medium text-sm">{data.interpretedGoal}</p>
      {data.organismScope != null && data.organismScope.length > 0 ? (
        <p className="mt-1 text-muted-foreground">
          Organism: {data.organismScope}
        </p>
      ) : null}
      {data.biologicalEntities && data.biologicalEntities.length > 0 ? (
        <div className="mt-1 flex flex-wrap gap-1">
          {data.biologicalEntities.map((entity) => (
            <span
              key={entity}
              className="rounded bg-muted px-1.5 py-0.5 text-[10px]"
            >
              {entity}
            </span>
          ))}
        </div>
      ) : null}
      {data.blockingQuestions && data.blockingQuestions.length > 0 ? (
        <div className="mt-2 border-t border-border pt-1">
          <p className="text-[10px] font-medium uppercase tracking-wide text-destructive">
            Blocking — please answer
          </p>
          <ul className="mt-0.5 list-inside list-disc text-foreground">
            {data.blockingQuestions.map((q) => (
              <li key={q.question}>
                {q.question}
                {q.context != null && q.context.length > 0 ? (
                  <span className="ml-1 text-muted-foreground">
                    — {q.context}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {data.optionalQuestions && data.optionalQuestions.length > 0 ? (
        <div className="mt-2 border-t border-border pt-1">
          <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Assumptions — correct me if needed
          </p>
          <ul className="mt-0.5 list-inside list-disc text-muted-foreground">
            {data.optionalQuestions.map((q) => (
              <li key={q.question}>
                {q.question}
                {q.context != null && q.context.length > 0 ? (
                  <span className="ml-1 opacity-80">— {q.context}</span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
