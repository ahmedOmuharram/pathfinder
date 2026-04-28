export { applyOperation } from "./apply";
export type {
  ApplyResult,
  AttachPoint,
  DeleteEdgeResolution,
  DeleteResolution,
  GraphOperation,
  OperationChoice,
} from "./types";
export { computeDeleteChoices, isAmbiguousDelete } from "./deleteResolutions";
export {
  buildIndex,
  findParent,
  getRootIds,
  isReachableFromAnyRoot,
  subtreeSize,
  walkSubtreeIds,
} from "./utils";
export type { GraphIndex } from "./utils";
