import { useState, useEffect, useCallback } from "react";
import { BarChart3, Loader2, AlertCircle } from "lucide-react";
import { Button } from "@/lib/components/ui/Button";
import {
  getExperimentAttributes,
  getExperimentDistribution,
  type RecordAttribute,
} from "../../api";

interface DistributionExplorerProps {
  experimentId: string;
}

interface DistributionEntry {
  value: string;
  count: number;
}

function parseDistribution(raw: Record<string, unknown>): DistributionEntry[] {
  const histogram = (raw.histogram ?? raw.distribution ?? raw) as Record<
    string,
    unknown
  >;

  return Object.entries(histogram)
    .filter(([key]) => key !== "total" && key !== "attributeName")
    .map(([value, count]) => ({ value, count: Number(count) || 0 }))
    .sort((a, b) => b.count - a.count);
}

export function DistributionExplorer({ experimentId }: DistributionExplorerProps) {
  const [attributes, setAttributes] = useState<RecordAttribute[]>([]);
  const [selectedAttr, setSelectedAttr] = useState<string>("");
  const [distribution, setDistribution] = useState<DistributionEntry[]>([]);
  const [loadingAttrs, setLoadingAttrs] = useState(true);
  const [loadingDist, setLoadingDist] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoadingAttrs(true);
    setError(null);

    getExperimentAttributes(experimentId)
      .then(({ attributes: attrs }) => {
        if (cancelled) return;
        const SKIP_ATTRS = new Set([
          "primary_key",
          "overview",
          "snp_overview",
          "record_overview",
        ]);
        const displayable = attrs.filter(
          (a) =>
            a.isDisplayable !== false &&
            !SKIP_ATTRS.has(a.name) &&
            !a.name.startsWith("wdk_") &&
            !a.name.endsWith("Link") &&
            a.type !== "link",
        );
        setAttributes(displayable);
        if (displayable.length > 0 && !selectedAttr) {
          setSelectedAttr(displayable[0].name);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(String(err));
      })
      .finally(() => {
        if (!cancelled) setLoadingAttrs(false);
      });

    return () => {
      cancelled = true;
    };
    // Only fetch attributes on mount / experimentId change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [experimentId]);

  const fetchDistribution = useCallback(
    (attrName: string) => {
      if (!attrName) return;
      setLoadingDist(true);
      setError(null);

      getExperimentDistribution(experimentId, attrName)
        .then((raw) => setDistribution(parseDistribution(raw)))
        .catch((err) => {
          const msg = err instanceof Error ? err.message : String(err);
          if (msg.includes("422") || msg.includes("not a valid filter")) {
            setError(
              `No distribution data available for this attribute. Try a different one.`,
            );
          } else {
            setError(msg);
          }
        })
        .finally(() => setLoadingDist(false));
    },
    [experimentId],
  );

  useEffect(() => {
    if (selectedAttr) fetchDistribution(selectedAttr);
  }, [selectedAttr, fetchDistribution]);

  const maxCount = Math.max(1, ...distribution.map((d) => d.count));
  const topEntries = distribution.slice(0, 20);

  if (loadingAttrs) {
    return (
      <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading attributes…
      </div>
    );
  }

  if (error && attributes.length === 0) {
    return (
      <div className="flex items-center gap-2 py-8 text-sm text-destructive">
        <AlertCircle className="h-4 w-4" />
        {error}
      </div>
    );
  }

  if (attributes.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-muted-foreground">
        No displayable attributes found.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <BarChart3 className="h-4 w-4 text-muted-foreground" />
        <select
          value={selectedAttr}
          onChange={(e) => setSelectedAttr(e.target.value)}
          className="h-8 rounded-md border border-input bg-background px-3 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        >
          {attributes.map((attr) => (
            <option key={attr.name} value={attr.name}>
              {attr.displayName}
            </option>
          ))}
        </select>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => fetchDistribution(selectedAttr)}
          disabled={loadingDist}
          loading={loadingDist}
        >
          Refresh
        </Button>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-xs text-destructive">
          <AlertCircle className="h-3.5 w-3.5" />
          {error}
        </div>
      )}

      {loadingDist ? (
        <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading distribution…
        </div>
      ) : topEntries.length === 0 ? (
        <div className="py-6 text-center text-xs text-muted-foreground">
          No distribution data available for this attribute.
        </div>
      ) : (
        <div className="space-y-1.5">
          {topEntries.map(({ value, count }) => {
            const pct = (count / maxCount) * 100;
            return (
              <div key={value} className="group flex items-center gap-3">
                <span
                  className="w-28 shrink-0 truncate text-right text-xs text-muted-foreground"
                  title={value}
                >
                  {value || "(empty)"}
                </span>
                <div className="relative h-5 flex-1 overflow-hidden rounded bg-muted/40">
                  <div
                    className="absolute inset-y-0 left-0 rounded bg-primary/20 transition-all duration-300 group-hover:bg-primary/30"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="w-14 shrink-0 text-right font-mono text-xs tabular-nums text-foreground">
                  {count.toLocaleString()}
                </span>
              </div>
            );
          })}
          {distribution.length > 20 && (
            <p className="pt-1 text-right text-xs text-muted-foreground">
              Showing top 20 of {distribution.length} values
            </p>
          )}
        </div>
      )}
    </div>
  );
}
