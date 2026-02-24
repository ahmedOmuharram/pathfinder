import { useState, useEffect, useCallback, useRef } from "react";
import {
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Columns,
  ArrowUpDown,
  X,
  Loader2,
} from "lucide-react";
import { Button } from "@/lib/components/ui/Button";
import { Badge } from "@/lib/components/ui/Badge";
import {
  getExperimentRecords,
  getExperimentAttributes,
  getExperimentRecordDetail,
} from "../../api";
import type { RecordAttribute, WdkRecord, RecordsResponse } from "../../api";

interface ResultsTableProps {
  experimentId: string;
}

type SortDir = "ASC" | "DESC";
type Classification = "TP" | "FP" | "FN" | "TN";

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100];

const CLASSIFICATION_STYLES: Record<
  Classification,
  {
    label: string;
    variant: "success" | "destructive" | "warning" | "default";
    className?: string;
  }
> = {
  TP: { label: "True Positive", variant: "success" },
  FP: { label: "False Positive", variant: "destructive" },
  FN: { label: "False Negative", variant: "warning" },
  TN: {
    label: "True Negative",
    variant: "default",
    className: "bg-blue-500/15 text-blue-600 border-transparent",
  },
};

function getPrimaryKey(record: WdkRecord): string {
  if (!Array.isArray(record.id) || record.id.length === 0) {
    return String(record.id ?? "unknown");
  }
  return record.id.map((k) => k.value).join("/");
}

