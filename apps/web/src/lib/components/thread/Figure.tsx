import type { ReactElement, ReactNode } from "react";

interface FigureProps {
  title: string | null;
  caption: string | null;
  children: ReactNode;
  testId?: string;
}

/** A typed result in the reading flow: a hairline, a title, the body, and a
 * caption that carries the numbers. `testId` names the part the figure draws,
 * and wraps the title and the caption with it. */
export function Figure({
  title,
  caption,
  children,
  testId,
}: FigureProps): ReactElement {
  const body = (
    <>
      {title !== null ? (
        <figcaption className="mb-2 text-sm font-medium">{title}</figcaption>
      ) : null}
      {children}
      {caption !== null ? (
        <div
          data-testid="figure-caption"
          className="mt-2 text-xs text-muted-foreground"
        >
          {caption}
        </div>
      ) : null}
    </>
  );
  return (
    <figure data-testid="figure" className="my-6 border-t border-border/60 pt-4">
      {testId === undefined ? body : <div data-testid={testId}>{body}</div>}
    </figure>
  );
}
