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
- [Enrichment of a gene list runs WDK's plugin, and the background is an organism](enrichment-by-value-runs-the-wdk-plugin.md) - the in-process exact hypergeometric was rejected because the annotated background lives in the site database, and a caller-supplied background list because the plugin refuses an organism its result does not contain
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
- [The checkpoint allowlist binds at construction](the-checkpoint-allowlist-binds-at-construction.md) - `with_msgpack_allowlist` discarded every declaration, so a state read warned on types that were on the list
- [A capability is not shipped until the model can find it](capability-must-be-reachable.md) - built, registered, and undiscoverable is not shipped
- [A sub-agent's approval is answered inside that sub-agent](sub-agent-approvals-re-enter-the-sub-agent.md) - the inner tool call is forwarded as its own approval card and the answer re-enters the suspended run
- [Every agent belongs to the turn that runs it](the-agent-belongs-to-the-turn.md) - the module singletons shared one `override`, and worker concurrency is about to rise

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
- [A write the caller reads back commits before its response](a-write-commits-before-its-response.md) - the session dependency commits after the response, and an in-process transport cannot see the race
- [The API rewrite carries a long call](the-api-rewrite-carries-a-long-call.md) - Next's 30 s rewrite cap answered the data purge with its own bare 500
- [A VEuPathDB bearer token is the user; a service token is the application](bearer-identity-and-service-tokens.md) - the ES512 JWKS protocol, and why `proxied-user-id` cannot serve a service that acts as the user
- [A resource is owned by a user under one application](application-id-tenancy.md) - the scope key, isolated memories, a per-user cap with per-application attribution, and why not one user row or one database per application
- [A conversation is a thread; its strategy is an attachment](conversation-thread-and-strategy-split.md) - the column partition, absent-row semantics, one eager loader, and why a nullable column is not an attachment
- [Part kinds keep their names when the taxonomy opens](part-kinds-keep-their-names.md) - the kind is persisted in every stored chunk, so namespacing waits for the assistant that needs it
- [The runtime takes the vocabulary as an argument; the wire keeps it](vocabulary-is-an-argument.md) - roles, guard tool sets and memory kinds became arguments; the published enums stay narrow until a client needs them open
- [The assistant runtime is a package boundary, not a contract over scattered modules](assistant-core-is-a-package-boundary.md) - superseded; the modules moved into `assistant_core/` and contract 7 rejected indirect chains too, because a config-only boundary has to be rediscovered on every extraction
- [The runtime is a package, so the boundary is an installation fact](the-runtime-is-a-package.md) - `packages/assistant-core` with its own pyproject, lock, tests and lane; contract 7 became a dependency list, the thread moved with it, and in-repo contracts only were rejected
- [The runtime's part payloads live in the runtime, so the package builds alone](runtime-part-payloads-live-in-the-runtime.md) - the durable-task payloads and `TurnUsage` moved out of `pathfinder-shared` and the dependency is gone; publishing `pathfinder-shared` as a second distribution was rejected because it has no second consumer, and the registry left `__init__.py` because a package that imports on load cannot hold a module its own importers need
- [The wire protocol is a written spec, verified against captured frames](the-wire-protocol-is-a-written-spec.md) - `PROTOCOL.md` states the rules a client must follow and a package test owns its facts; generating the page from the models was rejected because a generator has nowhere to put a rule
- [A staged eval case carries its user until promotion, and a promoted case carries nobody](a-staged-eval-case-carries-its-user-until-promotion.md) - the linkage has a lifetime and a check constraint enforces it; storing nothing was rejected because an opt-out could clear nothing, keeping it after promotion because the corpus is what ships
- [The eval harness is pydantic-evals, and the summary shape is ours](the-eval-harness-is-pydantic-evals.md) - the dataset, the case loop and the evaluator protocol come from the library; the SLI feed does not, and a graded tree distance waits for a corpus that needs one
- [The orchestration belongs to the assistant, not to the platform](the-orchestration-is-the-assistants.md) - `AssistantSpec` carries the graph factory, state, parts, kinds, mock and identity gate; one platform graph parameterized by config was rejected because a config-shaped Lead is still a Lead
- [The admitted tool sources are installed by the host](admitted-tool-sources-are-installed-by-the-host.md) - a module-level seam the host calls at start; a turn-seam parameter was rejected because a request must have no channel to name a server, and `RuntimeSettings` because a dropped env var would admit nothing in silence
- [A tool source's session belongs to the turn](a-tool-source-session-belongs-to-the-turn.md) - `ResolvedToolSources` opens and closes every declared source around the whole drive; the assistant's graph owning the entry was rejected because a graph that raises leaks the session, and the library's per-run entry because a turn with several agent runs would open a connection per run
- [The client package has three rings, and the innermost one has no dependencies](the-client-is-a-package-with-three-rings.md) - a dependency-free protocol core, one AI-SDK-coupled transport, and a named legacy module for the task dialect; one SDK-importing module was rejected because a non-SDK host would inherit it to parse a frame
- [A durable task reports itself on the thread, coarsely, and the per-task channel is deprecated](durable-task-progress-belongs-in-the-thread-log.md) - progress and completion join the log with the same cursor as every other chunk; a second dialect forever, every tick, and deleting the route were all rejected, each for a different reason
- [A WDK-backed feature requires a registered VEuPathDB login](wdk-requires-registered-login.md) - one 401 code for the refusal, guest minting deleted, the service account confined to user-independent reads, and why not one shared identity for anonymous users
- [The MCP server verifies with the API's own bearer verifier, and publishes RFC 9728](mcp-auth-reuses-the-api-verifier.md) - three credential modes, a separate service-token registry, and the SDK's protected-resource document; a second JWKS client and an inbound `VEUPATHDB_AUTH_TOKEN` were rejected
- [The wdk-mcp server is a product module of the api, served from the api image](the-wdk-mcp-server-is-a-product-module.md) - `pathfinder/mcp/` calls the services and the import contract holds the line; a standalone package, a mount inside the FastAPI app, and exporting the `ai/tools` wrappers were rejected, and a tool that cannot fit 60 seconds declares its own floor in `_meta`
- [The conformance suite is a distribution of its own, and a skipped check is not a pass](the-conformance-suite-is-a-separate-distribution.md) - `veupathdb-mcp-conformance` ships its six families inside a pytest plugin that imports nothing of this deployment; the api test tree, `assistant-core` and a container-only artifact were rejected, and the account-state extension point is a pytest hook because a fixture cannot be overridden from outside an installed package
- [The memory ceilings bound the worker and wdk-mcp, and leave the api uncapped](the-memory-ceilings-bound-the-growers-not-the-api.md) - 2g each on the two processes whose memory grows with sites touched, measured against the api's 6.54 GiB idle-warm; a 3g wdk-mcp ceiling was rejected after it let the kernel OOM-kill the api, and no api ceiling both fits the VM and clears its peak
- [Our own admission record reads incomplete, because one account cannot prove isolation](our-own-admission-record-reads-incomplete.md) - the registered account is the first credential and the service token the second, so the leak rule covers both; making the service token the owning identity would settle isolation and was rejected because every other check would then run as a credential WDK refuses
