import type { ConfusionMatrix } from "@pathfinder/shared";
import { Section } from "./Section";

interface ConfusionMatrixSectionProps {
  cm: ConfusionMatrix;
}

export function ConfusionMatrixSection({ cm }: ConfusionMatrixSectionProps) {
  const total =
    cm.truePositives + cm.falsePositives + cm.trueNegatives + cm.falseNegatives;

  const pctOf = (v: number) => (total > 0 ? `${((v / total) * 100).toFixed(1)}%` : "");

  return (
    <Section title="Confusion Matrix">
      <div className="inline-block rounded-lg border border-slate-200 bg-white">
        <table className="text-center text-[13px]">
          <thead>
            <tr>
              <th className="w-24" />
              <th
                colSpan={2}
                className="border-b border-slate-200 px-4 py-2 text-[10px] font-semibold uppercase tracking-widest text-slate-400"
              >
                Predicted
              </th>
            </tr>
            <tr>
              <th className="border-r border-slate-200 px-4 py-2 text-[10px] font-semibold uppercase tracking-widest text-slate-400">
                Actual
              </th>
              <th className="w-32 border-r border-b border-slate-200 px-4 py-2 text-[11px] font-medium text-slate-500">
                Positive
              </th>
              <th className="w-32 border-b border-slate-200 px-4 py-2 text-[11px] font-medium text-slate-500">
                Negative
              </th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="border-r border-b border-slate-200 px-4 py-2 text-[11px] font-medium text-slate-500">
                Positive
              </td>
              <td className="border-r border-b border-slate-200 bg-slate-50 px-4 py-3">
                <div className="text-lg font-semibold tabular-nums text-slate-900">
                  {cm.truePositives}
                </div>
                <div className="text-[10px] text-slate-400">
                  {pctOf(cm.truePositives)} TP
                </div>
              </td>
              <td className="border-b border-slate-200 px-4 py-3">
                <div className="text-lg font-semibold tabular-nums text-slate-900">
                  {cm.falseNegatives}
                </div>
                <div className="text-[10px] text-slate-400">
                  {pctOf(cm.falseNegatives)} FN
                </div>
              </td>
            </tr>
            <tr>
              <td className="border-r border-slate-200 px-4 py-2 text-[11px] font-medium text-slate-500">
                Negative
              </td>
              <td className="border-r border-slate-200 px-4 py-3">
                <div className="text-lg font-semibold tabular-nums text-slate-900">
                  {cm.falsePositives}
                </div>
                <div className="text-[10px] text-slate-400">
                  {pctOf(cm.falsePositives)} FP
                </div>
              </td>
              <td className="bg-slate-50 px-4 py-3">
                <div className="text-lg font-semibold tabular-nums text-slate-900">
                  {cm.trueNegatives}
                </div>
                <div className="text-[10px] text-slate-400">
                  {pctOf(cm.trueNegatives)} TN
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="mt-2 text-[11px] text-slate-400">
        n = {total} &middot; {cm.truePositives + cm.falseNegatives} actual positives
        &middot; {cm.trueNegatives + cm.falsePositives} actual negatives
      </div>
    </Section>
  );
}
