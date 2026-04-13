/**
 * Regression tests for Issue 1 (frontend half):
 *   Planning renders free text instead of structured widgets.
 *
 * The bug:
 *   ``PlanQuestionCard`` at ``PlanQuestionCard.tsx:115-120`` only routes to
 *   ``WdkQuestionInput`` when ``relatedStep``, ``relatedParam``, and ``siteId``
 *   are all present.  Otherwise it falls back to a plain ``<input type="text">``.
 *
 *   When the router does fire, ``WdkQuestionInput`` looks up the param spec
 *   via ``useParamSpecs`` and renders the full ``StepParamFields`` widget
 *   registry (TreeBox, TypeAhead, Select, Checkbox, String).
 *
 *   These tests document:
 *     - Spec-driven widget rendering (select/checkbox/typeahead behavior).
 *     - The contract that ``StepParamFields`` receives the correct
 *       ``siteId``, ``recordType``, and ``searchName`` from the question's
 *       step context.
 *     - The CURRENT buggy fallback for freeform clarifications (no
 *       ``relatedParam``) — documented so it surfaces the moment it's fixed.
 *
 * @vitest-environment jsdom
 */

import type { ComponentProps, ReactElement } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ParamSpec } from "@pathfinder/shared";

import { useParamSpecs } from "@/lib/hooks/useParamSpecs";
import type { PlannedStep, UserQuestion } from "@/lib/types/plan";
import { PlanQuestionCard } from "./PlanQuestionCard";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/lib/hooks/useParamSpecs", () => ({
  useParamSpecs: vi.fn(),
}));

// Capture the props passed to ``StepParamFields`` so we can assert that the
// question's step context flows through correctly.  Render a data-attributed
// shell rather than the real widget so the test stays focused on the wiring,
// not the widget internals (those are covered by the component's own tests).
const stepParamFieldsSpy = vi.hoisted(() =>
  vi.fn<
    (props: {
      paramSpecs: ParamSpec[];
      siteId: string;
      recordType: string;
      searchName: string;
    }) => void
  >(),
);

vi.mock("@/features/strategy/editor/components/StepParamFields", () => ({
  StepParamFields: (props: {
    paramSpecs: ParamSpec[];
    siteId: string;
    recordType: string;
    searchName: string;
  }) => {
    stepParamFieldsSpy(props);
    const specNames = props.paramSpecs.map((s) => s.name).join(",");
    return (
      <div
        data-testid="step-param-fields"
        data-site-id={props.siteId}
        data-record-type={props.recordType}
        data-search-name={props.searchName}
        data-spec-names={specNames}
      />
    );
  },
}));

const mockUseParamSpecs = vi.mocked(useParamSpecs);

// ---------------------------------------------------------------------------
// Fixtures — realistic WDK shapes mirroring the REST API payload
// ---------------------------------------------------------------------------

/**
 * A real ``ParamSpec`` shape for an organism treebox — the fields match the
 * OpenAPI ``ParamSpecResponse`` type exactly (see
 * ``packages/shared-ts/src/openapi.generated.ts``).
 */
const organismTreeBoxSpec: ParamSpec = {
  name: "organism",
  displayName: "Organism",
  type: "multi-pick-vocabulary",
  displayType: "treebox",
  allowEmptyValue: false,
  allowMultipleValues: true,
  countOnlyLeaves: false,
  initialDisplayValue: null,
  vocabulary: [
    {
      data: { value: "apicomplexa", term: "Apicomplexa" },
      children: [
        {
          data: { value: "pfal", term: "Plasmodium falciparum" },
          children: [],
        },
        {
          data: { value: "pvivax", term: "Plasmodium vivax" },
          children: [],
        },
      ],
    },
  ],
  isNumber: false,
  isVisible: true,
};

const organismSelectSpec: ParamSpec = {
  name: "organism",
  displayName: "Organism",
  type: "single-pick-vocabulary",
  displayType: "select",
  allowEmptyValue: false,
  allowMultipleValues: false,
  countOnlyLeaves: false,
  initialDisplayValue: "pfal",
  vocabulary: [
    { value: "a", label: "Option A" },
    { value: "b", label: "Option B" },
  ],
  isNumber: false,
  isVisible: true,
};

const geneIdsTypeAheadSpec: ParamSpec = {
  name: "gene_ids",
  displayName: "Gene IDs",
  type: "flat-vocabulary",
  displayType: "typeAhead",
  allowEmptyValue: false,
  allowMultipleValues: true,
  countOnlyLeaves: false,
  initialDisplayValue: null,
  vocabulary: [
    { value: "PF3D7_1343700", label: "PF3D7_1343700" },
    { value: "PF3D7_0102500", label: "PF3D7_0102500" },
  ],
  isNumber: false,
  isVisible: true,
};

