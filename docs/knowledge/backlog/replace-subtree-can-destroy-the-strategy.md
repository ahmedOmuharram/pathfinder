---
type: Backlog
---

# replace_subtree let a recovery pass halve a correct strategy

**What I did.** Built the nine-criterion kinase strategy on 2026-09-01
(conversation `ffdf8ab2-9485-40c6-80de-744e6829360f`). The build pushed a
correct 16-step tree: three UNION branches (two kinase pairs, and mass
spectrometry with DeRisi expression) intersected with the ortholog map, the
phylogenetic profile and the SNP filter. Recovery then ran.

**What I got.** From the event log, in order:

    replace_subtree | 8 validation errors: ... new_subtree.primaryInput.
                      primaryInput.parameters.type ...
    apply_operations | REJECTED: promote-primary on non-combine. Nothing was
                      applied and the strategy is unchanged ...
    replace_subtree | Replaced step_7af21640, 8 steps

"Strategy updated: 16 steps" became "Strategy updated: 8 steps", and the
graph panel now shows four rows named `__input_step__` under three
Intersects. Every kinase union is gone.

**Why that's wrong.** A researcher watched a correct strategy become a
different, smaller one with placeholder-named steps. Two guards caught two
malformed attempts and the third attempt destroyed the tree, so the
protection is arbitrary rather than structural. The spec still states nine
criteria; the tree holds four placeholder leaves.

**Why it happens.** `replace_subtree`
(ai/tools/standalone/strategy_edits.py, execution toolset) applies a
`ReplaceSubtreeOp` after checking only that `step_id` exists. Nothing
compares the resulting tree against the criteria the spec states. The edit
path has exactly this check
(`_refuse_a_shape_the_edit_did_not_state` in
domain/strategy/spec_to_operations.py: the leaf set must equal the spec's
criteria, nothing adopted, nothing stranded); the recovery path has none.
The literal name `__input_step__` reaching the graph also shows a
placeholder from the model's payload was accepted as a real step.

**Fix.** Hold every subtree write to the same invariant the edit path holds:
after the operation, the non-combine leaf set must equal the criteria the
spec states, nothing may be stranded, and no step may carry a placeholder
name. A violation is a `ModelRetry` naming the criteria that would be lost,
not a committed write. The check belongs beside the existing refusal so
there is one implementation and two call sites.

**What you'd get.** The same recovery attempt is refused with "this would
drop the four kinase criteria", the 16-step tree stays intact, and
`__input_step__` never names a step a user can see.
