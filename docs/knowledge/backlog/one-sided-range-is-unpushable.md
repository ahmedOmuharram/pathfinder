---
type: Backlog Item
title: A one-sided range serializes to a value WDK rejects
description: NumberRangeValue and DateRangeValue accept a single endpoint and to_wire omits the missing one, but WDK requires both min and max in the JSON object and rejects the parameter.
tags: [wdk-alignment, parameters, wire-format, integrations]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
status: stable
---

# The defect

`NumberRangeValue` and `DateRangeValue` in
`apps/api/src/pathfinder/domain/parameters/values.py` validate with
`_at_least_one_endpoint`, which requires **one** of `min` and `max`. `to_wire` then builds
the payload from whichever endpoints are present, so a range bound on one side serializes
to `{"min": 20.0}` or `{"max": 100.0}`.

WDK requires both. `NumberRangeParam.validateValue` calls `getDouble("min")` and
`getDouble("max")` on the parsed object and turns the resulting `JSONException` into an
invalid-parameter error; `DateRangeParam.validateValue` does the same with `getString`.
Detail and the pinned citations are in
[WDK-PARAM-005](../wdk/rules/parameters-and-vocabularies.md).

# Confirmed live, on both sites, 2026-08-10

Against `GenesByIntronJunctions.percent_max` on plasmodb.org and toxodb.org, through the
anonymous revise endpoint `POST /record-types/transcript/searches/{name}`:

| Value sent | Result |
|---|---|
| `{"min":"20","max":"100"}` | valid |
| `{"min":20,"max":100}` | valid - the JSON values may be strings or numbers |
| `{"min":"20"}` | invalid: `'{"min":"20"}' must be is the format {"min":<min value>,"max":<max value>}` |
| `{"max":"100"}` | invalid, same message |

`{"min":"2025-01-01"}` against `metrics/Awstats.date` fails the same way on both sites.

# Why the existing tests do not catch it

`tests/unit/domain/parameters/test_value_round_trip.py::test_number_range_including_negative_bounds`
generates one-sided ranges on purpose (`assume(low is not None or high is not None)`) and
asserts they round-trip. They do - through PathFinder's own encoder and decoder. The test
is a self-consistency property, not a WDK conformance check, so it passes on a value WDK
will not take.

# Blast radius

Loud rather than silent: WDK reports the parameter invalid, so a step built this way does
not run and does not produce a wrong gene count. What it produces is a build failure whose
message points at the range parameter without saying that the *missing* endpoint is the
problem, which is a plausible way for an agent to conclude the search cannot express the
criterion and drop it.

Ranked below the two items above it for that reason.

# How to confirm

Unit level, no live WDK: assert that `NumberRangeValue(min=20).to_wire()` produces an
object with both keys, or that constructing it fails. Live confirmation is the table above
and needs no credential.

# Where to look

`NumberRangeValue`, `DateRangeValue` and `from_decoded` in
`domain/parameters/values.py`. The decision to make is which end of the range a one-sided
bound should be paired with. There is a real answer available: the parameter spec carries
`min`/`max` (numeric) or `minDate`/`maxDate` (date) bounds, so an open end can be filled
from the parameter's own declared limit rather than invented. That keeps the model's
ability to express "at least 20" while sending WDK something it accepts.

Check the callers before changing the validator - `param_value_from_raw` and
`from_decoded` both construct these, and the canonicalizer path in
`domain/parameters/canonicalize.py` may already be normalizing some cases.

# Anchor

`_at_least_one_endpoint` and `to_wire` on `NumberRangeValue` in
`domain/parameters/values.py`. Done when a one-sided range either fails at construction or
serializes with both keys, and a test asserts the wire form against the WDK requirement
rather than against PathFinder's own decoder.
