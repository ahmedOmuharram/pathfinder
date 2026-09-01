/**
 * @vitest-environment jsdom
 */
import type { UIMessage } from "ai";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { ConsultRecapView } from "./ConsultRecap";
import { findConsultRecap, type ConsultRecap } from "./consultData";

const PROMPT =
  "For a febrile-versus-normal differential test, should I retain both " +
  "temperature-condition groups in the analysis?";

const CHOSEN = "Retain febrile and normal (recommended)";

function answeredMessage(): UIMessage {
  return {
    id: "m1",
    role: "assistant",
    parts: [
      {
        type: "tool-consult_user",
        toolCallId: "call_N1NVJP9yWQgucA4I5LWpfvbH",
        state: "output-available",
        input: {
          questions: [
            {
              id: "comparison_scope",
              kind: "single_choice",
              prompt: PROMPT,
              context: "The study has an exact temperature_condition variable.",
              options: [{ label: CHOSEN }, { label: "Febrile-only subset" }],
              allowNotes: true,
            },
          ],
        },
        output: [
          {
            questionId: "comparison_scope",
            prompt: PROMPT,
            chosenLabels: [CHOSEN],
            note: "",
          },
        ],
      },
    ] as UIMessage["parts"],
  };
}

function recapOf(message: UIMessage): ConsultRecap {
  const recap = findConsultRecap(message);
  if (recap === null) throw new Error("the message carries no consult recap");
  return recap;
}

describe("ConsultRecapView", () => {
  it("renders the label the user chose, not the empty placeholder", () => {
    render(<ConsultRecapView recap={recapOf(answeredMessage())} />);
    const recap = screen.getByTestId("consult-recap");
    expect(recap).toHaveTextContent(PROMPT);
    expect(recap).toHaveTextContent(CHOSEN);
  });

  it("heads the card Your answers and lays each pair out as Q: then A:", () => {
    render(<ConsultRecapView recap={recapOf(answeredMessage())} />);
    const recap = screen.getByTestId("consult-recap");
    expect(recap.textContent).toBe(`Your answersQ: ${PROMPT}A: ${CHOSEN}`);
    expect(screen.getByTestId("consult-recap-question").textContent).toBe(
      `Q: ${PROMPT}`,
    );
    expect(screen.getByTestId("consult-recap-answer").textContent).toBe(`A: ${CHOSEN}`);
  });

  it("keeps a block gap between one pair and the next", () => {
    render(<ConsultRecapView recap={recapOf(answeredMessage())} />);
    expect(screen.getByTestId("consult-recap-pairs")).toHaveClass("space-y-3");
    expect(screen.getAllByTestId("consult-recap-question")).toHaveLength(1);
  });

  it("writes the note beside the labels the user picked", () => {
    const questions = recapOf(answeredMessage()).questions;
    render(
      <ConsultRecapView
        recap={{
          questions,
          answers: [
            {
              questionId: "comparison_scope",
              prompt: PROMPT,
              chosenLabels: [CHOSEN],
              note: "only the 2016 cohort",
            },
          ],
        }}
      />,
    );
    expect(screen.getByTestId("consult-recap-answer").textContent).toBe(
      `A: ${CHOSEN} (only the 2016 cohort)`,
    );
  });

  it("writes the unanswered placeholder in ASCII", () => {
    const questions = recapOf(answeredMessage()).questions;
    render(<ConsultRecapView recap={{ questions, answers: [] }} />);
    const text = screen.getByTestId("consult-recap").textContent;
    expect(text).toBe(`Your answersQ: ${PROMPT}A: -`);
    expect(text).not.toMatch(/[^\x20-\x7e]/);
  });
});
