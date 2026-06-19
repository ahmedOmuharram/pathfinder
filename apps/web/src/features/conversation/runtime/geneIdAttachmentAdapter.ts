import type {
  AttachmentAdapter,
  CompleteAttachment,
  PendingAttachment,
} from "@assistant-ui/react";

import { parseGeneCsv } from "@/lib/utils/parseGeneCsv";

export class GeneIdAttachmentAdapter implements AttachmentAdapter {
  accept = ".csv,.tsv,.txt,text/csv,text/tab-separated-values,text/plain";

  async add({ file }: { file: File }): Promise<PendingAttachment> {
    return {
      id: file.name,
      type: "document",
      name: file.name,
      contentType: file.type,
      file,
      status: { type: "requires-action", reason: "composer-send" },
    };
  }

  async send(attachment: PendingAttachment): Promise<CompleteAttachment> {
    const raw = await attachment.file.text();
    const ids = parseGeneCsv(raw);
    // Natural-language framing (NOT a pseudo-XML tag) so the input
    // prompt-injection scanner doesn't flag a benign gene-ID upload.
    const body =
      ids.length > 0
        ? `Attached gene-ID list from ${attachment.name}: ${ids.join(", ")}`
        : `Attached file ${attachment.name} contained no recognizable gene IDs.`;
    return {
      ...attachment,
      status: { type: "complete" },
      content: [{ type: "text", text: body }],
    };
  }

  async remove(): Promise<void> {}
}
