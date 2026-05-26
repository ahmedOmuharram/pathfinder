import type { DataConversationTitlePayload } from "@pathfinder/shared";

export function DataConversationTitle({
  data,
}: {
  data: DataConversationTitlePayload;
}) {
  return (
    <div
      data-testid="data-conversation-title"
      className="my-1 text-xs text-muted-foreground"
    >
      <span className="italic">Title set: {data.title}</span>
    </div>
  );
}
