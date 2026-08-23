# The assistant runtime wire protocol

**Version 1.0.0.** This document specifies the bytes a client reads from an
assistant built on `assistant_core`. It is written so a consumer in any
language can implement a client from this page alone, with no reference to the
JavaScript SDK that inspired the chunk vocabulary.

The key words MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are to be interpreted
as described in RFC 2119.

Every example below is captured from a real turn by
`tests/integration/conversation/test_protocol_document.py`, which fails when
the runtime's output and this page disagree. Generated identifiers read as
`00000000-0000-0000-0000-000000000000` and generated instants as
`2026-01-01T00:00:00Z`; nothing else is edited.

## 1. Model

A **thread** is an ordered, append-only log of **chunks**. A **turn** is the
slice of that log between a `start` chunk and the `done` chunk that terminates
it. Every chunk row carries a monotonically increasing integer **cursor**, and
a client resumes by naming the last cursor it saw.

The log is the source of truth for what the assistant said. A client MUST be
able to rebuild the full conversation from the log alone; nothing the user sees
is carried only by a live connection.

## 2. Transport

An event stream MUST be served as `text/event-stream`. The runtime's own
streams also carry `x-vercel-ai-ui-message-stream: v1`, which names the chunk
vocabulary in section 5.

Two reads are defined:

- **Tail.** `GET <thread>/events?after=<cursor>` streams every chunk after
  `cursor` and then follows the log live. `after` defaults to `0`, which means
  the whole thread.
- **Snapshot.** `GET <thread>/events/snapshot` returns `{chunks, cursor}` for
  the completed history: every chunk up to and including the most recent turn
  terminator, plus the prompt that opened an in-flight turn when one exists.

The runtime guarantees that a snapshot followed by a tail from the snapshot's
cursor yields exactly the chunks a reader would have seen live, in the same
order, with the same bytes.

## 3. Framing

A frame is a sequence of lines terminated by a blank line. Two frame shapes
are defined and a client MUST reject any third shape.

**Event frame.** Exactly two lines:

```
id: <cursor>\n
data: <payload>\n
\n
```

`<cursor>` is a decimal integer. `<payload>` is either a JSON object with no
embedded newline, or the literal `[DONE]`.

**Comment frame.** One line beginning with a colon:

```
: keep-alive\n
\n
```

A comment frame carries no cursor and no payload. The runtime sends one after
every interval of silence (15 seconds by default) so an idle stream is not
closed by an intermediary. A client MUST ignore comment frames and MUST NOT
advance its cursor on one.

## 4. Cursors and resumption

- Cursors MUST be strictly increasing within a thread. They are not dense: a
  client MUST NOT assume `n + 1` is the next cursor.
- Cursors are per-deployment, not per-thread. Two threads written at the same
  time interleave their cursors and never share one.
- `after` is exclusive. A reader that saw cursor `n` and reconnects with
  `after=n` receives the chunk after `n` and never repeats one.
- A client SHOULD persist the last cursor it observed for each thread and send
  it on reconnect. A client that has lost its cursor MUST take a snapshot
  rather than tailing from `0` mid-turn, because a tail from `0` replays parts
  the client may already hold.

A host MAY answer a tail request with `204 No Content` when the thread has no
turn in flight. A client that receives it MUST fall back to the snapshot. A
client that cannot hold a long-lived connection MAY poll the snapshot instead;
the ordering and the bytes are identical either way.

## 5. Chunk vocabulary

A chunk is a JSON object whose `type` field discriminates it. Field names are
camelCase. A field the runtime has nothing to say about is omitted, never sent
as `null`. A client MUST ignore a chunk whose `type` it does not know, and MUST
ignore unknown fields on a chunk it does know.

### 5.1 Stream chunks

<!-- chunks:begin -->

