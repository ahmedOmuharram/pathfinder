export function GraphWdkBadge(props: {
  isCompact: boolean;
  wdkStrategyId?: number;
  wdkUrl?: string | null;
  wdkUrlFallback?: string | null;
}) {
  const { isCompact, wdkStrategyId, wdkUrl, wdkUrlFallback } = props;
  if (isCompact) return null;
  if (!wdkStrategyId && !wdkUrl && !wdkUrlFallback) return null;

  const href = wdkUrl || wdkUrlFallback || undefined;

  return (
    <div className="pointer-events-auto absolute left-4 top-4 z-10 rounded-lg border border-slate-200 bg-white/90 px-2 py-1 text-[11px] text-slate-600 shadow-sm backdrop-blur">
      {wdkStrategyId && (
        <div className="font-medium">
          Synced{" "}
          {href ? (
            <a
              className="font-mono text-slate-900 underline decoration-slate-300 underline-offset-4 hover:text-slate-700"
              href={href}
              target="_blank"
              rel="noreferrer"
            >
              #{wdkStrategyId}
            </a>
          ) : (
            <span className="font-mono">#{wdkStrategyId}</span>
          )}
        </div>
      )}

      {href && !wdkStrategyId && (
        <a
          className="inline-block text-slate-900 underline decoration-slate-300 underline-offset-4 hover:text-slate-700"
          href={href}
          target="_blank"
          rel="noreferrer"
        >
          View
        </a>
      )}
    </div>
  );
}

