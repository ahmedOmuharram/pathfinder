/**
 * @vitest-environment jsdom
 */
import { afterEach, describe, it, expect, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { RecordRow } from "./RecordRow";
import type { RecordAttribute, WdkRecord } from "@/lib/types/wdk";

// Mock ResultsTableColumns to avoid DOMParser dependency
vi.mock("./ResultsTableColumns", () => ({
  ClassificationBadge: ({ value }: { value: string | null }) =>
    value ? <span data-testid="classification">{value}</span> : null,
  AttributeValue: ({ value }: { value: string | null | undefined }) => (
    <span data-testid="attr-value">{value ?? "\u2014"}</span>
  ),
}));

// Mock ExpandedRowDetail
vi.mock("./ExpandedRowDetail", () => ({
  ExpandedRowDetail: ({ pk, loading }: { pk: string; loading: boolean }) => (
    <div data-testid="expanded-detail" data-loading={loading}>
      {pk}
    </div>
  ),
}));

const columns: RecordAttribute[] = [
  { name: "gene_id", displayName: "Gene ID", isDisplayable: true },
  { name: "product", displayName: "Product", isDisplayable: true },
];

const record: WdkRecord = {
  id: [{ name: "source_id", value: "PF3D7_1234" }],
  attributes: { gene_id: "PF3D7_1234", product: "kinase" },
};

function renderRow(overrides: Partial<Parameters<typeof RecordRow>[0]> = {}) {
  const defaults = {
    record,
    pk: "PF3D7_1234",
    columns,
    hasClassification: false,
    isExpanded: false,
    detail: null,
    detailError: null,
    detailLoading: false,
    onToggle: vi.fn(),
    ...overrides,
  };

  return render(
    <table>
      <tbody>
        <RecordRow {...defaults} />
      </tbody>
    </table>,
  );
}

describe("RecordRow", () => {
  afterEach(cleanup);

  it("renders attribute values for each column", () => {
    renderRow();
    const values = screen.getAllByTestId("attr-value");
    expect(values).toHaveLength(2);
    expect(values[0]!.textContent).toBe("PF3D7_1234");
    expect(values[1]!.textContent).toBe("kinase");
  });

  it("calls onToggle when the data row is clicked", () => {
    const onToggle = vi.fn();
    const { container } = renderRow({ onToggle });
    // The clickable <tr> has data-expanded attribute
    const dataRow = container.querySelector("tr[data-expanded]");
    expect(dataRow).not.toBeNull();
    fireEvent.click(dataRow!);
    expect(onToggle).toHaveBeenCalledOnce();
  });

  it("shows classification badge when hasClassification is true", () => {
    const classifiedRecord: WdkRecord = {
      ...record,
      _classification: "TP" as const,
    };
    renderRow({ record: classifiedRecord, hasClassification: true });
    expect(screen.getByTestId("classification").textContent).toBe("TP");
  });

  it("renders ExpandedRowDetail with the pk", () => {
    renderRow({ isExpanded: true });
    // The detail is always in the DOM (hidden via CSS when collapsed),
    // so just verify it received the correct pk
    const details = screen.getAllByTestId("expanded-detail");
    expect(details.length).toBeGreaterThanOrEqual(1);
    expect(details[0]!.textContent).toContain("PF3D7_1234");
  });
});
