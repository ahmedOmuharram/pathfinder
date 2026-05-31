import type { Step } from "@pathfinder/shared";
import { inferStepKind } from "@/lib/strategyGraph";
import { findParent, walkSubtreeIds } from "./utils";
import type { DeleteResolution, OperationChoice } from "./types";

export function computeDeleteChoices(
  steps: Step[],
  stepId: string,
): OperationChoice<DeleteResolution>[] {
  const target = steps.find((s) => s.id === stepId);
  if (!target) return [];

  if (steps.length === 1) {
    return [
      {
        resolution: "delete-strategy",
        title: "Delete strategy",
        description: "This is the only step. Removing it empties the strategy.",
        isDefault: true,
        willDelete: [stepId],
        willOrphan: [],
      },
    ];
  }

  const kind = inferStepKind(target);
  const parentInfo = findParent(steps, stepId);

  if (kind === "transform") {
    return [
      {
        resolution: "collapse-combine",
        title: "Delete this transform",
        description:
          "The step it consumed becomes the input of the next step downstream.",
        isDefault: true,
        willDelete: [stepId],
        willOrphan: [],
      },
    ];
  }

  if (parentInfo === null) {
    if (kind === "combine") {
      const secondarySubtree =
        target.secondaryInputStepId != null && target.secondaryInputStepId !== ""
          ? walkSubtreeIds(steps, target.secondaryInputStepId)
          : [];
      return [
        {
          resolution: "promote-primary",
          title: "Keep primary branch only",
          description:
            "Drop this combine and the secondary branch; the primary branch becomes the new root.",
          isDefault: true,
          willDelete: [stepId, ...secondarySubtree],
          willOrphan: [],
        },
        {
          resolution: "delete-strategy",
          title: "Delete entire strategy",
          description: "Remove every step.",
          isDefault: false,
          willDelete: steps.map((s) => s.id),
          willOrphan: [],
        },
      ];
    }
    return [
      {
        resolution: "delete-strategy",
        title: "Delete strategy",
        description: "Removing this leaf leaves no steps.",
        isDefault: true,
        willDelete: steps.map((s) => s.id),
        willOrphan: [],
      },
    ];
  }

  const { parent } = parentInfo;
  const parentKind = inferStepKind(parent);

  if (parentKind === "combine") {
    const siblingId =
      parentInfo.slot === "primary"
        ? parent.secondaryInputStepId
        : parent.primaryInputStepId;
    const subtreeIds = walkSubtreeIds(steps, stepId);
    const siblingSubtree =
      siblingId != null && siblingId !== "" ? walkSubtreeIds(steps, siblingId) : [];
    return [
      {
        resolution: "collapse-combine",
        title: "Delete and collapse",
        description:
          "Drop this branch and the combine; the other branch reconnects upward.",
        isDefault: true,
        willDelete: [...subtreeIds, parent.id],
        willOrphan: [],
      },
      {
        resolution: "orphan-sibling",
        title: "Delete only this branch",
        description:
          "Leave the combine and the other branch as orphan nodes (not pushed).",
        isDefault: false,
        willDelete: subtreeIds,
        willOrphan:
          siblingSubtree.length > 0 ? [parent.id, ...siblingSubtree] : [parent.id],
      },
      {
        resolution: "delete-subtree",
        title: "Delete this subtree",
        description:
          "Same as the first option for a leaf, but for a multi-step branch it removes everything below.",
        isDefault: false,
        willDelete: [...subtreeIds, parent.id],
        willOrphan: [],
      },
    ];
  }

  return [
    {
      resolution: "delete-subtree",
      title: "Delete this and the transform above it",
      description:
        "The transform consuming this step has no other input, so it is removed too.",
      isDefault: true,
      willDelete: [...walkSubtreeIds(steps, stepId), parent.id],
      willOrphan: [],
    },
  ];
}

export function isAmbiguousDelete(steps: Step[], stepId: string): boolean {
  return computeDeleteChoices(steps, stepId).length > 1;
}