const leafStep: PlannedStep = {
  id: "step_1",
  searchName: "GenesByTaxon",
  displayName: "Genes by Taxon",
  recordType: "transcript",
  rationale: "",
  stepType: "leaf",
  status: "needs_user_input",
  parameters: {},
  operator: null,
  expectedCount: null,
  actualCount: null,
  wdkStepId: null,
  graphStepId: null,
};

function organismQuestion(overrides: Partial<UserQuestion> = {}): UserQuestion {
  return {
    id: "q_organism",
    question: "Which organism?",
    context: "",
    relatedStep: "step_1",
    relatedParam: "organism",
    options: null,
    answer: null,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Render helper — wraps in QueryClientProvider to satisfy useParamSpecs
// ---------------------------------------------------------------------------

function renderWithProviders(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

function renderCard(props: Partial<ComponentProps<typeof PlanQuestionCard>> = {}) {
  return renderWithProviders(
    <PlanQuestionCard
      question={organismQuestion()}
      onAnswer={vi.fn()}
      disabled={false}
      steps={[leafStep]}
      siteId="plasmodb"
      {...props}
    />,
  );
}

// ---------------------------------------------------------------------------
// Test suites
// ---------------------------------------------------------------------------

beforeEach(() => {
  stepParamFieldsSpy.mockClear();
  mockUseParamSpecs.mockReset();
});

afterEach(() => {
  cleanup();
});

describe("PlanQuestionCard — WDK widget routing", () => {
  it("renders WdkQuestionInput (not a plain text input) when relatedStep, relatedParam, and siteId are all provided", () => {
    // Given a treeBox spec for the organism param
    mockUseParamSpecs.mockReturnValue({
      paramSpecs: [organismTreeBoxSpec],
      isLoading: false,
    });

    renderCard();

    // The WDK widget dispatch must have fired — with the treebox spec.
    expect(stepParamFieldsSpy).toHaveBeenCalled();
    expect(stepParamFieldsSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        paramSpecs: [organismTreeBoxSpec],
        siteId: "plasmodb",
        recordType: "transcript",
        searchName: "GenesByTaxon",
      }),
    );

    // The WdkQuestionInput marker must be in the DOM.
    const paramFields = screen.getByTestId("step-param-fields");
    expect(paramFields.getAttribute("data-spec-names")).toBe("organism");
    expect(paramFields.getAttribute("data-site-id")).toBe("plasmodb");
    expect(paramFields.getAttribute("data-record-type")).toBe("transcript");
    expect(paramFields.getAttribute("data-search-name")).toBe("GenesByTaxon");

    // CRITICAL: the plain text fallback must NOT appear.
    expect(screen.queryByPlaceholderText("Type your answer...")).toBeNull();
  });

  it("passes a typeAhead ParamSpec through when paramType is typeahead", () => {
    mockUseParamSpecs.mockReturnValue({
      paramSpecs: [geneIdsTypeAheadSpec],
      isLoading: false,
    });

    renderCard({
      question: organismQuestion({
        id: "q_genes",
        question: "Which genes?",
        relatedParam: "gene_ids",
      }),
    });

    expect(stepParamFieldsSpy).toHaveBeenCalled();
    const call = stepParamFieldsSpy.mock.calls.at(-1);
    expect(call).toBeDefined();
    const spec = call![0].paramSpecs[0];
    // Assert actual values flow through, not just presence.
    expect(spec).toBeDefined();
    expect(spec!.name).toBe("gene_ids");
    expect(spec!.displayType).toBe("typeAhead");
    expect(spec!.type).toBe("flat-vocabulary");
    expect(spec!.allowMultipleValues).toBe(true);
    // vocabulary content — value/label pairs must arrive intact.
    expect(spec!.vocabulary).toEqual([
      { value: "PF3D7_1343700", label: "PF3D7_1343700" },
      { value: "PF3D7_0102500", label: "PF3D7_0102500" },
    ]);

    // Plain text input must not be rendered.
    expect(screen.queryByPlaceholderText("Type your answer...")).toBeNull();
  });

  it("passes a select ParamSpec (with vocabulary=[{value:'a'},{value:'b'}]) when displayType=select", () => {
    mockUseParamSpecs.mockReturnValue({
      paramSpecs: [organismSelectSpec],
      isLoading: false,
    });

    renderCard();

    expect(stepParamFieldsSpy).toHaveBeenCalled();
    const call = stepParamFieldsSpy.mock.calls.at(-1);
    expect(call).toBeDefined();
    const spec = call![0].paramSpecs[0];
    expect(spec).toBeDefined();
    expect(spec!.displayType).toBe("select");
    // Exact vocabulary values — these drive the <option> list in the real widget.
    expect(spec!.vocabulary).toEqual([
      { value: "a", label: "Option A" },
      { value: "b", label: "Option B" },
    ]);
    // Not multi-pick.
    expect(spec!.allowMultipleValues).toBe(false);
  });

  it("passes the exact siteId / recordType / searchName from the question's step to StepParamFields", () => {
    mockUseParamSpecs.mockReturnValue({
      paramSpecs: [organismSelectSpec],
      isLoading: false,
    });

    const customStep: PlannedStep = {
      ...leafStep,
      id: "step_42",
      searchName: "GenesByLocation",
      recordType: "gene",
    };
    renderCard({
      question: organismQuestion({ relatedStep: "step_42" }),
      steps: [customStep],
      siteId: "toxodb",
    });

    expect(stepParamFieldsSpy).toHaveBeenCalled();
    expect(stepParamFieldsSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        siteId: "toxodb",
        recordType: "gene",
        searchName: "GenesByLocation",
      }),
    );

    // useParamSpecs must have been called with the same values — this is how
    // the frontend fetches the right spec for the right search.
    expect(mockUseParamSpecs).toHaveBeenCalledWith("toxodb", "gene", "GenesByLocation");
  });
});

