/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { DataProblemFrame } from "./DataProblemFrame";

describe("DataProblemFrame", () => {
  it("renders interpreted goal and entities", () => {
    render(
      <DataProblemFrame
        data={{
          siteId: "plasmodb",
          userGoal: "Find malaria genes",
          interpretedGoal:
            "Identify P. falciparum genes upregulated during erythrocytic stage",
          biologicalEntities: ["PfEMP1", "var genes"],
        }}
      />,
    );
    expect(screen.getByTestId("data-problem-frame")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Identify P. falciparum genes upregulated during erythrocytic stage",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("PfEMP1")).toBeInTheDocument();
    expect(screen.getByText("var genes")).toBeInTheDocument();
  });

  it("renders blocking and optional questions separately", () => {
    render(
      <DataProblemFrame
        data={{
          siteId: "plasmodb",
          userGoal: "g",
          interpretedGoal: "Differential expression",
          blockingQuestions: [
            {
              question: "Which strain?",
              context: "3D7 vs IT",
              priority: "blocking",
            },
          ],
          optionalQuestions: [
            {
              question: "Ring-stage only assumed",
              context: "vs all asexual stages",
              priority: "optional",
            },
          ],
        }}
      />,
    );
    expect(screen.getByText(/blocking — please answer/i)).toBeInTheDocument();
    expect(screen.getByText(/which strain/i)).toBeInTheDocument();
    expect(screen.getByText(/assumptions — correct me if needed/i)).toBeInTheDocument();
    expect(screen.getByText(/ring-stage only assumed/i)).toBeInTheDocument();
  });
});
