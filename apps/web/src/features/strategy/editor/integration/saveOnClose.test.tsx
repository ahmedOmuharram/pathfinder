// @vitest-environment jsdom
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import {
  cleanup,
  render,
  screen,
  fireEvent,
  waitFor,
  act,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { ParamSpec, Step, Strategy } from "@pathfinder/shared";
import type * as ConversationsModule from "@/lib/api/conversations";

const patchConversationStepMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api/conversations", async (importOriginal) => {
  const actual = await importOriginal<typeof ConversationsModule>();
  return { ...actual, patchConversationStep: patchConversationStepMock };
});

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), warning: vi.fn(), success: vi.fn() },
}));

const PARAM_SPECS = vi.hoisted(
  () =>
    [
      {
        name: "organism",
        type: "string",
        displayName: "Organism",
        displayType: "",
        allowEmptyValue: false,
        isVisible: true,
        isNumber: false,
        countOnlyLeaves: false,
        initialDisplayValue: "Pf3D7",
        allowMultipleValues: false,
        multiPick: false,
        minSelectedCount: null,
        maxSelectedCount: null,
        vocabulary: null,
        min: null,
        max: null,
        increment: null,
        group: null,
        help: null,
      },
      {
        name: "min_weight",
        type: "number",
        displayName: "Min Weight",
        displayType: "",
        allowEmptyValue: true,
        isVisible: true,
        isNumber: true,
        countOnlyLeaves: false,
        initialDisplayValue: "100",
        allowMultipleValues: false,
        multiPick: false,
        minSelectedCount: null,
        maxSelectedCount: null,
        vocabulary: null,
        min: 0,
        max: 999999,
        increment: 1,
        group: null,
        help: null,
      },
    ] satisfies ParamSpec[],
);

vi.mock("@/lib/hooks/useParamSpecs", () => ({
  useParamSpecs: () => ({ paramSpecs: PARAM_SPECS, isLoading: false, error: null }),
}));

vi.mock("@/state/strategy/store", () => ({
  useStrategyStore: <T,>(
    selector: (s: { graphValidationStatus: Record<string, boolean> }) => T,
  ): T => selector({ graphValidationStatus: {} }),
}));

vi.mock("@/state/useSessionStore", () => ({
  useSessionStore: <T,>(
    selector: (s: {
      selectedSite: string;
      selectedSiteDisplayName: string;
    }) => T,
  ): T =>
    selector({ selectedSite: "plasmodb", selectedSiteDisplayName: "PlasmoDB" }),
}));

vi.mock("@/lib/api/sites", () => ({
  getParamSpecs: vi.fn().mockResolvedValue(PARAM_SPECS),
  getRecordTypes: vi.fn().mockResolvedValue([{ name: "transcript", displayName: "Transcript" }]),
  getSearches: vi.fn().mockResolvedValue([
    { name: "GenesByTaxon", displayName: "Genes by taxon", recordType: "transcript" },
  ]),
  refreshDependentParams: vi.fn().mockResolvedValue([]),
  recordTypesOptions: (siteId: string) => ({
    queryKey: ["sites", siteId, "record-types"] as const,
    queryFn: async () => [{ name: "transcript", displayName: "Transcript" }],
    enabled: siteId !== "",
  }),
  searchesOptions: (siteId: string, recordType?: string | null) => ({
    queryKey: ["sites", siteId, "searches", recordType ?? "all"] as const,
    queryFn: async () => [
      { name: "GenesByTaxon", displayName: "Genes by taxon", recordType: "transcript" },
    ],
    enabled: siteId !== "",
  }),
  paramSpecsOptions: () => ({
    queryKey: ["param-specs"] as const,
    queryFn: async () => PARAM_SPECS,
    enabled: false,
  }),
}));

vi.mock("@/state/strategy/useStepSnapshot", () => ({
  useStepSnapshot: () => ({ estimatedSize: 0 }),
}));

import { Editor } from "../Editor";
import { conversationDetailKey } from "@/lib/api/conversations";

const STRATEGY_ID = "strategy-1";

function makeStep(overrides: Partial<Step> = {}): Step {
  return {
    id: "step-1",
    displayName: "Genes by taxon",
    searchName: "GenesByTaxon",
    recordType: "transcript",
    parameters: { organism: "Pf3D7", min_weight: "100" },
    isBuilt: false,
    isFiltered: false,
    operator: "",
    colocationParams: null,
    ...overrides,
  };
}

