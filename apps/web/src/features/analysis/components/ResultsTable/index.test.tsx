/**
 * @vitest-environment jsdom
 */
import { afterEach, describe, it, expect, vi, beforeEach } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import type { RecordAttribute } from "@/lib/types/wdk";

// ---------------------------------------------------------------------------
// Mock the stepResults API module
// ---------------------------------------------------------------------------

const mockGetAttributes = vi.fn();
const mockGetRecords = vi.fn();
const mockGetRecordDetail = vi.fn();

vi.mock("@/features/analysis/api/stepResults", () => ({
  getAttributes: (...args: unknown[]) => mockGetAttributes(...args),
  getRecords: (...args: unknown[]) => mockGetRecords(...args),
  getRecordDetail: (...args: unknown[]) => mockGetRecordDetail(...args),
}));

// ---------------------------------------------------------------------------
// Mock sub-components to simplify rendering
// ---------------------------------------------------------------------------

vi.mock("./ResultsTableHeader", () => ({
  ResultsTableHeader: ({
    totalCount,
    visibleColumns,
  }: {
    totalCount: number;
    visibleColumns: Set<string>;
  }) => (
    <div data-testid="header">
      count={totalCount} cols={[...visibleColumns].join(",")}
    </div>
  ),
}));

vi.mock("./ResultsTableBody", () => ({
  ResultsTableBody: ({
    records,
    loading,
  }: {
    records: unknown[];
    loading: boolean;
  }) => (
    <div data-testid="body" data-loading={loading}>
      records={records.length}
    </div>
  ),
}));

vi.mock("./PaginationControls", () => ({
  PaginationControls: ({ totalCount }: { totalCount: number }) => (
    <div data-testid="pagination">total={totalCount}</div>
  ),
}));

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------

import { ResultsTable } from "./index";
import type { EntityRef } from "@/features/analysis/api/stepResults";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeAttrs(...names: string[]): RecordAttribute[] {
  return names.map((name) => ({
    name,
    displayName: name.replace(/_/g, " "),
    isDisplayable: true,
  }));
}

function makeRecordsResponse(count: number) {
  return {
    records: Array.from({ length: count }, (_, i) => ({
      id: [{ name: "source_id", value: `GENE_${i}` }],
      attributes: { gene_id: `GENE_${i}` },
    })),
    meta: {
      totalCount: count,
      displayTotalCount: count,
      responseCount: count,
      pagination: { offset: 0, numRecords: 25 },
      attributes: ["gene_id"],
      tables: [],
    },
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ResultsTable", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("resets visibleColumns when entityRef changes", async () => {
    const attrs1 = makeAttrs("gene_id", "organism", "product");
    const attrs2 = makeAttrs("molecular_weight", "go_terms", "ec_number");

    mockGetAttributes
      .mockResolvedValueOnce({ attributes: attrs1, recordType: "gene" })
      .mockResolvedValueOnce({ attributes: attrs2, recordType: "gene" });

    mockGetRecords
      .mockResolvedValueOnce(makeRecordsResponse(3))
      .mockResolvedValueOnce(makeRecordsResponse(2));

    const entity1: EntityRef = { type: "experiment", id: "exp-1" };
    const entity2: EntityRef = { type: "experiment", id: "exp-2" };

    const { rerender } = render(<ResultsTable entityRef={entity1} />);

    // Wait for first entity's attributes and records to load
    await waitFor(() => {
      const header = screen.getByTestId("header");
      expect(header.textContent).toContain("gene_id");
    });

    // Switch to second entity
    rerender(<ResultsTable entityRef={entity2} />);

    // After rerender, the header should show new columns from entity2
    await waitFor(() => {
      const header = screen.getByTestId("header");
      expect(header.textContent).toContain("molecular_weight");
    });

    // Old columns should be gone
    const header = screen.getByTestId("header");
    expect(header.textContent).not.toContain("gene_id");
  });

  it("stops loading when attributes list is empty", async () => {
    // Return empty displayable attributes
    mockGetAttributes.mockResolvedValueOnce({
      attributes: [{ name: "hidden", displayName: "Hidden", isDisplayable: false }],
      recordType: "gene",
    });

    const entity: EntityRef = { type: "experiment", id: "exp-1" };
    render(<ResultsTable entityRef={entity} />);

    // Should stop loading even with no displayable attributes.
    // The component filters out non-displayable, yielding 0 displayable attrs,
    // which sets attributes=[] and loading=false.
    await waitFor(() => {
      const body = screen.getByTestId("body");
      expect(body.getAttribute("data-loading")).toBe("false");
    });

    // getRecords should NOT have been called (no visible columns)
    expect(mockGetRecords).not.toHaveBeenCalled();
  });

  it("aborts previous record fetch when a new one starts", async () => {
    const attrs = makeAttrs("gene_id", "organism");
    mockGetAttributes.mockResolvedValue({
      attributes: attrs,
      recordType: "gene",
    });

    // First call takes a while, second resolves immediately
    let resolveFirst: (v: unknown) => void;
    const firstCall = new Promise((r) => {
      resolveFirst = r;
    });
    mockGetRecords
      .mockReturnValueOnce(firstCall)
      .mockResolvedValueOnce(makeRecordsResponse(5));

    const entity1: EntityRef = { type: "experiment", id: "exp-1" };
    const entity2: EntityRef = { type: "experiment", id: "exp-2" };

    const { rerender } = render(<ResultsTable entityRef={entity1} />);

    // Wait for attributes to load (triggers record fetch)
    await waitFor(() => {
      expect(mockGetRecords).toHaveBeenCalledTimes(1);
    });

    // Re-render with new entity before first records resolve
    rerender(<ResultsTable entityRef={entity2} />);

    // Wait for second entity's attributes + records
    await waitFor(() => {
      expect(mockGetAttributes).toHaveBeenCalledTimes(2);
    });

    // Resolve the first (stale) call -- it should be ignored via abort
    resolveFirst!(makeRecordsResponse(10));

    // Final state should reflect entity2's records (5), not entity1's (10)
    await waitFor(() => {
      const body = screen.getByTestId("body");
      expect(body.textContent).toContain("records=5");
    });
  });

  it("shows error state when getAttributes fails", async () => {
    mockGetAttributes.mockRejectedValueOnce(new Error("Server error"));

    const entity: EntityRef = { type: "experiment", id: "exp-1" };
    render(<ResultsTable entityRef={entity} />);

    // The component does String(err) so the text will be "Error: Server error"
    await waitFor(() => {
      expect(screen.getByText("Error: Server error")).toBeTruthy();
    });
  });
});