describe("PlanQuestionCard — freeform fallback (CURRENT buggy behavior)", () => {
  /**
   * These tests document the CURRENT behavior for questions without a
   * ``relatedParam`` / ``relatedStep``.  The router skips the WDK widget
   * and renders a plain text ``<input>``.
   *
   * Issue 1's correct post-fix behavior: even freeform clarifications
   * (e.g. "What p-value threshold?") should render a richer control when
   * the agent can supply enough metadata (e.g. a numeric input with
   * min/max if the question is about a number).  Once that's implemented,
   * these tests must be UPDATED to assert the new widget path, not left
   * asserting the text input.
   */

  it("falls back to plain text <input> when the question has no relatedParam", () => {
    mockUseParamSpecs.mockReturnValue({ paramSpecs: [], isLoading: false });

    renderCard({
      question: organismQuestion({
        id: "q_pvalue",
        question: "What p-value threshold?",
        relatedStep: null,
        relatedParam: null,
      }),
    });

    const input = screen.getByPlaceholderText("Type your answer...");
    // An HTMLInputElement with type="text" — NOT a number input, NOT a select.
    expect(input).toBeInstanceOf(HTMLInputElement);
    expect((input as HTMLInputElement).type).toBe("text");

    // StepParamFields must NOT have been invoked for this fallback path.
    expect(stepParamFieldsSpy).not.toHaveBeenCalled();
  });

  it("falls back to plain text <input> when siteId is empty", () => {
    mockUseParamSpecs.mockReturnValue({
      paramSpecs: [organismTreeBoxSpec],
      isLoading: false,
    });

    renderCard({ siteId: "" });

    const input = screen.getByPlaceholderText("Type your answer...");
    expect(input).toBeInstanceOf(HTMLInputElement);
    expect((input as HTMLInputElement).type).toBe("text");
    expect(stepParamFieldsSpy).not.toHaveBeenCalled();
  });

  it("falls back to plain text <input> when the related step is not found in the steps list", () => {
    mockUseParamSpecs.mockReturnValue({
      paramSpecs: [organismTreeBoxSpec],
      isLoading: false,
    });

    renderCard({
      question: organismQuestion({ relatedStep: "step_missing" }),
    });

    const input = screen.getByPlaceholderText("Type your answer...");
    expect((input as HTMLInputElement).type).toBe("text");
    expect(stepParamFieldsSpy).not.toHaveBeenCalled();
  });

  it("submits the text answer via onAnswer when the Submit button is clicked", () => {
    mockUseParamSpecs.mockReturnValue({ paramSpecs: [], isLoading: false });
    const onAnswer = vi.fn();

    renderCard({
      question: organismQuestion({
        id: "q_freeform",
        relatedStep: null,
        relatedParam: null,
      }),
      onAnswer,
    });

    const input = screen.getByPlaceholderText("Type your answer...");
    fireEvent.change(input, { target: { value: "1e-5" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    expect(onAnswer).toHaveBeenCalledWith("q_freeform", "1e-5");
  });
});

describe("PlanQuestionCard — option list path (unchanged by Issue 1)", () => {
  it("renders predefined options instead of a WDK widget when question.options is non-empty", () => {
    mockUseParamSpecs.mockReturnValue({
      paramSpecs: [organismTreeBoxSpec],
      isLoading: false,
    });

    const questionWithOptions: UserQuestion = organismQuestion({
      id: "q_opts",
      options: [
        { label: "Option A", description: "First option", pros: [], cons: [], recommended: false },
        { label: "Option B", description: "Second option", pros: [], cons: [], recommended: true },
      ],
    });

    renderCard({ question: questionWithOptions });

    expect(screen.getByRole("button", { name: /Option A/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Option B/ })).toBeTruthy();
    // Neither the WDK widget nor the text input should appear.
    expect(stepParamFieldsSpy).not.toHaveBeenCalled();
    expect(screen.queryByPlaceholderText("Type your answer...")).toBeNull();
  });
});