function makeStrategy(steps: Step[]): Strategy {
  return {
    id: STRATEGY_ID,
    name: "Test",
    siteId: "plasmodb",
    recordType: "transcript",
    steps,
    rootStepId: steps[0]?.id ?? null,
    isSaved: false,
    description: null,
    wdkStrategyId: null,
    wdkUrl: null,
    createdAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:00:00.000Z",
  };
}

interface Harness {
  client: QueryClient;
  Wrapper: ({ children }: { children: ReactNode }) => React.JSX.Element;
}

function makeHarness(initial: Strategy): Harness {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: Infinity },
      mutations: { retry: false },
    },
  });
  client.setQueryData(conversationDetailKey(initial.id), initial);
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  }
  return { client, Wrapper };
}

beforeEach(() => {
  patchConversationStepMock.mockReset();
  patchConversationStepMock.mockImplementation(
    async (_convId: string, _stepId: string, patch: Partial<Step>) => ({
      ...makeStep(),
      ...patch,
    }),
  );
  window.localStorage.clear();
});

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});

function renderEditor(opts?: { step?: Step }) {
  const step = opts?.step ?? makeStep();
  const strategy = makeStrategy([step]);
  const harness = makeHarness(strategy);
  let openState = true;
  const onOpenChange = vi.fn((next: boolean) => {
    openState = next;
  });
  const { rerender } = render(
    <Editor
      step={step}
      isOpen={openState}
      onOpenChange={onOpenChange}
      siteId="plasmodb"
      recordType="transcript"
      conversationId={STRATEGY_ID}
    />,
    { wrapper: harness.Wrapper },
  );
  return {
    harness,
    onOpenChange,
    step,
    rerender: (open: boolean) => {
      rerender(
        <Editor
          step={step}
          isOpen={open}
          onOpenChange={onOpenChange}
          siteId="plasmodb"
          recordType="transcript"
          conversationId={STRATEGY_ID}
        />,
      );
    },
  };
}

async function waitForOrganismInput(): Promise<HTMLInputElement> {
  const label = await screen.findByText("Organism", {}, { timeout: 5000 });
  const wrapper = label.parentElement;
  if (wrapper === null) throw new Error("Organism label has no parent");
  const input = wrapper.querySelector('input[name="organism"]');
  if (input === null) throw new Error("organism input not found");
  return input as HTMLInputElement;
}

async function waitForMinWeightInput(): Promise<HTMLInputElement> {
  const label = await screen.findByText("Min Weight", {}, { timeout: 5000 });
  const wrapper = label.parentElement;
  if (wrapper === null) throw new Error("Min Weight label has no parent");
  const input = wrapper.querySelector('input[name="min_weight"]');
  if (input === null) throw new Error("min_weight input not found");
  return input as HTMLInputElement;
}