| Kind | Meaning |
| --- | --- |
| `start` | The turn begins. `messageId` names the assistant message it builds. |
| `start-step` | A step of the turn begins. |
| `text-start` | A text part begins. `id` identifies the part. |
| `text-delta` | More text for the part named by `id`. |
| `text-end` | The text part named by `id` is complete. |
| `reasoning-start` | A reasoning part begins. |
| `reasoning-delta` | More reasoning text for the part named by `id`. |
| `reasoning-end` | The reasoning part named by `id` is complete. |
| `tool-input-start` | A tool call begins. `toolCallId` identifies it. |
| `tool-input-delta` | More raw input text for the call. |
| `tool-input-available` | The call's input is complete and valid. |
| `tool-input-error` | The call's input could not be parsed. |
| `tool-approval-request` | The call needs the user's approval before it runs. |
| `tool-output-available` | The call returned. |
| `tool-output-error` | The call failed. |
| `tool-output-denied` | The user refused the call. |
| `file` | A file the assistant produced. |
| `source-url` | A web source the assistant cited. |
| `source-document` | A document source the assistant cited. |
| `message-metadata` | Metadata to merge onto the assistant message. |
| `finish-step` | The step ends. |
| `error` | The turn hit an error. The turn is not necessarily over. |
| `abort` | The run was aborted. |
| `finish` | The turn ends. `finishReason` says how. |
| `done` | The turn's terminator. Its payload is the literal `[DONE]`. |

<!-- chunks:end -->

### 5.2 Data parts

A data part is a chunk whose `type` begins with `data-` and whose `data` field
carries the payload. A data part with `transient: true` MUST NOT be persisted
onto the message a client renders from history; it is a live indicator only. A
data part with an `id` reconciles: a later chunk with the same `type` and `id`
replaces the payload of the earlier one rather than appending a second part.

The runtime defines these. An assistant MAY register more.

<!-- data_parts:begin -->

| Kind | Meaning |
| --- | --- |
| `data-turn-status` | A human-readable hint about what the turn is doing. |
| `data-turn-usage` | Running tokens and cost for the turn. Transient. |
| `data-turn-stopped` | The user stopped this turn. |
| `data-lead-usage` | Usage of the lead agent alone. Reconciles on its `id`. |
| `data-sub-agent-call` | One sub-agent dispatch. Reconciles on its `id`. |
| `data-sub-agent-step` | One event inside a sub-agent's run. |
| `data-conversation-title` | The thread's generated title. |
| `data-background-task-started` | A durable tool was deferred to a worker. |
| `data-task-progress` | Progress of a durable tool. |
| `data-task-completed` | A durable tool finished. |

<!-- data_parts:end -->

### 5.3 Log envelopes

Three kinds are written to the log and MUST NOT be framed onto the wire. They
record the prompt side of a thread so a snapshot can rebuild the whole
conversation, and a client reads them from the snapshot's `chunks` array.

<!-- envelopes:begin -->

| Kind | Meaning |
| --- | --- |
| `user-message` | The user's message, as a complete message object. |
| `system-message` | A system message, as a complete message object. |
| `assistant-message` | A whole assistant message, not built from deltas. |

<!-- envelopes:end -->

## 6. The shape of a turn

A turn MUST begin with exactly one `start` chunk and MUST end with exactly one
`finish` chunk followed by exactly one `done` chunk. A client MAY treat `done`
as the only reliable turn boundary.

`finishReason` reports how the turn ended:

| Value | Meaning |
| --- | --- |
| `stop` | The turn ran to completion. |
| `error` | The turn's driver raised. |
| `other` | The turn was stopped by the user, or suspended on a durable task. |

An `error` chunk does not end a turn: the runtime converts a failure inside the
agent's stream into an `error` chunk, continues, and still closes the turn with
`finish` and `done`. A turn that streamed an `error` chunk and then completed
therefore reports `finishReason: "stop"`. A client MUST use the `error` chunk,
not `finishReason`, to decide whether to show a failure.

A stopped turn writes `data-turn-stopped` before `finish`, so the stopped state
survives a reload.

## 7. Producer envelope

Between a turn's graph and the log, a chunk travels wrapped:

```json
{ "chunk": { "type": "text-delta", "id": "...", "delta": "..." } }
```

This envelope is internal to a deployment. It is unwrapped before the chunk is
written to the log, so it never reaches a client. It is specified here because
an assistant that emits its own chunks MUST use it.

## 8. Captured examples

One example per chunk kind the reference assistant produces. The kinds in
section 5 that are absent here are defined by the protocol and emitted by
assistants that use those capabilities; the reference assistant does not.

<!-- examples:begin -->

#### `data-turn-status`

```json
{
  "type": "data-turn-status",
  "data": {
    "label": "Preparing context",
    "waitingOnLlm": false
  }
}
```

#### `data-turn-stopped`

```json
{
  "type": "data-turn-stopped",
  "data": {}
}
```

