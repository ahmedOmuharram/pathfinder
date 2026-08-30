// @vitest-environment jsdom
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { ModelCatalogModal } from "./ModelCatalogModal";

const BASE = "http://localhost:3000";

const CATALOG = {
  models: [
    {
      id: "openai:gpt-5.6-luna",
      name: "GPT-5.6 Luna",
      description: "Default model",
      supportsReasoning: true,
      contextSize: 400000,
      inputPrice: 1.25,
      cachedInputPrice: 0.75,
      outputPrice: 10,
      isProviderSmallest: false,
      provider: "openai",
      modelName: "gpt-5.6-luna",
      enabled: true,
    },
  ],
  defaultProvider: "openai",
  defaultTier: "default",
  phaseDefaults: {},
};

const server = setupServer(
  http.get(`${BASE}/api/v1/models`, () => HttpResponse.json(CATALOG)),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("ModelCatalogModal", () => {
  it("prices the cached-input column from the primary token", async () => {
    render(<ModelCatalogModal open onOpenChange={() => {}} />);
    const cell = await screen.findByText("$0.75");
    expect(cell).toHaveClass("text-primary/80");
    expect(cell.className).not.toContain("sky");
  });
});
