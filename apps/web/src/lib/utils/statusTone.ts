export type Tone = "neutral" | "warn" | "bad" | "good";

const BADGE: Record<Tone, string> = {
  good: "bg-success/15 text-success",
  warn: "bg-warning/15 text-warning",
  bad: "bg-destructive/15 text-destructive",
  neutral: "bg-muted text-muted-foreground",
};

const DOT: Record<Tone, string> = {
  good: "bg-success",
  warn: "bg-warning",
  bad: "bg-destructive",
  neutral: "bg-muted-foreground/40",
};

export function toneBadge(tone: Tone): string {
  return BADGE[tone];
}

export function toneDot(tone: Tone): string {
  return DOT[tone];
}
