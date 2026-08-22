import type { KnownDataPartKind } from "@pathfinder/shared";

import { coreDataPartComponents } from "./coreDataParts";
import { strategyDataPartComponents } from "./strategyDataParts";
import type { DataPartComponentMap } from "./dataPartComponentMap";

// The one place the runtime map and a product map compose. A kind that no half
// covers fails to compile, because the merged object must be total over
// KnownDataPartKind. Unknown kinds are absent here and hit the fallback.
export const dataPartComponents: DataPartComponentMap<KnownDataPartKind> = {
  ...coreDataPartComponents,
  ...strategyDataPartComponents,
};
