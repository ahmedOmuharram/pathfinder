import type { DataMessagePartComponent } from "@assistant-ui/react";
import type { KnownDataPartKind } from "@pathfinder/shared";
import { createElement } from "react";

import { USER_QUESTION_ANSWERS_PART_TYPE } from "../rail/consultActions";
import { DataPartRenderer } from "./DataPartRenderer";
import { noRender } from "./coreDataParts";
import { dataPartComponents } from "./contentComponents";

const DATA_PREFIX = "data-" as const;

const registry: Record<string, DataMessagePartComponent<unknown>> = {};
for (const kind of Object.keys(dataPartComponents)) {
  const kindTyped = kind as KnownDataPartKind;
  const shortName = kindTyped.startsWith(DATA_PREFIX)
    ? kindTyped.slice(DATA_PREFIX.length)
    : kindTyped;
  registry[shortName] = (({ data }: { data: unknown }) =>
    createElement(DataPartRenderer, {
      kind: kindTyped,
      data,
    })) as DataMessagePartComponent<unknown>;
}

// Parts that carry data for something other than a renderer: the carousel's
// answers travel back to the backend, and the strategy revision is read off the
// parts array by SupersededBadge.
const blank = noRender as DataMessagePartComponent<unknown>;
registry[USER_QUESTION_ANSWERS_PART_TYPE.slice(DATA_PREFIX.length)] = blank;
registry["strategy-revision"] = blank;

/** Data-part renderers keyed by the part name assistant-ui reports (no `data-` prefix). */
export const dataPartRenderers: Readonly<
  Record<string, DataMessagePartComponent<unknown>>
> = registry;
