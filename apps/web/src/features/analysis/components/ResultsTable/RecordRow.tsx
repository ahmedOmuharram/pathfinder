import { ChevronDown, ChevronUp } from "lucide-react";
import type { RecordAttribute, RecordDetail, WdkRecord } from "@/lib/types/wdk";
import { ClassificationBadge, AttributeValue } from "./ResultsTableColumns";
import { ExpandedRowDetail } from "./ExpandedRowDetail";

interface RecordRowProps {
  record: WdkRecord;
  pk: string;
  columns: RecordAttribute[];
  hasClassification: boolean;
  isExpanded: boolean;
  detail: RecordDetail | null;
  detailError: string | null;
  detailLoading: boolean;
  onToggle: () => void;
}

export function RecordRow({
  record,
  pk,
  columns,
  hasClassification,
  isExpanded,
  detail,
  detailError,
  detailLoading,
  onToggle,
}: RecordRowProps) {
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
            <ExpandedRowDetail
              pk={pk}
              detail={detail}
              error={detailError}
              loading={detailLoading}
              onClose={onToggle}
            />
          </div>
        </td>
      </tr>
    </>
  );
}
