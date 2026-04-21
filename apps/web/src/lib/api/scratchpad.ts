import type { CompactionRun } from "@pathfinder/shared/generated/types/CompactionRun";
import type { Note } from "@pathfinder/shared/generated/types/Note";
import { compactionRunSchema } from "@pathfinder/shared/generated/zod/compactionRunSchema";
import { noteSchema } from "@pathfinder/shared/generated/zod/noteSchema";
import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";

import { requestJson, requestVoid } from "./http";

const noteListSchema = z.array(noteSchema);
const compactionListSchema = z.array(compactionRunSchema);

export type { CompactionRun, Note };

export async function listScratchpadNotes(
  conversationId: string,
): Promise<Note[]> {
  return requestJson(
    noteListSchema,
    `/api/v1/conversations/${conversationId}/scratchpad/notes`,
  );
}

export async function getScratchpadNote(
  conversationId: string,
  noteId: string,
): Promise<Note> {
  return requestJson(
    noteSchema,
    `/api/v1/conversations/${conversationId}/scratchpad/notes/${noteId}`,
  );
}

export async function patchScratchpadNote(
  conversationId: string,
  noteId: string,
  body: { pinned: boolean },
): Promise<Note> {
  return requestJson(
    noteSchema,
    `/api/v1/conversations/${conversationId}/scratchpad/notes/${noteId}`,
    { method: "PATCH", body },
  );
}

export async function deleteScratchpadNote(
  conversationId: string,
  noteId: string,
): Promise<void> {
  await requestVoid(
    `/api/v1/conversations/${conversationId}/scratchpad/notes/${noteId}`,
    { method: "DELETE" },
  );
}

export async function listScratchpadCompactions(
  conversationId: string,
): Promise<CompactionRun[]> {
  return requestJson(
    compactionListSchema,
    `/api/v1/conversations/${conversationId}/scratchpad/compactions`,
  );
}

export function scratchpadNotesOptions(conversationId: string) {
  return queryOptions({
    queryKey: ["conversations", conversationId, "scratchpad", "notes"] as const,
    queryFn: () => listScratchpadNotes(conversationId),
  });
}

export function scratchpadCompactionsOptions(conversationId: string) {
  return queryOptions({
    queryKey: [
      "conversations",
      conversationId,
      "scratchpad",
      "compactions",
    ] as const,
    queryFn: () => listScratchpadCompactions(conversationId),
  });
}
