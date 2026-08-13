---
type: Backlog Item
title: The applied-analyses list is always empty, and the emptiness is swallowed
description: WDK's analysis instance list carries two fields per entry. PathFinder validates each entry against a model requiring four, so every entry is dropped by a deliberate per-item suppress and the call returns an empty list rather than raising - the diagnostic reports "no analyses" for a step that has them.
tags: [wdk-alignment, integrations, step-analyses, observability]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
status: stable
---

# The defect

`list_step_analyses` in
`apps/api/src/pathfinder/integrations/veupathdb/_analyses.py` validates the
response through `_validate_list(raw, _ANALYSIS_CONFIG_ADAPTER)`, where the
adapter is `TypeAdapter(WDKStepAnalysisConfig)`. That model requires
`analysis_id`, `step_id` and `analysis_name`, none of which carry a default.

WDK sends two fields. The upstream behavior and its pinned citation are
[WDK-VALID-010](../wdk/rules/validation.md): `instanceSummaryJson` emits
`analysisId` and `displayName` and stops. Measured on both verification sites,
`GET .../steps/{id}/analyses` returns
`[{"displayName":"Word Enrichment","analysisId":203635253}]`.

So `step_id` and `analysis_name` are missing on every entry and every entry
raises `ValidationError`.

# What the swallow means

`_validate_list` in `integrations/veupathdb/_helpers.py` wraps each item in
`contextlib.suppress(ValidationError)`, and that is deliberate and reasonable in
general - its docstring says one bad WDK entry should not take down a whole
list. Here every entry is a bad entry, so the suppression is total: the
`ValidationError` never surfaces, no exception is raised, and the method returns
`[]`.

That is the point of this item, and it is worth being blunt about. **The feature
does not fail; it silently does nothing.** A raise would have been noticed
within a day of the first call. An empty list is a plausible answer - a step
genuinely can have no analyses - so nothing about the return value says the code
is broken, and nothing ever will. It has presumably been wrong since it was
written.

# What a researcher actually sees

Nothing, which is why this is ranked last of the three items filed from this
work.

The only caller is `_log_analysis_failure` in
`integrations/veupathdb/strategy_api/analyses.py`, which runs when an analysis
has exhausted its retries and exists purely to put context in the log. It logs
`analyses=[]`. So the cost is not a wrong number in front of a scientist; it is
that the diagnostic written to explain a failed enrichment reports "this step
has no analyses" for a step that has one, and reports it at exactly the moment
someone is reading the log to find out what happened.

Note the interaction with the `try/except Exception` around that call. The
`except` is not what hides this - nothing raises for it to catch. It would have
hidden a raise had the models matched more closely, and it is worth removing or
narrowing on the same pass for that reason, but it is not the cause here.

`list_step_analyses` is also the natural building block for anything that shows
a researcher which analyses have already been run on a step - re-attaching a
previous enrichment, avoiding a duplicate run. Nothing does that today, and
whoever builds it will inherit a method that always says "none".

# How to confirm

No live WDK needed. One call, no transport stub required:

```python
_validate_list(
    [{"displayName": "Word Enrichment", "analysisId": 203635253}],
    TypeAdapter(WDKStepAnalysisConfig),
)
```

returns `[]` today. The live shape it is built from is recorded in
[WDK-VALID-010](../wdk/rules/validation.md) and was confirmed on both sites on
2026-08-10; re-confirming it needs only a guest session, a step in a strategy,
one created analysis instance, and a `GET` of the list.

# Where to look, and the shape of the fix

`list_step_analyses` in `integrations/veupathdb/_analyses.py`. Three things the
fix should get right:

- **Model what the endpoint actually returns.** A separate two-field summary
  model - `analysisId`, `displayName` - is the honest representation.
  `WDKStepAnalysisConfig` is the shape of `GET .../analyses/{analysisId}` and
  should keep being exactly that.
- **Decide whether callers need the full instance.** If they do, the list gives
  ids and the detail must be fetched per id; that is a real N+1 and should be a
  conscious choice rather than something a model accidentally implied.
- **Consider whether a whole-list wipeout should stay silent.** `_validate_list`
  dropping one entry of twenty is the behavior it was designed for. Dropping
  twenty of twenty is a schema mismatch wearing the same clothes, and it is the
  reason this went unnoticed. A log line when every item fails would have caught
  it and would catch the next one.

Per the repo's TDD rule the failing test comes first.

# Anchor

`list_step_analyses` in `integrations/veupathdb/_analyses.py`. Done when the
list validates against a model matching the two fields WDK sends, a test asserts
a real entry survives validation, and
[WDK-VALID-010](../wdk/rules/validation.md) can be moved off `UNENFORCED`.
