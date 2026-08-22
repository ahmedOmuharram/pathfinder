---
type: Backlog Item
title: A failed turn shows "Response failed" while it streams, and nothing at all after a reload
description: A turn that ends with error + finish(error) + done renders the assistant error card live, because the error chunk reaches useChat as chat.error. Neither reducer turns that chunk into a message part, so the snapshot replay that rebuilds the transcript on reload drops it: the reader sees the half-finished answer with no sign that the turn failed. Applies to every failed turn, including the terminator the stalled-job sweep writes.
tags: [chat, transport, sse, frontend, error-handling]
generated: { by: claude-code/opus-5, at: 2026-08-19T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-19T00:00:00Z }
status: stable
---

# Investigation (2026-08-19, reducers driven directly)

**What I did.** Built the chunk log a failed turn leaves in `conversation_events` - the
nine chunks `user-message`, `data-turn-status {label: "Queued"}`, `start {messageId:
"a1"}`, `text-start`, `text-delta {delta: "Looking at PlasmoDB kinases"}`, `text-end`,
`error {errorText: "The worker running this turn stopped before it finished. Send the
message again to retry."}`, `finish {finishReason: "error"}`, `done` - and ran it through
both reducers that rebuild a transcript from that log: the backend's
`tests/_support/chunk_log.py::reduce_chunks_to_messages` (over
`assistant_core/conversation/ui_message_reducer.py::reduce_chunks`) and the frontend's
`readUIMessageStream`, the reducer `lib/api/conversationSnapshot.ts::reduceAssistantSlice`
drives on every snapshot load.

**What I got.** Both dropped the error. The backend produced two messages, the assistant
one being

```
{"id": "a1", "role": "assistant", "parts": [
  {"type": "data-turn-status", "data": {"label": "Queued", "waitingOnLlm": false}},
  {"type": "text", "text": "Looking at PlasmoDB kinases", "providerMetadata": null, "state": "done"}]}
```

and the frontend produced the same two parts:

```
{"id": "a1", "role": "assistant", "parts": [
  {"type": "data-turn-status", "data": {"label": "Queued", "waitingOnLlm": false}},
  {"type": "text", "text": "Looking at PlasmoDB kinases", "state": "done"}]}
```

Two parts in both, no third. Side by side with the live render: while the same nine chunks
stream, `AssistantErrorCard` (`features/conversation/content/MessageRenderer.tsx:225`)
draws "Response failed" plus the `errorText`, because `useChat` puts the error chunk on
`chat.error` and `@assistant-ui/react-ai-sdk/dist/ui/use-chat/useAISDKRuntime.js:31`
forwards it as message metadata, which becomes `status.type === "incomplete"`. Reload the
tab and that card is gone.

**Why that's wrong.** The reader is left with a half-finished answer presented as a
finished one. In the log above the assistant text stops at "Looking at PlasmoDB kinases" -
no gene count, no strategy - and after a reload nothing on screen says the turn died, so
the partial text reads as the whole answer. A researcher who comes back to the tab, or
opens the conversation on another machine, cannot tell a truncated turn from a short one,
and the message is quotable and forkable in that state.

**Why it happens.** No reducer maps the `error` chunk to a part.
`assistant_core/conversation/_chunk_handlers.py::_HANDLERS` has no `"error"` key, so `_apply_chunk` is
a no-op for it, and `write_turn_message` (`ai/graph/_lead_turn.py:329`) persists the same
part list to `messages`. On the client, `processUIMessageStream`'s `case "error"` only
calls `onError` (`apps/web/node_modules/ai/dist/index.mjs:5781-5784`), and
`reduceAssistantSlice` passes no `onError` and leaves `terminateOnError` at its default
`false` (`:8301-8341`), so the chunk is consumed and discarded. Live rendering works
because it reads `chat.error`, which the snapshot path never populates: the transcript is
rebuilt from chunks alone.

**Fix (to decide).** Two options, and they are not equivalent.
1. A visible interrupted/failed part: add a payload to `assistant_core/graph/stream_events.py` (next
   to `TurnStoppedPayload`, which `StoppedNotice.tsx` already renders and which cannot be
   reused here because it reads "You stopped this response."), emit it wherever an
   `ErrorChunk` is written today (`ai/conversation/turn_runner.py:311`,
   `jobs/maintenance.py::_close_stalled_turn`), and register a renderer in
   `features/conversation/content/contentComponents.ts`. The part is a durable chunk, so
   it survives the snapshot with no reducer change, and the wording is ours.
2. Reduce `error` into a part: add an `"error"` handler to
   `assistant_core/conversation/_chunk_handlers.py` and a matching client-side part. Cheaper, but the
   AI SDK owns the `error` chunk shape and has no error part type, so the client would
   need a non-standard part that `uiMessageChunkSchema` does not describe.
Whichever is chosen, the test is a snapshot-replay case asserting a third part for the
nine-chunk log above, on both sides.

**What you'd get.** A reloaded conversation shows the same "Response failed" notice the
live stream showed, under the partial answer, so a turn that died is never mistaken for
one that finished.
