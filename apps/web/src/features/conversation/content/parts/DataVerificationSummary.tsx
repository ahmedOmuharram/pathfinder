import type { DataVerificationSummaryPayload } from "@pathfinder/shared";

import { Figure } from "@/lib/components/thread/Figure";

export function DataVerificationSummary({
  data,
}: {
  data: DataVerificationSummaryPayload;
}) {
  const passedCount = data.checks.filter((check) => check.passed).length;
  return (
    <Figure
      testId="data-verification-summary"
      title="Verification"
      caption={`${passedCount.toLocaleString()} of ${data.checks.length.toLocaleString()} checks passed`}
    >
      <div className="text-xs">
        <p
          className={`text-sm font-medium ${
            data.passed ? "text-success" : "text-destructive"
          }`}
        >
          Verification {data.passed ? "passed" : "failed"}
        </p>
        <p className="mt-0.5 text-muted-foreground">{data.summary}</p>
        {data.checks.length > 0 ? (
          <ul className="mt-1 space-y-0.5">
            {data.checks.map((check) => (
              <li key={check.name} className="flex items-center gap-1.5">
                <span
                  className={`inline-block size-1.5 rounded-full ${
                    check.passed ? "bg-success" : "bg-destructive"
                  }`}
                />
                <span>{check.name}</span>
                {check.detail != null && check.detail.length > 0 ? (
                  <span className="text-muted-foreground">{`- ${check.detail}`}</span>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </Figure>
  );
}
