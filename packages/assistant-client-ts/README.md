# @pathfinder/assistant-client

A headless TypeScript client for the assistant runtime wire protocol. It is
built from `packages/assistant-core/PROTOCOL.md`, not from the app that uses it,
and its test suite is the protocol's consumer-side conformance suite.

## Entry points

| Import                                | Dependencies         | Holds                                                                       |
| ------------------------------------- | -------------------- | --------------------------------------------------------------------------- |
| `@pathfinder/assistant-client`        | none                 | Frame reader, cursors, reduction, snapshot, request body, `AssistantClient` |
| `@pathfinder/assistant-client/ai-sdk` | `ai` (optional peer) | `DurableChatTransport` for `useChat`                                        |
| `@pathfinder/assistant-client/legacy` | none                 | The task-progress dialect the protocol does not define                      |

No entry point imports React. A host supplies its own hooks, storage and
rendering.

## Reading a thread

```ts
import { AssistantClient, webStorageCursorStore } from "@pathfinder/assistant-client";

const client = new AssistantClient({
  eventsUrlFor: (id) => `/api/v1/conversations/${id}/events`,
  snapshotUrlFor: (id) => `/api/v1/conversations/${id}/events/snapshot`,
  cursors: webStorageCursorStore(),
  headers: () => ({ authorization: `Bearer ${token}` }),
});

const { messages } = await client.snapshot(threadId);

const tail = await client.openTail(threadId);
if (tail.status === "idle") {
  // No turn in flight. Section 4 says take a snapshot.
} else {
  for await (const chunk of tail.chunks) render(chunk);
}
```

A host that cannot hold a connection calls `client.poll(threadId)` instead. The
ordering and the bytes are the same either way.

## The conformance gate

`src/protocol/captured.json` is generated from `PROTOCOL.md` by
`yarn sync:protocol`. The suite regenerates it and compares, so the capture
cannot drift from the document. A second gate compares the document's chunk
table to the kinds the reducer answers to, so a kind the document adds fails
here until this client reads it.

```bash
yarn test        # conformance + unit
yarn typecheck
yarn lint
```
