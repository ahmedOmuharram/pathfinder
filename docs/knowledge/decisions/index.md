# Decisions

Choices with a real alternative, where the reasoning is not recoverable from the code. Each names what was rejected and why.

## Knowledge bundle

- [Upstream is the falsifier](upstream-is-the-falsifier.md) - why WDK reference material is admitted to a bundle that bans reference material

## Strategy graph

- [The nested tree stays at the wire boundary](nested-tree-at-the-wire-boundary.md) - why R1 did not flatten persistence
- [Step status is derived, never stored](step-status-is-derived.md) - four states, not three, and no stored copy
- [A boolean operator is a type, not a string](boolean-operator-is-a-type.md) - one annotated type, so a bad operator is a 422
- [The local edit is the truth](local-edit-is-the-truth.md) - a WDK rejection is that step's problem, not the operation's
- [build_strategy is not revision-guarded](build-strategy-is-not-revision-guarded.md) - accepted exposure, with the reason

## Agents

- [A multi-pick slot takes a list](a-multi-pick-slot-takes-a-list.md) - a `dict[str, str]` signature became "the API rejected it"
- [An override list stays a list](an-override-list-stays-a-list.md) - encoding at the tool boundary made the whole array one candidate option
- [A dependent vocabulary is read under its parents](a-dependent-vocabulary-is-read-under-its-parents.md) - the model was shown HB3's time points for a criterion bound to 3D7
- [A contextualized param view is an enrichment, and it has one owner](contextualizing-params-is-an-enrichment.md) - six implementations, four exception types, two with no policy at all
- [One proposer, one validator](one-proposer-one-validator.md) - the model reads the whole parameter sheet and answers every parameter once; the rules that read English and the per-parameter resolvers are deleted
- [A small model reads the request; embeddings only shortlist](the-model-reads-the-request-not-a-cosine-score.md) - the 0.45 threshold decided 108 of 237 uncovered params, and picked a phosphofructokinase domain; amended, since the resolver it introduced never bound
- [The two species lists are the proposal; the profile pattern is derived](phyletic-lists-are-the-proposal.md) - the hidden LIKE pattern is computed from what the model proposes, because that grammar answers a wrong value with a count
- [A value the request already states is not a question](a-value-in-the-request-is-not-a-question.md) - polarity, vocabulary-less identifiers, and an EC wildcard the regex could not match
- [An unmatched accession stops the chain](unmatched-accession-stops-the-chain.md) - PF00069 became phosphofructokinase because a miss fell through to similarity
- [A number's initial value is a default, not an example](numeric-default-is-not-an-example.md) - the free-text guard swallowed five WDK-declared defaults
- [The strategy structure is a tree, because its shape is the science](structure-is-a-tree.md) - a left fold made `(B UNION C)` inexpressible and lost a gene
- [Chunk suppression follows the call, not a list of chunk types](suppression-follows-the-call-not-the-chunk-type.md) - the real cause of the recurring crash; the SDK threw on an orphan we emitted
- [Do not echo OpenAI item IDs back when you rewrite history](no-openai-item-ids.md) - the root cause of the tool-call-id crash on branch/revert/cancel/long loops
- [A retry must be something the model can act on](build-retry-must-be-actionable.md) - "call frame_problem first" looped when only the user could unblock
- [Eliding a tool result makes the agent fetch it again](elision-caused-refetching.md) - the context saver cost 12 duplicate calls in one turn
- [Prompts are checked against the architecture](prompts-match-the-architecture.md) - the base prompt named three schemas that do not exist
- [Strict state, and the checkpoints flushed to allow it](no-checkpoint-truncation.md) - a permissive `extra` was a shim for a shape nothing writes
- [A capability is not shipped until the model can find it](capability-must-be-reachable.md) - built, registered, and undiscoverable is not shipped
- [A sub-agent's approval is answered inside that sub-agent](sub-agent-approvals-re-enter-the-sub-agent.md) - the inner tool call is forwarded as its own approval card and the answer re-enters the suspended run

## Frontend

- [A parent term is a selection, so the tree expands it](parent-term-is-a-selection.md) - a correct organism scope rendered as "0 of 62 selected"

## Testing

- [Fixtures are built, not cast](fixtures-are-built-not-cast.md) - a cast also disables excess-property checks, which is how a deleted field survived

## Tooling

- [A silent anomaly must read the reply](silent-anomaly-must-read-the-reply.md) - the devtool judged prose handling without reading the prose
- [No faker or msw generation](no-faker-or-msw-generation.md) - reproduced, structural in the plugin, and it fights the real-data testing rule
- [One way to generate types](one-way-to-generate-types.md) - the duplicate codegen path was broken and was deleted, not fixed

## Transport

- [NUL is rejected at the ASGI boundary](nul-rejected-at-the-asgi-boundary.md) - why not a validator, and why not an exception handler
- [A VEuPathDB bearer token is the user; a service token is the application](bearer-identity-and-service-tokens.md) - the ES512 JWKS protocol, and why `proxied-user-id` cannot serve a service that acts as the user
- [A resource is owned by a user under one application](application-id-tenancy.md) - the scope key, isolated memories, a per-user cap with per-application attribution, and why not one user row or one database per application
- [A WDK-backed feature requires a registered VEuPathDB login](wdk-requires-registered-login.md) - one 401 code for the refusal, guest minting deleted, the service account confined to user-independent reads, and why not one shared identity for anonymous users
