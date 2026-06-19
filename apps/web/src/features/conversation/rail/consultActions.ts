"use client";

import type { UIMessage } from "ai";

import type { ChatHelpersForApproval } from "./planPanelActions";

export const USER_QUESTION_ANSWERS_PART_TYPE = "data-user-question-answers";

export type UserQuestionAnswerEntry = {
  questionId: string;
  prompt: string;
  chosenLabels: string[];
  note: string;
};

export function handleConsultSubmit(
  chat: ChatHelpersForApproval,
  pending: { approvalId: string; sourceMessage: UIMessage },
  answers: UserQuestionAnswerEntry[],
): void {
  const part: UIMessage["parts"][number] = {
    type: USER_QUESTION_ANSWERS_PART_TYPE,
    data: {
      toolCallId: pending.approvalId,
      answers: answers.map((a) => ({
        questionId: a.questionId,
        prompt: a.prompt,
        chosenLabels: a.chosenLabels,
        note: a.note,
      })),
    },
  } as unknown as UIMessage["parts"][number];

  chat.setMessages((messages) =>
    messages.map((msg) => {
      if (msg.id !== pending.sourceMessage.id) return msg;
      const filtered = msg.parts.filter(
        (p) => p.type !== USER_QUESTION_ANSWERS_PART_TYPE,
      );
      return { ...msg, parts: [...filtered, part] };
    }),
  );
  chat.addToolApprovalResponse({ id: pending.approvalId, approved: true });
}
