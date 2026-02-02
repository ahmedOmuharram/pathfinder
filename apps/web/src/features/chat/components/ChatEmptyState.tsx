import suggestedQuestions from "@/data/suggestedQuestions.json";

export function ChatEmptyState(props: {
  isCompact: boolean;
  siteId: string;
  displayName: string;
  firstName: string | undefined;
  signedIn: boolean;
  onSend: (message: string) => void;
  isStreaming: boolean;
  hasMessages: boolean;
}) {
  const { isCompact, siteId, displayName, firstName, signedIn, onSend, isStreaming, hasMessages } =
    props;

  if (hasMessages || isStreaming) return null;

  const suggestions =
    (suggestedQuestions as any)[siteId] ??
    (suggestedQuestions as any).plasmodb ??
    [];

  return (
    <div className="flex flex-col items-center justify-center h-full text-center">
      <h2
        className={`mb-2 font-semibold text-slate-900 ${
          isCompact ? "text-sm" : "text-base"
        }`}
      >
        {signedIn && firstName
          ? `Welcome, ${firstName}. Ready to create strategies?`
          : `Ready to create strategies?`}
      </h2>
      <p className={`max-w-md text-slate-500 ${isCompact ? "mb-3" : "mb-6"}`}>
        Ask me to prepare a VEuPathDB search strategy to push to the selected database (currently{" "}
        {displayName}). I can help you find genes, combine results, and explore your data.
      </p>
      <div className="grid max-w-lg grid-cols-1 gap-3 text-left">
        {suggestions.map((suggestion: string, i: number) => (
          <button
            key={i}
            onClick={() => onSend(suggestion)}
            className={`rounded-md border border-slate-200 bg-white px-3 py-2 text-left text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-50 ${
              isCompact ? "text-[11px]" : "text-[13px]"
            }`}
          >
            &ldquo;{suggestion}&rdquo;
          </button>
        ))}
      </div>
    </div>
  );
}