export function ResultsTable({ experimentId }: ResultsTableProps) {
  const [attributes, setAttributes] = useState<RecordAttribute[]>([]);
  const [visibleColumns, setVisibleColumns] = useState<Set<string>>(new Set());
  const [columnsOpen, setColumnsOpen] = useState(false);
  const columnsRef = useRef<HTMLDivElement>(null);

  const [records, setRecords] = useState<WdkRecord[]>([]);
  const [meta, setMeta] = useState<RecordsResponse["meta"] | null>(null);
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("ASC");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getExperimentAttributes(experimentId)
      .then(({ attributes: attrs }) => {
        if (cancelled) return;
        const displayable = attrs.filter((a) => a.isDisplayable !== false);
        setAttributes(displayable);
        setVisibleColumns(new Set(displayable.slice(0, 6).map((a) => a.name)));
      })
      .catch((err) => {
        if (!cancelled) setError(String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [experimentId]);

  const fetchRecords = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getExperimentRecords(experimentId, {
        offset,
        limit: pageSize,
        sort: sortColumn ?? undefined,
        dir: sortColumn ? sortDir : undefined,
        attributes: [...visibleColumns],
      });
      setRecords(res.records);
      setMeta(res.meta);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [experimentId, offset, pageSize, sortColumn, sortDir, visibleColumns]);

  useEffect(() => {
    if (visibleColumns.size > 0) fetchRecords();
  }, [fetchRecords, visibleColumns]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (columnsRef.current && !columnsRef.current.contains(e.target as Node)) {
        setColumnsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSort = useCallback(
    (colName: string) => {
      if (sortColumn === colName) {
        setSortDir((d) => (d === "ASC" ? "DESC" : "ASC"));
      } else {
        setSortColumn(colName);
        setSortDir("ASC");
      }
      setOffset(0);
    },
    [sortColumn],
  );

  const handleExpandRow = useCallback(
    async (key: string, recordId: WdkRecord["id"]) => {
      if (expandedKey === key) {
        setExpandedKey(null);
        setDetail(null);
        return;
      }
      setExpandedKey(key);
      setDetail(null);
      setDetailLoading(true);
      try {
        const d = await getExperimentRecordDetail(experimentId, recordId);
        setDetail(d);
      } catch {
        setDetail(null);
      } finally {
        setDetailLoading(false);
      }
    },
    [experimentId, expandedKey],
  );

  const toggleColumn = useCallback((name: string) => {
    setVisibleColumns((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
    setOffset(0);
  }, []);

  const totalCount = meta?.totalCount ?? 0;
  const currentPage = Math.floor(offset / pageSize) + 1;
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const hasPrev = offset > 0;
  const hasNext = offset + pageSize < totalCount;

  const orderedColumns = attributes.filter((a) => visibleColumns.has(a.name));
  const hasClassification = records.some((r) => r._classification != null);

  if (error && records.length === 0) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-center">
        <p className="text-sm text-destructive">{error}</p>
        <Button variant="outline" size="sm" className="mt-3" onClick={fetchRecords}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground tabular-nums">
          {totalCount.toLocaleString()} records
        </p>

        <div className="flex items-center gap-2">
          <div ref={columnsRef} className="relative">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setColumnsOpen((o) => !o)}
            >
              <Columns className="h-3.5 w-3.5" />
              Columns
            </Button>

            {columnsOpen && (
              <div className="absolute right-0 top-full z-30 mt-1 w-64 rounded-lg border border-border bg-popover p-2 shadow-lg">
                <div className="max-h-60 overflow-y-auto space-y-0.5">
                  {attributes.map((attr) => (
                    <label
                      key={attr.name}
                      className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent transition-colors"
                    >
                      <input
                        type="checkbox"
                        checked={visibleColumns.has(attr.name)}
                        onChange={() => toggleColumn(attr.name)}
                        className="rounded border-border"
                      />
                      <span className="truncate">{attr.displayName}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              {hasClassification && (
                <th className="whitespace-nowrap px-4 py-2.5 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Class
                </th>
              )}
              {orderedColumns.map((col) => (
                <th key={col.name} className="whitespace-nowrap px-4 py-2.5">
                  <button
                    type="button"
                    onClick={() => handleSort(col.name)}
                    className="inline-flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {col.displayName}
                    {sortColumn === col.name ? (
                      sortDir === "ASC" ? (
                        <ChevronUp className="h-3 w-3" />
                      ) : (
                        <ChevronDown className="h-3 w-3" />
                      )
                    ) : (
                      <ArrowUpDown className="h-3 w-3 opacity-40" />
                    )}
                  </button>
                </th>
              ))}
              <th className="w-8 px-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {loading && records.length === 0 ? (
              <tr>
                <td
                  colSpan={orderedColumns.length + (hasClassification ? 1 : 0) + 1}
                  className="py-16 text-center"
                >
                  <Loader2 className="mx-auto h-5 w-5 animate-spin text-muted-foreground" />
                </td>
              </tr>
            ) : records.length === 0 ? (
              <tr>
                <td
                  colSpan={orderedColumns.length + (hasClassification ? 1 : 0) + 1}
                  className="py-16 text-center text-sm text-muted-foreground"
                >
                  No records found.
                </td>
              </tr>
            ) : (
              records.map((record) => {
                const pk = getPrimaryKey(record);
                const isExpanded = expandedKey === pk;
                return (
                  <RecordRow
                    key={pk}
                    record={record}
                    pk={pk}
                    columns={orderedColumns}
                    hasClassification={hasClassification}
                    isExpanded={isExpanded}
                    detail={isExpanded ? detail : null}
                    detailLoading={isExpanded && detailLoading}
                    onToggle={() => handleExpandRow(pk, record.id)}
                  />
                );
              })
            )}
          </tbody>
        </table>

        {loading && records.length > 0 && (
          <div className="flex items-center justify-center border-t border-border bg-muted/30 py-2">
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          </div>
        )}
      </div>

      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <span>Rows per page</span>
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setOffset(0);
            }}
            className="rounded-md border border-border bg-background px-2 py-1 text-xs"
          >
            {PAGE_SIZE_OPTIONS.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-3">
          <span className="tabular-nums">
            Page {currentPage} of {totalPages}
          </span>
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon"
              className="h-7 w-7"
              disabled={!hasPrev || loading}
              onClick={() => setOffset((o) => Math.max(0, o - pageSize))}
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              className="h-7 w-7"
              disabled={!hasNext || loading}
              onClick={() => setOffset((o) => o + pageSize)}
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function RecordRow({
  record,
  pk,
  columns,
  hasClassification,
  isExpanded,
  detail,
  detailLoading,
  onToggle,
}: {
  record: WdkRecord;
  pk: string;
  columns: RecordAttribute[];
  hasClassification: boolean;
  isExpanded: boolean;
  detail: Record<string, unknown> | null;
  detailLoading: boolean;
  onToggle: () => void;
}) {
  const colSpan = columns.length + (hasClassification ? 1 : 0) + 1;

  return (
    <>
      <tr
        onClick={onToggle}
        className="cursor-pointer transition-colors hover:bg-accent/50 data-[expanded=true]:bg-accent/30"
        data-expanded={isExpanded}
      >
        {hasClassification && (
          <td className="px-4 py-2">
            <ClassificationBadge value={record._classification ?? null} />
          </td>
        )}
        {columns.map((col) => (
          <td
            key={col.name}
            className="max-w-[300px] truncate px-4 py-2 text-sm text-foreground"
          >
            <AttributeValue value={record.attributes[col.name]} />
          </td>
        ))}
        <td className="px-2 py-2 text-muted-foreground">
          {isExpanded ? (
            <ChevronUp className="h-3.5 w-3.5" />
          ) : (
            <ChevronDown className="h-3.5 w-3.5" />
          )}
        </td>
      </tr>
      <tr>
        <td colSpan={colSpan} className="p-0">
          <div
            className="overflow-hidden transition-all duration-200 ease-in-out"
            style={{
              maxHeight: isExpanded ? "500px" : "0px",
              opacity: isExpanded ? 1 : 0,
            }}
          >
            <DetailPanel
              pk={pk}
              detail={detail}
              loading={detailLoading}
              onClose={onToggle}
            />
          </div>
        </td>
      </tr>
    </>
  );
}

function ClassificationBadge({ value }: { value: Classification | null }) {
  if (!value) return null;
  const style = CLASSIFICATION_STYLES[value];
  return (
    <Badge variant={style.variant} className={style.className}>
      {style.label}
    </Badge>
  );
}

const HTML_TAG_RE = /<[^>]+>/;

function stripHtml(html: string): string {
  const doc = new DOMParser().parseFromString(html, "text/html");
  return doc.body.textContent ?? "";
}

function tryParseJsonLink(raw: string): { text: string; url: string } | null {
  if (!raw.startsWith("{")) return null;
  try {
    const obj = JSON.parse(raw) as Record<string, unknown>;
    const url = obj.url ?? obj.href;
    if (typeof url === "string") {
      const text = typeof obj.displayText === "string" ? obj.displayText : "Link";
      return { text, url };
    }
  } catch {
    /* not JSON */
  }
  return null;
}

function AttributeValue({ value }: { value: string | null | undefined }) {
  if (value == null) return <span className="text-muted-foreground">—</span>;

  const str = typeof value === "object" ? JSON.stringify(value) : String(value);

  const link = tryParseJsonLink(str);
  if (link) {
    return (
      <a
        href={link.url}
        target="_blank"
        rel="noopener noreferrer"
        onClick={(e) => e.stopPropagation()}
        className="text-primary underline decoration-primary/30 transition hover:decoration-primary"
      >
        {link.text}
      </a>
    );
  }

  if (HTML_TAG_RE.test(str)) return <>{stripHtml(str)}</>;

  return <>{str}</>;
}

function AttributeValueRich({ value }: { value: unknown }) {
  if (value == null) return <span className="text-muted-foreground">—</span>;

  const str = typeof value === "object" ? JSON.stringify(value) : String(value);

  const link = tryParseJsonLink(str);
  if (link) {
    return (
      <a
        href={link.url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary underline decoration-primary/30 transition hover:decoration-primary"
      >
        {link.text}
      </a>
    );
  }

  if (HTML_TAG_RE.test(str)) {
    return (
      <span
        className="[&_a]:text-primary [&_a]:underline"
        dangerouslySetInnerHTML={{ __html: str }}
      />
    );
  }

  return <>{str}</>;
}

function DetailPanel({
  pk,
  detail,
  loading,
  onClose,
}: {
  pk: string;
  detail: Record<string, unknown> | null;
  loading: boolean;
  onClose: () => void;
}) {
  const attrs =
    detail && typeof detail.attributes === "object" && detail.attributes != null
      ? (detail.attributes as Record<string, unknown>)
      : detail;

  return (
    <div className="border-t border-border bg-muted/30 px-6 py-4">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Record Detail — {pk}
        </h4>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onClose();
          }}
          className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading details…
        </div>
      ) : attrs ? (
        <div className="max-h-72 overflow-y-auto">
          <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1.5 text-sm">
            {Object.entries(attrs).map(([key, val]) => (
              <div key={key} className="contents">
                <dt className="whitespace-nowrap font-medium text-muted-foreground">
                  {key}
                </dt>
                <dd className="text-foreground">
                  <AttributeValueRich value={val} />
                </dd>
              </div>
            ))}
          </dl>
        </div>
      ) : (
        <p className="py-4 text-sm text-muted-foreground">Unable to load details.</p>
      )}
    </div>
  );
}