#### `data-turn-usage`

```json
{
  "type": "data-turn-usage",
  "data": {
    "costUsd": "0",
    "totalTokens": 57
  },
  "transient": true
}
```

#### `done`

```json
"[DONE]"
```

#### `error`

```json
{
  "type": "error",
  "errorText": "A deferred tool call was present, but `DeferredToolRequests` is not among output types. To resolve this, add `DeferredToolRequests` to the list of output types for this agent, or use a `HandleDeferredToolCalls` capability to handle deferred tool calls inline."
}
```

#### `finish`

```json
{
  "type": "finish",
  "finishReason": "stop"
}
```

#### `finish-step`

```json
{
  "type": "finish-step"
}
```

#### `message-metadata`

```json
{
  "type": "message-metadata",
  "messageMetadata": {
    "pydantic_ai": {
      "timestamp": "2026-01-01T00:00:00Z"
    }
  }
}
```

#### `start`

```json
{
  "type": "start",
  "messageId": "00000000-0000-0000-0000-000000000000"
}
```

#### `start-step`

```json
{
  "type": "start-step"
}
```

#### `text-delta`

```json
{
  "type": "text-delta",
  "delta": "You said: which sites do you serve",
  "id": "00000000-0000-0000-0000-000000000000"
}
```

#### `text-end`

```json
{
  "type": "text-end",
  "id": "00000000-0000-0000-0000-000000000000"
}
```

#### `text-start`

```json
{
  "type": "text-start",
  "id": "00000000-0000-0000-0000-000000000000"
}
```

#### `tool-input-available`

```json
{
  "type": "tool-input-available",
  "toolCallId": "call_add",
  "toolName": "add",
  "input": {
    "a": 2,
    "b": 3
  }
}
```

#### `tool-input-delta`

```json
{
  "type": "tool-input-delta",
  "toolCallId": "call_add",
  "inputTextDelta": "{\"a\":2,\"b\":3}"
}
```

#### `tool-input-start`

```json
{
  "type": "tool-input-start",
  "toolCallId": "call_add",
  "toolName": "add"
}
```

#### `tool-output-available`

```json
{
  "type": "tool-output-available",
  "toolCallId": "call_add",
  "output": 5
}
```

#### `tool-output-error`

```json
{
  "type": "tool-output-error",
  "toolCallId": "call_wipe",
  "errorText": "Tool execution was interrupted by an error."
}
```

<!-- examples:end -->

## 9. Building a message from chunks

A client reduces a turn's chunks into one assistant message with an ordered
`parts` array. The rules a conforming reducer MUST follow:

- `start` sets the message id. `message-metadata` and `finish` merge metadata.
- `start-step` appends a `step-start` part.
- `text-start` appends a text part in state `streaming`; `text-delta` appends
  to the part with the same `id`; `text-end` moves it to `done`. Reasoning
  parts follow the same rule.
- Tool chunks address one part by `toolCallId`. The part's `state` walks
  `input-streaming` -> `input-available` -> (`approval-requested`) ->
  `output-available` | `output-error` | `output-denied`. A later chunk for a
  call already in the array patches that part; it never appends a second one.
- A non-transient data part appends, unless it carries an `id` that matches an
  existing part of the same `type`, in which case it replaces that part's
  `data`.
- A chunk that addresses a part the client does not hold MUST be ignored, not
  treated as an error.

The runtime's own reducer is `assistant_core.conversation.ui_message_reducer`.

## 10. Versioning

This protocol follows the runtime package's contract rule:

- **Additive only within a minor version.** A new chunk kind, a new data part
  or a new optional field is a minor bump. A client written against 1.0.0 MUST
  keep working against any 1.x.
- **Removing or retyping anything is a major version**, and every registered
  assistant must be migrated in the same change.
- A client MUST ignore what it does not recognise, which is what makes the
  additive rule safe.

## 11. What this runtime does not implement

The `tool-approval-request` and `tool-output-denied` chunks are part of the
protocol and the runtime carries them, but the one-agent turn graph the package
ships (`assistant_core.graph.single_agent`) resolves no deferred tool call: an
assistant that marks a tool approval-required gets an `error` chunk instead of
an approval request. The repository's knowledge bundle records the gap and the
fix as `backlog/single-agent-graph-cannot-ask-for-approval.md`.
