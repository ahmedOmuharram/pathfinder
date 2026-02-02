export function EmptyGraphState(props: { isCompact: boolean }) {
  const { isCompact } = props;
  return (
    <div className="flex items-center justify-center h-full text-slate-500">
      <div className="text-center">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          className={`mx-auto mb-4 opacity-50 ${isCompact ? "h-8 w-8" : "h-16 w-16"}`}
        >
          <path d="M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z" />
          <path d="M10 7h4M7 10v4M17 10v4M10 17h4" />
        </svg>
        <p className={`text-slate-500 ${isCompact ? "text-xs" : "text-sm"}`}>
          Your strategy will appear here as you build it
        </p>
      </div>
    </div>
  );
}

