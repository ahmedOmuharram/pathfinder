// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Step } from "@pathfinder/shared";

vi.mock("@tanstack/react-form", () => ({ useStore: () => ({}) }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("./EditorBody", () => ({ EditorBody: () => null }));
vi.mock("./EditorFooter", () => ({ EditorFooter: () => null }));
vi.mock("./useStepEditorState", () => ({
  useStepEditorState: () => ({
    kind: "search",
    name: "Genes by taxon",
    setName: vi.fn(),
    paramSpecs: [],
    hiddenDefaults: {},
    operatorValue: "",
    setOperatorValue: vi.fn(),
    colocationParams: null,
    setColocationParams: vi.fn(),
    searchOptions: [],
    onDependentFieldChange: vi.fn(),
    form: {
      store: {},
      state: { values: {} },
      reset: vi.fn(),
      setFieldValue: vi.fn(),
    },
    paramFormHydrated: true,
  }),
}));
vi.mock("@/features/strategy/graph/StrategyGraphContext", () => ({
  useStrategyGraphCtx: () => ({ requestDelete: vi.fn() }),
}));
vi.mock("@/features/strategy/mutations", () => ({
  useDuplicateStepMutation: () => ({ mutate: vi.fn() }),
  useUpdateStepMutation: () => ({
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
    isError: false,
  }),
}));
vi.mock("@/features/strategy/mutations/useSaveSubstrategyMutation", () => ({
  useSaveSubstrategyMutation: () => ({ mutate: vi.fn(), isPending: false }),
}));
vi.mock("@/lib/api/strategy", () => ({ useStrategyData: () => null }));
vi.mock("@/state/strategy/useStepSnapshot", () => ({
  useStepSnapshot: () => ({ estimatedSize: null }),
}));
vi.mock("./hooks/useStepDraftPersistence", () => ({
  useStepDraftPersistence: () => ({
    scheduleWrite: vi.fn(),
    flush: vi.fn(),
    clear: vi.fn(),
  }),
  useRecoveredDraft: () => ({ draft: null, dismiss: vi.fn() }),
}));
vi.mock("./hooks/useStepDraftChanges", () => ({
  useStepDraftChanges: () => ({ hasChanges: false, changeCount: 0 }),
}));

import { strategyStepUrl } from "@/lib/routes";
import { EditorContent } from "./EditorContent";

const STEP: Step = {
  id: "step_7",
  kind: "search",
  displayName: "Genes by taxon",
  searchName: "GenesByTaxon",
  recordType: "gene",
  parameters: {},
};

describe("EditorContent", () => {
  afterEach(cleanup);

  it("copies the step deep link the route builder produces", async () => {
    const writeText = vi.fn(async () => undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    render(
      <EditorContent
        step={STEP}
        siteId="plasmodb"
        recordType="gene"
        conversationId="conv-1"
        registerCloseHandler={vi.fn()}
        onClosed={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByLabelText("More actions"));
    await userEvent.click(await screen.findByText("Copy step URL"));
    expect(writeText).toHaveBeenCalledWith(
      `${window.location.origin}${strategyStepUrl("plasmodb", "conv-1", "step_7")}`,
    );
    expect(writeText).toHaveBeenCalledWith(
      "http://localhost:3000/plasmodb/conversation/conv-1/strategy/step/step_7",
    );
    expect(writeText).toHaveBeenCalledTimes(1);
  });
});
