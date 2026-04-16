"use client";

import { Differ, Viewer } from "json-diff-kit";
import "json-diff-kit/dist/viewer.css";
import { useQuery } from "@tanstack/react-query";
import type { CheckpointSnapshot } from "@pathfinder/shared/generated/types/CheckpointSnapshot";
import { client } from "@/lib/api/client";

const differ = new Differ({
  detectCircular: true,
  maxDepth: 6,
  arrayDiffMethod: "lcs",
});

interface CheckpointDiffViewProps {
  chatId: string;
  leftCp: string;
  rightCp: string;
}

function useCheckpoint(chatId: string, checkpointId: string) {
  return useQuery<CheckpointSnapshot>({
    queryKey: ["checkpoint", chatId, checkpointId],
    queryFn: async () => {
      const res = await client<CheckpointSnapshot>({
        method: "get",
        url: `/api/v1/chats/${chatId}/checkpoints/${checkpointId}`,
      });
      return res.data;
    },
  });
}

export function CheckpointDiffView({
  chatId,
  leftCp,
  rightCp,
}: CheckpointDiffViewProps) {
  const left = useCheckpoint(chatId, leftCp);
  const right = useCheckpoint(chatId, rightCp);

  if (left.isLoading || right.isLoading) {
    return <p className="p-4 text-sm text-muted-foreground">Loading…</p>;
  }

  const diff = differ.diff(
    left.data?.values ?? {},
    right.data?.values ?? {},
  );

  return (
    <Viewer
      diff={diff}
      indent={2}
      lineNumbers
      highlightInlineDiff
      inlineDiffOptions={{ mode: "word" }}
    />
  );
}
