/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import type { LedgerFramePayload } from "@pathfinder/shared";

import {
  BuildSection,
  FrameSection,
  IntentSection,
  VerificationSection,
} from "./LedgerPanelSections";

describe("IntentSection", () => {
  it("renders the classification, goal, and differential sides", () => {
    render(
      <IntentSection
        intent={{
          classification: "NEW_STRATEGY",
          inferredGoal: "Find kinase drug targets",
          isDifferential: true,
          differentialSides: ["expressed", "not expressed"],
        }}
      />,
    );
    expect(screen.getByText("NEW_STRATEGY")).toBeInTheDocument();
    expect(screen.getByText("Find kinase drug targets")).toBeInTheDocument();
    expect(screen.getByText("expressed")).toBeInTheDocument();
  });

  it("shows 'Not classified yet' for null", () => {
    render(<IntentSection intent={null} />);
    expect(screen.getByText(/not classified yet/i)).toBeInTheDocument();
  });

  it("shows 'Not classified yet' for undefined (the exclude_none wire gap) — does not crash", () => {
    render(<IntentSection intent={undefined} />);
    expect(screen.getByText(/not classified yet/i)).toBeInTheDocument();
  });
});

const FRAME_WITH_SPEC: LedgerFramePayload = {
  present: true,
  criteriaCount: 2,
  boundCount: 2,
  openSlotCount: 1,
  droppedCount: 1,
  readyToBuild: false,
  needsUser: true,
  contrasts: [
    {
      criterionId: "gametocyte_enrichment",
      comparator: "gametocyte",
      reference: "asexual",
      direction: "up-regulated",
      summary: "up-regulated in gametocyte vs asexual",
    },
  ],
  structureRender: "(GenesByText INTERSECT GenesByTaxon)",
  spec: {
    goal: "find gametocyte genes",
    interpretedGoal: "find gametocyte genes",
    recordType: "transcript",
    organismScope: "Plasmodium falciparum",
    title: "Gametocyte genes",
    readyToBuild: false,
    criteria: [
      {
        id: "c1",
        text: "product mentions gametocyte",
        searchName: "GenesByText",
        role: "seed",
        resolvedParams: { text_expression: "gametocyte", text_fields: "product" },
        openParams: [],
        confidence: 0.9,
      },
      {
        id: "c2",
        text: "restrict to Pf",
        searchName: "GenesByTaxon",
        role: "filter",
        resolvedParams: {},
        openParams: [
          { criterionId: "c2", paramName: "organism", question: "Which organism?" },
        ],
        confidence: 0.5,
      },
    ],
    dropped: [{ text: "ortholog map", reason: "search unavailable" }],
    openSlots: [
      { criterionId: "c2", paramName: "organism", question: "Which organism?" },
    ],
  },
};

describe("FrameSection detail", () => {
  it("renders only counts in summary mode (no criteria detail)", () => {
    render(<FrameSection frame={FRAME_WITH_SPEC} />);
    expect(screen.queryByText("GenesByText")).not.toBeInTheDocument();
  });

  it("renders criteria, resolved params, structure and dropped in detail mode", () => {
    render(<FrameSection frame={FRAME_WITH_SPEC} detail />);
    expect(screen.getByText("GenesByText")).toBeInTheDocument();
    expect(screen.getByText(/product mentions gametocyte/)).toBeInTheDocument();
    expect(screen.getByText(/text_fields/)).toBeInTheDocument();
    expect(screen.getByText(/Which organism\?/)).toBeInTheDocument();
    expect(
      screen.getByText("(GenesByText INTERSECT GenesByTaxon)"),
    ).toBeInTheDocument();
    expect(screen.getByText(/search unavailable/)).toBeInTheDocument();
  });
});

const BUILD_WITH_NODES = {
  pushedCount: 2,
  failedCount: 1,
  skippedCount: 0,
  zeroResultSteps: [],
  needsRecovery: true,
  recoveryKind: "search_replan" as const,
  succeeded: false,
  wdkStrategyId: 42,
  wdkUrl: "https://plasmodb.org/s/42",
  nodeResults: [
    { nodeId: "n1", searchName: "GenesByText", count: 61, status: "ok" as const },
    {
      nodeId: "n2",
      searchName: "GenesByOrthologs",
      status: "failed" as const,
      error: "Answer Params must be null",
    },
  ],
};

describe("BuildSection detail", () => {
  it("renders per-node results and the strategy link in detail mode", () => {
    render(<BuildSection build={BUILD_WITH_NODES} detail />);
    expect(screen.getByText("GenesByText")).toBeInTheDocument();
    expect(screen.getByText(/61/)).toBeInTheDocument();
    expect(screen.getByText("GenesByOrthologs")).toBeInTheDocument();
    expect(screen.getByText(/Answer Params must be null/)).toBeInTheDocument();
    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      "https://plasmodb.org/s/42",
    );
  });

  it("omits node detail in summary mode", () => {
    render(<BuildSection build={BUILD_WITH_NODES} />);
    expect(screen.queryByText("GenesByOrthologs")).not.toBeInTheDocument();
  });

  it("does not crash on a legacy payload missing nodeResults", () => {
    // Ledger snapshots persisted before nodeResults existed arrive without the
    // field; the detail view must tolerate the wire gap, not throw.
    const legacy = {
      pushedCount: 1,
      failedCount: 0,
      skippedCount: 0,
      zeroResultSteps: [],
      needsRecovery: false,
      recoveryKind: "none" as const,
      succeeded: true,
    } as unknown as typeof BUILD_WITH_NODES;
    render(<BuildSection build={legacy} detail />);
    expect(screen.getByText("Build")).toBeInTheDocument();
  });

  it("labels combine nodes 'Combine', never the raw __combine__ sentinel", () => {
    const build = {
      ...BUILD_WITH_NODES,
      nodeResults: [
        { nodeId: "n1", searchName: "GenesByText", count: 61, status: "ok" as const },
        { nodeId: "n3", searchName: "__combine__", count: 42, status: "ok" as const },
      ],
    };
    render(<BuildSection build={build} detail />);
    expect(screen.getByText("Combine")).toBeInTheDocument();
    expect(screen.queryByText("__combine__")).not.toBeInTheDocument();
  });
});

const VERIFY_WITH_DIGEST = {
  complete: true,
  successful: true,
  digest: {
    prose: "The strategy returned 61 gametocyte genes.",
    reason: "sizes look right",
    success: true,
    keyFindings: ["61 genes overlap the gold set"],
    caveats: ["product-name search matched 0"],
  },
};

describe("VerificationSection detail", () => {
  it("renders prose, findings and caveats in detail mode", () => {
    render(<VerificationSection verification={VERIFY_WITH_DIGEST} detail />);
    expect(screen.getByText(/61 gametocyte genes/)).toBeInTheDocument();
    expect(screen.getByText(/61 genes overlap the gold set/)).toBeInTheDocument();
    expect(screen.getByText(/product-name search matched 0/)).toBeInTheDocument();
  });

  it("omits digest prose in summary mode", () => {
    render(<VerificationSection verification={VERIFY_WITH_DIGEST} />);
    expect(screen.queryByText(/61 gametocyte genes/)).not.toBeInTheDocument();
  });
});
