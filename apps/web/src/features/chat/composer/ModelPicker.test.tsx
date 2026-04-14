// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { useEngineStore } from "@/state/useEngineStore";
import { useHasHydrated } from "@/lib/hooks/useHasHydrated";

import { ModelPicker } from "./ModelPicker";

vi.mock("@/lib/hooks/useHasHydrated", () => ({
  useHasHydrated: vi.fn(() => true),
}));

vi.mock("@/lib/api/models", () => ({
  modelCatalogOptions: () => ({
    queryKey: ["models", "catalog"] as const,
    queryFn: async () => ({
      models: [
        {
          id: "openai/gpt-4.1-mini",
          name: "GPT-4.1 Mini",
          provider: "openai",
          model: "gpt-4.1-mini",
          description: "",
          supportsReasoning: false,
          contextSize: 128000,
          enabled: true,
        },
        {
          id: "openai/gpt-4.1",
          name: "GPT-4.1",
          provider: "openai",
          model: "gpt-4.1",
          description: "",
          supportsReasoning: false,
          contextSize: 128000,
          enabled: true,
        },
        {
          id: "anthropic/claude-sonnet",
          name: "Claude Sonnet",
          provider: "anthropic",
          model: "claude-3-5-sonnet",
          description: "",
          supportsReasoning: false,
          contextSize: 200000,
          enabled: false,
        },
      ],
      defaultProvider: "openai" as const,
      defaultTier: "fast" as const,
    }),
    staleTime: Infinity,
  }),
}));

const INITIAL_PLANNING_MODEL = "openai/gpt-4.1-mini";

beforeEach(() => {
  useEngineStore.setState({
    tier: "fast",
    phases: {
      scoping: { modelId: INITIAL_PLANNING_MODEL },
      discovery: { modelId: INITIAL_PLANNING_MODEL },
      planning: { modelId: INITIAL_PLANNING_MODEL },
      execution: { modelId: INITIAL_PLANNING_MODEL },
      verification: { modelId: INITIAL_PLANNING_MODEL },
    } as ReturnType<typeof useEngineStore.getState>["phases"],
  });
});

afterEach(() => {
  cleanup();
});

describe("ModelPicker", () => {
  it("renders the current tier label and selected model name on the trigger", async () => {
    render(<ModelPicker />);
    await waitFor(() => {
      expect(screen.getByText("Fast")).toBeInTheDocument();
      expect(screen.getByText("GPT-4.1 Mini")).toBeInTheDocument();
    });
  });

  it("opens a searchable dialog when the trigger is clicked", async () => {
    render(<ModelPicker />);
    await waitFor(() => {
      expect(screen.getByText("GPT-4.1 Mini")).toBeInTheDocument();
    });

    const trigger = screen.getAllByRole("button")[0];
    if (!trigger) throw new Error("trigger not found");
    fireEvent.click(trigger);

    expect(await screen.findByPlaceholderText(/search models/i)).toBeInTheDocument();
  });

  it("groups models by provider in the list", async () => {
    render(<ModelPicker />);
    fireEvent.click((await screen.findAllByRole("button"))[0]!);

    await waitFor(() => {
      expect(screen.getByText("openai")).toBeInTheDocument();
      expect(screen.getByText("anthropic")).toBeInTheDocument();
    });
  });

  it("filters models when typing into the search box", async () => {
    render(<ModelPicker />);
    fireEvent.click((await screen.findAllByRole("button"))[0]!);

    const search = await screen.findByPlaceholderText(/search models/i);
    fireEvent.change(search, { target: { value: "claude" } });

    const dialog = await screen.findByRole("dialog");
    await waitFor(() => {
      expect(within(dialog).getByText("Claude Sonnet")).toBeInTheDocument();
    });
    expect(within(dialog).queryByText("GPT-4.1 Mini")).not.toBeInTheDocument();
  });

  it("shows an empty message when no models match the search", async () => {
    render(<ModelPicker />);
    fireEvent.click((await screen.findAllByRole("button"))[0]!);

    const search = await screen.findByPlaceholderText(/search models/i);
    fireEvent.change(search, { target: { value: "no-such-model-xyz" } });

    expect(await screen.findByText(/no models found/i)).toBeInTheDocument();
  });

  it("updates the planning phase model when a different model is selected", async () => {
    render(<ModelPicker />);
    fireEvent.click((await screen.findAllByRole("button"))[0]!);

    const dialog = await screen.findByRole("dialog");
    const targetItem = within(dialog).getByText("GPT-4.1");
    fireEvent.click(targetItem);

    await waitFor(() => {
      expect(useEngineStore.getState().phases.planning.modelId).toBe(
        "openai/gpt-4.1",
      );
    });
  });

  it("disables models whose provider has no API key", async () => {
    render(<ModelPicker />);
    fireEvent.click((await screen.findAllByRole("button"))[0]!);

    const dialog = await screen.findByRole("dialog");
    const claudeItem = within(dialog).getByText("Claude Sonnet").closest("[role='option']");
    expect(claudeItem).toHaveAttribute("data-disabled", "true");
  });

  it("hides the model name on the trigger before hydration to avoid SSR mismatch", async () => {
    vi.mocked(useHasHydrated).mockReturnValue(false);
    render(<ModelPicker />);

    await waitFor(() => {
      expect(screen.queryByText("GPT-4.1 Mini")).not.toBeInTheDocument();
      expect(screen.queryByText("Fast")).not.toBeInTheDocument();
    });
  });
});
