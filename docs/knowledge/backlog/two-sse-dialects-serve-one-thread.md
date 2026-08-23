---
type: Backlog Item
title: A thread streams two SSE dialects, and a conforming client can only read one
description: The per-task progress endpoint frames `event: stream` with a `{type,kind,data}` envelope and no cursor, while the chat stream frames `id`/`data` with the chunk as the payload. PROTOCOL.md section 3 defines two frame shapes and says a client must reject a third, so the client package refuses the task frames and keeps a separate legacy reader for them.
tags: [assistant-client, assistant-core, ws-v, protocol, sse, tasks]
generated: { by: claude-code/opus-5, at: 2026-08-23T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-23T00:00:00Z }
status: stable
---

# What I did

Built the consumer-side client from `PROTOCOL.md` alone and pointed its strict
frame reader at both streams a durable task produces: the thread's own
`GET /conversations/{id}/events`, and the task's
`GET /conversations/{id}/tasks/{task_id}/events`.

# What I got

The thread frames a chunk, with a cursor
(`assistant_core/conversation/event_stream.py::_frame_event`):

```
id: 41
data: {"type":"data-task-progress","data":{"taskId":"...","percent":40}}

```

The task endpoint frames the same information differently
(`pathfinder/transport/http/routers/tasks.py::_encode_event`):

```
event: stream
data: {"type":"custom","kind":"data-task-progress","data":{"taskId":"...","percent":40}}

```

Three differences in one payload: the field is `event`, not `id`; the chunk is
wrapped in a `{type:"custom", kind}` envelope instead of carrying its own
`type`; and no cursor is sent, so nothing can be resumed.

# Why that's wrong

`data-task-progress` and `data-task-completed` are in the protocol's data-part
table, so a client that implements the document expects them on the thread and
gets them nowhere. Section 3 defines exactly two frame shapes and says a client
MUST reject any third, so a conforming reader refuses the task stream by
construction - the refusal is asserted in
`packages/assistant-client-ts/tests/unit/typedEventFrames.test.ts`. A host that
wants task progress therefore needs a second reader, a second reconnect story
and a second set of types, and gets no resume for the half that matters most:
the long-running one. Every new consumer of the runtime pays this twice.

# Why it happens

The task channel predates the protocol document. It reuses the app's generic
typed-event helper (`streamTypedEvents`) and its `CustomEvent` envelope, while
the chat channel was rebuilt on the durable log and the AI SDK chunk vocabulary.
Nothing forced the two together, and `conversation_events` rows tagged with a
`task_id` are deliberately excluded from the chat stream
(`event_stream.py::_fetch_after`).

# Fix

Serve task progress as protocol frames on the thread: write the chunk as
`{"type":"data-task-progress", ...}` with no `custom` wrapper, frame it
`id: <cursor>\ndata: <chunk>`, and let the per-task endpoint become a filtered
read of the same log rather than a second dialect. The rows already exist and
already carry a cursor; what changes is the envelope and the framing. Then
delete `@pathfinder/assistant-client/legacy` and the app's `streamTypedEvents`
wrapper, or keep the wrapper only for the experiment and sweep routes that are
not thread events at all.

# What you'd get

One reader, one reconnect rule and one cursor for everything a thread emits: a
page reopened during a 20-minute enrichment resumes its progress the same way it
resumes the turn, and the client package drops a module.