describe("save-on-close UX", () => {
  it("does not autosave after typing into a field — change count appears instead", async () => {
    renderEditor();
    const organism = await waitForOrganismInput();

    fireEvent.change(organism, { target: { value: "PvP01" } });

    await waitFor(() => {
      expect(
        screen.getByTestId("step-editor-change-count").textContent,
      ).toBe("Edited: 1 change");
    });

    await new Promise((resolve) => setTimeout(resolve, 700));
    expect(patchConversationStepMock).not.toHaveBeenCalled();
  });

  it("clicking Save triggers exactly one PATCH and the sheet stays open", async () => {
    renderEditor();
    const organism = await waitForOrganismInput();

    fireEvent.change(organism, { target: { value: "PvP01" } });
    await waitFor(() => {
      expect(screen.getByTestId("step-editor-save")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("step-editor-save"));

    await waitFor(() => {
      expect(patchConversationStepMock).toHaveBeenCalledTimes(1);
    });
    expect(patchConversationStepMock).toHaveBeenCalledWith(
      STRATEGY_ID,
      "step-1",
      { parameters: { organism: "PvP01" } },
      "plasmodb",
    );
    expect(screen.getByTestId("step-editor-sheet")).toBeInTheDocument();
  });

  it("multiple sequential edits in one open session result in ONE PATCH on close", async () => {
    const harness = renderEditor();
    const organism = await waitForOrganismInput();

    fireEvent.change(organism, { target: { value: "PvP01" } });
    fireEvent.change(organism, { target: { value: "TgME49" } });
    fireEvent.change(organism, { target: { value: "Pk" } });

    const minWeight = await waitForMinWeightInput();
    fireEvent.change(minWeight, { target: { value: "5000" } });
    fireEvent.change(minWeight, { target: { value: "7500" } });

    expect(patchConversationStepMock).not.toHaveBeenCalled();

    await waitFor(() => {
      expect(
        screen.getByTestId("step-editor-change-count").textContent,
      ).toBe("Edited: 2 changes");
    });

    fireEvent.click(screen.getByTestId("step-editor-save"));

    await waitFor(() => {
      expect(patchConversationStepMock).toHaveBeenCalledTimes(1);
    });
    expect(patchConversationStepMock).toHaveBeenCalledWith(
      STRATEGY_ID,
      "step-1",
      { parameters: { organism: "Pk", min_weight: "7500" } },
      "plasmodb",
    );
    expect(harness.onOpenChange).not.toHaveBeenCalledWith(false);
  });

  it("Discard opens a confirm dialog; confirming resets the form and fires no PATCH", async () => {
    renderEditor();
    const organism = await waitForOrganismInput();

    fireEvent.change(organism, { target: { value: "PvP01" } });

    await waitFor(() => {
      expect(screen.getByTestId("step-editor-discard")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("step-editor-discard"));

    expect(
      await screen.findByTestId("step-editor-discard-confirm"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("step-editor-discard-confirm-button"));

    await waitFor(() => {
      const input = screen
        .getByText("Organism")
        .parentElement!.querySelector('input[name="organism"]') as HTMLInputElement;
      expect(input.value).toBe("Pf3D7");
    });
    expect(patchConversationStepMock).not.toHaveBeenCalled();
  });

  it("persists draft to localStorage after edit and clears on save success", async () => {
    renderEditor();
    const organism = await waitForOrganismInput();
    fireEvent.change(organism, { target: { value: "PvP01" } });

    await waitFor(() => {
      const stored = window.localStorage.getItem(
        `pathfinder.editor.draft.${STRATEGY_ID}.step-1`,
      );
      expect(stored).not.toBeNull();
      expect(JSON.parse(stored!)).toMatchObject({ organism: "PvP01" });
    });

    fireEvent.click(screen.getByTestId("step-editor-save"));
    await waitFor(() => {
      expect(patchConversationStepMock).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(
        window.localStorage.getItem(
          `pathfinder.editor.draft.${STRATEGY_ID}.step-1`,
        ),
      ).toBeNull();
    });
  });

  it("recovery banner appears on remount when localStorage has a divergent draft, Restore re-applies values", async () => {
    window.localStorage.setItem(
      `pathfinder.editor.draft.${STRATEGY_ID}.step-1`,
      JSON.stringify({ organism: "RecoveredValue", min_weight: "100" }),
    );

    renderEditor();
    await waitForOrganismInput();

    expect(
      await screen.findByTestId("step-editor-recovery-banner"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("step-editor-recovery-restore"));

    await waitFor(() => {
      const input = screen
        .getByText("Organism")
        .parentElement!.querySelector('input[name="organism"]') as HTMLInputElement;
      expect(input.value).toBe("RecoveredValue");
    });

    expect(
      window.localStorage.getItem(
        `pathfinder.editor.draft.${STRATEGY_ID}.step-1`,
      ),
    ).toBeNull();
  });

  it("recovery banner Discard clears localStorage without applying values", async () => {
    window.localStorage.setItem(
      `pathfinder.editor.draft.${STRATEGY_ID}.step-1`,
      JSON.stringify({ organism: "RecoveredValue", min_weight: "100" }),
    );

    renderEditor();
    const organismInput = await waitForOrganismInput();
    expect(organismInput.value).toBe("Pf3D7");

    fireEvent.click(screen.getByTestId("step-editor-recovery-discard"));

    await waitFor(() => {
      expect(
        window.localStorage.getItem(
          `pathfinder.editor.draft.${STRATEGY_ID}.step-1`,
        ),
      ).toBeNull();
    });
    expect(organismInput.value).toBe("Pf3D7");
  });

  it("closing the sheet with unsaved changes commits ONE PATCH then closes", async () => {
    const harness = renderEditor();
    const organism = await waitForOrganismInput();
    fireEvent.change(organism, { target: { value: "PvP01" } });

    await waitFor(() => {
      expect(screen.getByTestId("step-editor-change-count")).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.keyDown(document.body, { key: "Escape", code: "Escape" });
    });

    await waitFor(() => {
      expect(patchConversationStepMock).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(harness.onOpenChange).toHaveBeenCalledWith(false);
    });
  });
});
