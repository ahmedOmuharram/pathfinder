---
type: Reference
title: Validation, and the four different things a missing number means
description: The validation bundle and its levels, why validity is a claim about a level rather than about a step, how invalidity reaches a consumer, and the difference between a result of zero, a step nobody has run, an invalid step and a lost identity.
tags: [wdk-alignment, validation, estimated-size, steps, strategies, model]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
status: stable
---

Every permalink below is pinned to the sha recorded in [sources.md](../sources.md).

# A validation bundle is two fields, and sometimes a third

Every WDK object that can be wrong carries the same small object.
[`ValidationFormatter.getValidationBundleJson`](https://github.com/VEuPathDB/WDK/blob/e534d2e6a5119165e1742c7a9e07a371217ddda5/Service/src/main/java/org/gusdb/wdk/service/formatter/ValidationFormatter.java#L10-L22)
writes `level` and `isValid` always, and adds `errors` **only when `isValid` is
false**. `errors` is `{general: [string], byKey: {paramName: [string]}}`:
`general` for what is wrong with the object, `byKey` for what is wrong with a
named parameter.

[The service's own JSON schema](https://github.com/VEuPathDB/WDK/blob/e534d2e6a5119165e1742c7a9e07a371217ddda5/Service/doc/schema/wdk/includes/validation-bundle.json#L5-L47)
agrees: `required` is `["level", "isValid"]` and `errors` is optional.

Two silences hide in that shape.

**An absent `errors` is not "no errors were found".** It is "this object is
valid", which is a claim about a level, and the level is the other field.

**A present `errors` is not "errors were found" either.** The object is written
whenever `isValid` is false, and both of its members can be empty. That is not
hypothetical; it is what the deployment returns at the lowest level, below.

# Five levels on the schema, six on the wire

The schema enumerates `NONE`, `UNSPECIFIED`, `SYNTACTIC`, `SEMANTIC`,
`RUNNABLE`. They are ordered, and each is a strictly stronger question:

| Level | What has been checked |
|---|---|
| `NONE` | nothing. The object was built without validating it at all. |
| `UNSPECIFIED` | not a level a build requests. It is the synthetic level stamped on an error body - see below. |
| `SYNTACTIC` | each value has the right shape for its parameter type |
| `SEMANTIC` | each value is a legal value: in the vocabulary, inside the bounds, non-empty when required |
| `RUNNABLE` | the step can actually be executed: its inputs resolve, they are of an accepted record type, and they are themselves runnable |

**There is a sixth, `DISPLAYABLE`, and it is live.** It sits between `SEMANTIC`
and `RUNNABLE` and it is what the step-analysis form endpoint validates at:
[`getStepAnalysisTypeDataFromName`](https://github.com/VEuPathDB/WDK/blob/e534d2e6a5119165e1742c7a9e07a371217ddda5/Service/src/main/java/org/gusdb/wdk/service/service/user/StepAnalysisFormService.java#L108-L130)
builds the form spec at `ValidationLevel.DISPLAYABLE` and hands the resulting
bundle straight to the formatter. On 2026-08-10 both plasmodb.org and
toxodb.org returned `{"level": "DISPLAYABLE", "isValid": true}` from
`GET .../steps/{id}/analysis-types/word-enrichment` and from
`GET .../steps/{id}/analyses/{id}`.

So the schema include is not a complete enumeration of what the platform emits,
and a client that validates a validation bundle against it rejects a legitimate
response. WDK does exactly that to itself
([WDK-VALID-007](../rules/validation.md)).

# `isValid: false` at level `NONE` means nobody looked

This is the single most misreadable field in the API.

`GET /users/{id}/steps/{stepId}` takes a `validationLevel` query parameter and
[defaults it to `RUNNABLE`](https://github.com/VEuPathDB/WDK/blob/e534d2e6a5119165e1742c7a9e07a371217ddda5/Service/src/main/java/org/gusdb/wdk/service/service/user/StepService.java#L116-L129).
Asking the same step at each level on plasmodb.org and toxodb.org on
2026-08-10, against a step that is correct by every other measure:

| `validationLevel` | Response |
|---|---|
| `NONE` | `{"level":"NONE","isValid":false,"errors":{"general":[],"byKey":{}}}` |
| `SYNTACTIC` | `{"level":"SYNTACTIC","isValid":true}` |
| `SEMANTIC` | `{"level":"SEMANTIC","isValid":true}` |
| `RUNNABLE` | `{"level":"RUNNABLE","isValid":true}` |
| `DISPLAYABLE` | **HTTP 500** - WDK's own out-schema rejects the body it just built |
| anything else | silently 200 at `RUNNABLE` |

The first row is the whole point. **A `NONE` bundle reports `isValid: false`
with an empty error list, because "not validated" is not "valid".** A client
that reads `isValid` without reading `level` calls a perfectly good step broken,
and it will do so on exactly the paths that build at `NONE` - which includes
`PUT .../strategies/{id}/step-tree`, the write PathFinder uses for every
structural edit ([WDK-STRAT-005](../rules/strategies-and-steps.md)).

The last row is the other trap: an unrecognised level string is not a 400. The
service parses it inside `defaultOnException`, so a typo silently answers a
different question from the one asked.

# Every endpoint picks its own level, and no strategy endpoint picks `RUNNABLE`

Validity is not a property of a step. It is a property of a step *and a level*,
and the level is chosen by whichever endpoint you happened to call.

| Endpoint | Built at | What the response carries |
|---|---|---|
| `GET .../steps/{id}` | `RUNNABLE` by default, caller may override | full `validation` bundle |
| `GET .../strategies` | [`SYNTACTIC`, with `FILL_PARAM_IF_MISSING`](https://github.com/VEuPathDB/WDK/blob/e534d2e6a5119165e1742c7a9e07a371217ddda5/Service/src/main/java/org/gusdb/wdk/service/service/user/StrategyService.java#L80-L95) | `isValid` only. No `validation` object. |
| `GET .../strategies/{id}` | [`RUNNABLE`, then rebuilt at `SEMANTIC` and *that* is what gets formatted](https://github.com/VEuPathDB/WDK/blob/e534d2e6a5119165e1742c7a9e07a371217ddda5/Service/src/main/java/org/gusdb/wdk/service/service/user/StrategyService.java#L149-L170) | `isValid` on the strategy, a full bundle per step, all at `SEMANTIC` |
| `POST .../steps`, `PUT .../search-config` | `SEMANTIC` | on failure, a bundle as the 422 body |
| `POST .../analyses` | `RUNNABLE` with `NO_FILL` | on failure, a bundle as the 422 body |

Two consequences worth stating plainly.

**The strategy detail never carries a `validation` object.**
[`getDetailedStrategyJson`](https://github.com/VEuPathDB/WDK/blob/e534d2e6a5119165e1742c7a9e07a371217ddda5/Service/src/main/java/org/gusdb/wdk/service/formatter/StrategyFormatter.java#L56-L67)
calls the listing formatter with `includeValidationObject` false - its comment
says "individual steps will contain validation" - and
[a null there means org.json drops the key](https://github.com/VEuPathDB/WDK/blob/e534d2e6a5119165e1742c7a9e07a371217ddda5/Service/src/main/java/org/gusdb/wdk/service/formatter/StrategyFormatter.java#L44-L53).
Confirmed on both sites: the detail has `isValid` and no `validation`. A client
that defaults the missing object to "valid at level NONE" has invented a claim
in the one place WDK deliberately made none.

**No strategy endpoint answers "will this run".** The list answers `SYNTACTIC`
after filling in whatever was missing; the detail answers `SEMANTIC`. The
`RUNNABLE` build that `getStrategy` does first is used for its side effect -
refreshing result sizes - and then thrown away. If you need to know whether a
strategy runs, run it.

# A strategy is invalid when any step in it is invalid

The strategy's bundle is not the root step's bundle. The constructor
[aggregates the status of every step in the map](https://github.com/VEuPathDB/WDK/blob/e534d2e6a5119165e1742c7a9e07a371217ddda5/Model/src/main/java/org/gusdb/wdk/model/user/Strategy.java#L263-L269),
and the map is every step in the tree, so one broken leaf five levels down makes
the whole strategy `isValid: false` while the root step's own bundle may be
fine.

Structural problems are not validation at all. A step assigned to the strategy
but absent from its tree, a step owned by another user, a step belonging to a
different strategy: each throws `InvalidStrategyStructureException` during
construction rather than producing an invalid bundle. Structure is a
precondition of having a strategy to validate.

# Invalidity reaches a consumer only at `RUNNABLE`

An `input-step` parameter is where a step learns about its inputs, and
[`AnswerParam.validateValue`](https://github.com/VEuPathDB/WDK/blob/e534d2e6a5119165e1742c7a9e07a371217ddda5/Model/src/main/java/org/gusdb/wdk/model/query/param/AnswerParam.java#L110-L159)
does two completely different jobs depending on the level it is called at.

Below `RUNNABLE` it checks that the value is an integer or the empty string, and
returns valid. It does not look the step up. It cannot: nothing below
`RUNNABLE` is required to have resolved the container.

At `RUNNABLE` it resolves the id in the step container and fails four ways -
the id is not in the container, the referenced step has no valid search, the
referenced step's record class is not one this parameter accepts, or the
referenced step is itself not runnable. The last is the propagation, and the
message it produces embeds the input's entire bundle:

```
The step referenced by ID '440085953' is not runnable because: <that step's whole validation bundle>
```

So a consumer's `byKey` entry for its answer parameter can contain a
pretty-printed JSON document rather than a sentence. Parse the consumer's own
errors; do not try to read the nested one out of a string.

The empty-string case has a deliberate exemption and it explains a result that
otherwise looks like a bug.
[`Param.validate`](https://github.com/VEuPathDB/WDK/blob/e534d2e6a5119165e1742c7a9e07a371217ddda5/Model/src/main/java/org/gusdb/wdk/model/query/param/Param.java#L574-L590)
short-circuits an empty value to valid when the parameter allows empty, and
[`AnswerParam.isAllowEmpty` returns true](https://github.com/VEuPathDB/WDK/blob/e534d2e6a5119165e1742c7a9e07a371217ddda5/Model/src/main/java/org/gusdb/wdk/model/query/param/AnswerParam.java#L192-L205)
precisely so that a combined step can exist before it is wired. Live on both
sites, an unwired combined step therefore reports `isValid: true` at `RUNNABLE`
- and it is telling the truth about the only thing it was asked.

The invariant that keeps that from being a hole is enforced outside validation:
[the `Step` constructor throws](https://github.com/VEuPathDB/WDK/blob/e534d2e6a5119165e1742c7a9e07a371217ddda5/Model/src/main/java/org/gusdb/wdk/model/user/Step.java#L392-L402)
if a step has a strategy and a null answer parameter, or has no strategy and a
non-null one. That is a `WdkModelException` - a 500 - not a validation error.

# You cannot make an invalid step through the REST API

Every write path validates before it stores, and each returns the failure as a
validation bundle in the 422 body. Measured on plasmodb.org on 2026-08-10:

| Request | Status | Body |
|---|---|---|
| `POST .../steps` with an unknown vocabulary term | 422 | `{"level":"SEMANTIC","isValid":false,"errors":{"general":[],"byKey":{"organism":["Number of selected values (0) is not allowed..."]}}}` |
| `POST .../steps` omitting two required parameters | 422 | `byKey` naming both, each `Cannot be empty.` |
| `PUT .../steps/{id}/search-config` with an unknown term | 422 | same shape, level `SEMANTIC` |
| `POST .../steps/{id}/reports/standard` on a step not in a strategy | 422 | `{"level":"UNSPECIFIED","isValid":false,"errors":{"general":["Step 440085953 is not part of a strategy, so cannot run."],"byKey":{}}}` |

The last row is the other producer of a bundle:
[the single-message overload](https://github.com/VEuPathDB/WDK/blob/e534d2e6a5119165e1742c7a9e07a371217ddda5/Service/src/main/java/org/gusdb/wdk/service/formatter/ValidationFormatter.java#L24-L31)
hard-codes `"UNSPECIFIED"` for an error that never came from a real validation
run. **`UNSPECIFIED` is therefore a reliable marker that the message is prose
rather than a parameter verdict**, and it never appears on a resource's own
`validation` field.

The practical conclusion is that a step in WDK becomes invalid because the
*model* changed underneath it - a search retired, a vocabulary term withdrawn,
a record class renamed - and not because a client wrote something bad. That is
why invalid steps show up on old saved strategies and almost never on new ones,
and it is why PathFinder treats a WDK rejection as that step's problem rather
than as a failure of the operation
([local-edit-is-the-truth](../../decisions/local-edit-is-the-truth.md)).

PathFinder derives its own four-state step status rather than storing one, for
the same reason WDK recomputes a bundle on every read
([step-status-is-derived](../../decisions/step-status-is-derived.md)).

# The four different things a missing number means

`estimatedSize` is where all of this becomes a number a scientist reads, and it
has four distinguishable states that are easy to collapse into one.

[`Step.getEstimatedSize`](https://github.com/VEuPathDB/WDK/blob/e534d2e6a5119165e1742c7a9e07a371217ddda5/Model/src/main/java/org/gusdb/wdk/model/user/Step.java#L490-L500)
returns the stored size when the answer spec is valid and **-1** when it is not.
Its own javadoc says it returns 0 in that case. The javadoc is wrong; the code
is the contract. Then
[`translateEstimatedSize`](https://github.com/VEuPathDB/WDK/blob/e534d2e6a5119165e1742c7a9e07a371217ddda5/Service/src/main/java/org/gusdb/wdk/service/formatter/StepFormatter.java#L106-L121)
maps any negative to null on the way out, and its comment records what that
does: "returning null here means the actuall property will be omitted due to
JSONObject's API", typo included. So on a step, -1 is never seen - it is an
absent key.

The strategy does not get that treatment.
[`getDetailedStrategyJson`](https://github.com/VEuPathDB/WDK/blob/e534d2e6a5119165e1742c7a9e07a371217ddda5/Service/src/main/java/org/gusdb/wdk/service/formatter/StrategyFormatter.java#L56-L67)
overwrites the key with `strategy.getResultSize()` and does not pass it through
the translator, and
[`Strategy.getResultSize`](https://github.com/VEuPathDB/WDK/blob/e534d2e6a5119165e1742c7a9e07a371217ddda5/Model/src/main/java/org/gusdb/wdk/model/user/Strategy.java#L519-L527)
delegates to
[`Step.getResultSize`](https://github.com/VEuPathDB/WDK/blob/e534d2e6a5119165e1742c7a9e07a371217ddda5/Model/src/main/java/org/gusdb/wdk/model/user/Step.java#L502-L513),
which returns -1 for a spec that is not runnable. The object being formatted is
the `SEMANTIC` rebuild, which is not runnable by construction. **So the strategy
detail's top-level `estimatedSize` is -1 for a perfectly valid strategy.**

Measured on both sites on 2026-08-10, one step per strategy, in this order:

| Call | plasmodb.org | toxodb.org |
|---|---|---|
| `GET .../steps/{id}` before any strategy read | `estimatedSize` **absent** | absent |
| `GET .../strategies/{id}` | top-level **-1**, step entry **3392** | top-level **-1**, step entry **3717** |
| `GET .../steps/{id}` again | **3392** | **3717** |
| `GET .../strategies` | **3392** | **3717** |

The ordering is the mechanism, and it resolves what looks like a contradiction
in [filters](filters.md), where a step read directly had no `estimatedSize`
while its strategy reported one for the same step. The step's size is absent
until something computes it, and the thing that computes it is the strategy
read:
[`updateStaleResultSizesOnRunnableSteps`](https://github.com/VEuPathDB/WDK/blob/e534d2e6a5119165e1742c7a9e07a371217ddda5/Model/src/main/java/org/gusdb/wdk/model/user/Strategy.java#L558-L581)
runs on every `GET .../strategies/{id}`, refreshes each runnable step and writes
the number to the database, which is why the third row differs from the first.

So the four states, and what each one is:

| On the wire | Means | Not |
|---|---|---|
| `estimatedSize: 0` | **a real result of zero records** | anything wrong |
| `estimatedSize` absent, on a step | nobody has run this step yet, or it is invalid at the level you asked | zero |
| `estimatedSize: -1`, on a strategy detail | the formatter was handed a non-runnable copy | a count, a negative count, or an error |
| `[]` from `GET .../strategies` | possibly a lost identity, since a fresh guest owns nothing | an empty workspace |

The fourth is the one that does not look like it belongs on this list, and it is
the reason the list exists. A client that has lost its `Authorization` cookie is
a brand-new guest on every request ([WDK-AUTH-001](../rules/auth-and-transport.md)),
and a brand-new guest gets a 200 and an empty array. Measured on plasmodb.org on
2026-08-10: a second guest listing strategies got `200 []`, reading the first
guest's step by concrete id got **403**, and reading it through
`/users/current/steps/{id}` got **404** - which is the argument for concrete ids
in [users, auth and sessions](users-auth-and-sessions.md) arriving from a third
direction.

Collapsing these is how a genuine scientific negative and a bug become
indistinguishable to the person reading the screen
([WDK-VALID-005](../rules/validation.md)). The identity half is in
[transport-quirks](../rest/transport-quirks.md), which also records that the
long-held `JSESSIONID` silent-zero belief did not reproduce.
