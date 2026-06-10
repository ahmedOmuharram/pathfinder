import type { DataVerificationSummaryPayload } from "@pathfinder/shared";

export function DataVerificationSummary({
  data,
}: {
  data: DataVerificationSummaryPayload;
}) {
  return (
    <div
      data-testid="data-verification-summary"
      className={`my-2 rounded-md border px-3 py-2 text-xs ${
        data.passed
          ? "border-success/30 bg-success/10"
          : "border-destructive/30 bg-destructive/10"
      }`}
    >
      <p className="font-medium text-sm">
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
                <span className="text-muted-foreground">— {check.detail}</span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
