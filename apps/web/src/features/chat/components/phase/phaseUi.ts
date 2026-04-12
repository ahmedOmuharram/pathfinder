"use client";

export function formatPipelinePhaseLabel(phase: string): string {
  return phase.charAt(0).toUpperCase() + phase.slice(1);
}

export function formatPipelineStatusLabel(status: string): string {
  if (status === "awaiting_approval") return "Awaiting approval";
  if (status === "awaiting_input") return "Awaiting input";
  return status.charAt(0).toUpperCase() + status.slice(1);
}

export function formatPipelineDuration(
  durationMs: number | null,
  status: string,
): string {
  if (status === "started") return "Running";
  if (durationMs == null) return "Pending";
  if (durationMs < 1000) return `${durationMs} ms`;
  if (durationMs < 60_000) {
    return `${(durationMs / 1000).toFixed(durationMs < 10_000 ? 1 : 0)} s`;
  }
  const minutes = Math.floor(durationMs / 60_000);
  const seconds = Math.round((durationMs % 60_000) / 1000);
  return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
}

export function pipelineStatusTone(status: string): string {
  if (status === "started") return "border-blue-500/30 bg-blue-500/10 text-blue-200";
  if (status === "completed") {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-200";
  }
  if (status === "awaiting_approval") {
    return "border-amber-500/30 bg-amber-500/10 text-amber-200";
  }
  if (status === "awaiting_input") {
    return "border-yellow-500/30 bg-yellow-500/10 text-yellow-200";
  }
  if (status === "failed") return "border-red-500/30 bg-red-500/10 text-red-200";
  return "border-border/80 bg-background/70 text-foreground";
}
