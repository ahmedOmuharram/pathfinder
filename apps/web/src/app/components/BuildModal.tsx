interface BuildModalProps {
  onCancel: () => void;
  onPushAnyway: () => void;
  onRebuild: () => void;
}

export function BuildModal({
  onCancel,
  onPushAnyway,
  onRebuild,
}: BuildModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-6 shadow-xl">
        <div className="text-lg font-semibold text-slate-900">Changes detected</div>
        <p className="mt-2 text-sm text-slate-600">
          The graph has changed since the last push. Push without rebuilding to use
          the previous version, or rebuild and push to include changes.
        </p>
        <div className="mt-4 flex flex-wrap justify-end gap-2">
          <button
            onClick={onCancel}
            className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 hover:border-slate-300 hover:text-slate-900"
          >
            Cancel
          </button>
          <button
            onClick={onPushAnyway}
            className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 hover:border-slate-300 hover:text-slate-900"
          >
            Push anyway
          </button>
          <button
            onClick={onRebuild}
            className="rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-700"
          >
            Rebuild and push
          </button>
        </div>
      </div>
    </div>
  );
}
