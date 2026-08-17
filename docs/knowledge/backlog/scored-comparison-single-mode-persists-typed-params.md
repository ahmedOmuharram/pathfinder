---
type: Backlog Item
title: Every scored variant fails at persist time because single-mode materialization hands typed ParamValues to WDKSearchConfig, and the UI then prints seven raw pydantic errors per variant
description: compare_variants_scored ran three variants; each evaluated, then failed with "7 validation errors for WDKSearchConfig parameters.channel Input should be a valid string [input_value=SinglePickValue(...)]". materialization.py builds the single-mode step with WDKSearchConfig.model_validate({"parameters": config.parameters}) while the tree path right above it uses encode_params. The Lead then fell back to an unscored comparison and told the user "no control set was available" although build_control_set had succeeded.
tags: [investigation, ui-run, experiments, scored-comparison, wdk-alignment, parameters]
generated: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# Investigation (UI run, 2026-08-17, PlasmoDB, conversation 4f69357c)

**What I did.** On the 5-step protease strategy: "Run an experiment comparing the Su et
al. gametocyte filter at three thresholds (top 20%, top 10%, top 5%) and tell me which
threshold best recovers these known gametocyte proteases as positives: PF3D7_1116700,
PF3D7_0507500, PF3D7_1245900. Use the rest of the strategy unchanged."

**What I got.** Transcript: Classify intent, Build control set (Completed), Get live
strategy state, Score variants (Completed), then a "Scored comparison / RANKED BY
SENSITIVITY" card with all three rows showing a dash and, per row, the full text
"failed: 7 validation errors for WDKSearchConfig parameters.channel Input should be a
valid string [type=string_type, input_value=SinglePickValue(type='sin...ary',
value='Channel 1'), input_type=SinglePickValue] For further information visit
https://errors.pydantic.dev/2.12/v/string_type parameters.any_or_all ..." (all seven
parameters of the Su step, three times). Then Compare variants (unscored): Top 20% 700,
Top 10% 294, Top 5% 115, pairwise Jaccard; then a consult_user question that says "This
comparison was unscored because no control set was available". The question the user
asked (which threshold recovers the three ids) was never answered.

**Why that is wrong.** The scored experiment is the one feature that answers a
sensitivity question with a number; it fails on every variant, shows the user a pydantic
dump, and the fallback misreports why. The user's three ids were never even checked
against the three sets, which is a trivial membership test.

**Why it happens.** `services/experiment/materialization.py` single-mode branch (the
`else` under `mode in ("multi-step", "import")`) calls
`WDKSearchConfig.model_validate({"parameters": config.parameters or {}})`;
`ExperimentConfig.parameters` is `dict[str, ParamValue]`, and `WDKSearchConfig.parameters`
is `dict[str, str]`. The tree branch four lines above encodes with `encode_params`. Since
`phase_evaluate` succeeds first (control_tests encodes correctly), the failure lands in
`phase_persist_strategy` and `run_experiment` raises `ValidationError` (a `ValueError`),
which `_score_one` stores as the variant's error. The Lead's fallback text ("no control
set") is written by the model, not from the tool result.

**Fix (to decide).** `search_config=WDKSearchConfig(parameters=encode_params(
config.parameters))` in the single-mode branch, plus a unit test that runs
`materialize` in single mode with typed values. The scored-comparison card should render a
short error, not the pydantic text. The Lead's fallback should say the scoring failed and
still answer membership of the given ids in each variant.

**What you would get.** Three scored rows with sensitivity over the three positives (and
a winner), or, if scoring fails, "scoring failed: <one line>" and a membership table.
