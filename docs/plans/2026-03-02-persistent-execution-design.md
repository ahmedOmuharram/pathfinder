# Persistent Execution Design

**Date**: 2026-03-02
**Status**: Approved
**Scope**: Chat + Experiments — background execution with SSE reconnection

## Problem

1. **Experiment SSE stuck on "connecting"** — initial run never receives events (bug).
2. **No persistent execution** — refreshing the page, switching tabs, or navigating away kills
   running operations (both chat and experiments). The server cancels background tasks when
   the HTTP response is interrupted.
3. **No reconnection** — once disconnected, there's no way to see progress for a still-running
   operation. All accumulated state (trial history, step analysis, in-flight messages) is lost.

### Root Cause

Both `sse.py:50` and `streaming.py:202` call `task.cancel()` in a `finally` block — the
producer is killed when the client disconnects. There is no event buffering, no pub/sub,
and no subscribe/reconnect endpoint.

## Architecture

### Universal Pattern

Both chat and experiments follow the same contract — no special cases:

```
POST /api/v1/chat                    → 202 {operationId, strategyId}
POST /api/v1/experiments             → 202 {operationId, experimentId}

GET  /api/v1/operations/{id}/subscribe  → SSE (catchup + live events)
GET  /api/v1/operations/active          → [{id, type, entityId, startedAt}]
```

Operations are identified by a unique `operationId`. The client starts an operation (fire-and-forget),
then subscribes for events. If the client disconnects, it re-subscribes and receives all buffered
events (catchup) followed by live events.

### Event Bus (`platform/event_bus.py`)

Per-operation in-memory event buffer + pub/sub:

```python
class EventBus:
    operation_id: str
    operation_type: str          # "chat" | "experiment"
    entity_id: str               # strategy_id or experiment_id
    events: list[JSONObject]     # all events buffered
    subscribers: list[Queue]     # active SSE listeners
    completed: bool
    end_event_types: set[str]

    async def emit(event) -> None:
        """Append to buffer, push to all subscribers."""

    async def subscribe() -> AsyncIterator[JSONObject]:
        """Yield all buffered events (catchup), then live events until completion."""
```

### Background Task Manager (`platform/task_manager.py`)

Singleton tracking all running operations:

```python
class BackgroundTaskManager:
    _operations: dict[str, EventBus]

    def start(id, type, entity_id, producer, end_events) -> EventBus:
        """Launch producer as asyncio.create_task. Returns EventBus for subscribing.
        Auto-cleans 5 minutes after completion."""

    def get(id) -> EventBus | None
    def list_active(type?) -> list[OperationInfo]
```

### SSE Subscribe Endpoint (`transport/http/routers/operations.py`)

```python
@router.get("/{operation_id}/subscribe")
async def subscribe(operation_id: str) -> StreamingResponse:
    """SSE stream: catchup events first, then live events until operation completes.
    Returns 404 if operation not found (completed and cleaned up)."""

@router.get("/active")
async def list_active(type: str | None = None) -> list[OperationInfo]:
    """List running operations. Used by frontend on mount to detect reconnectable ops."""
```

## API Changes

### Chat (`transport/http/routers/chat.py`)

- `POST /chat` returns 202 JSON `{operationId, strategyId}` (no longer SSE).
- The chat producer (agent loop + finalization) runs as a background task.
- Events are emitted to the EventBus instead of yielded to the HTTP response.
- Finalization (persist messages, graph, thinking) runs inside the producer after all events.

### Experiments (`transport/http/routers/experiments/execution.py`)

- `POST /experiments` returns 202 JSON `{operationId, experimentId}` (no longer SSE).
- Experiment runs as a background task via task manager.
- Progress events go to EventBus.
- Same for batch and benchmark endpoints.

### Experiment Incremental Persistence

Currently experiments only save at start and end. Change to save after each phase completion:

- After initial metrics/evaluation
- After each optimization trial batch (throttled: every ~5 trials)
- After cross-validation
- After enrichment
- After each step analysis phase

This ensures partial results survive even an API crash.

### Removed / Modified

- `transport/http/sse.py` — `sse_stream()` no longer cancels producer. Repurposed or replaced
  by EventBus integration.
- `transport/http/streaming.py` — `stream_chat()` no longer cancels producer. Events go to
  EventBus instead of being yielded directly.

## Frontend Changes

### SSE Library (`lib/sse.ts`)

New function `subscribeToOperation(operationId, handlers)`:

- Connects to `GET /operations/{id}/subscribe`
- Parses SSE events and routes to handlers
- Auto-reconnects on disconnect (exponential backoff: 1s, 2s, 4s, max 30s)
- Returns `{unsubscribe}` function

### Chat (`features/chat/`)

**`stream.ts`**:
- `streamChat()` → POST to start, then `subscribeToOperation()` for events.

**`hooks/useChatStreaming.ts`**:
- On mount: check `GET /operations/active` for running chat operations matching current strategy.
- If found: subscribe and replay catchup events through existing event handlers.
- All existing `handleChatEvent()` logic works unchanged — events are events regardless of source.

**`hooks/useUnifiedChatDataLoading.ts`**:
- After loading strategy history, check for active operation.
- If active: auto-subscribe (user sees live tool calls, thinking, etc.).

### Experiments (`features/experiments/`)

**`api/streaming.ts`**:
- `createExperimentStream()` → POST to start, then `subscribeToOperation()`.

**`store/useExperimentRunStore.ts`**:
- Support multiple concurrent runs: `activeRuns: Map<experimentId, RunState>`.
- On mount: check active operations, subscribe to any running experiments.
- Hydrate from catchup events (trial history, step analysis, metrics).

**`utils/experimentStreamRunner.ts`**:
- Updated to use `subscribeToOperation()` instead of `streamSSEParsed()`.

### Shared Hook: `useActiveOperations`

New hook used by both chat and experiments on mount:

```typescript
function useActiveOperations(type?: "chat" | "experiment") {
  // Fetches GET /operations/active on mount
  // Returns list of {operationId, type, entityId}
  // Used to auto-reconnect to running operations
}
```

### Next.js Proxy

- Add proxy route for `/api/v1/operations/` to forward subscribe SSE and active list.

## Bug Fix: "Stuck on Connecting"

The silent `catch {}` in `lib/sse.ts:179-182` swallows JSON parse errors. Fix:

1. Log parse errors (don't silently swallow).
2. The new `subscribeToOperation()` function handles this properly from the start.
3. EventBus always emits a `connected` event as the first frame, guaranteeing the client
   receives at least one event immediately.

## Concurrent Operations

- Multiple experiments run simultaneously (each with its own operation ID).
- One chat turn per strategy at a time (enforced by operation ID = strategy-scoped).
- `GET /operations/active` returns all running operations.
- Frontend subscribes to all independently.

## Cleanup & Lifecycle

- Operations auto-clean from memory 5 minutes after completion.
- If the API restarts, in-memory buffers are lost but:
  - Experiments: partial results persisted to DB via incremental saves.
  - Chat: messages already persisted incrementally during streaming.
  - Running operations that died with the process: experiments marked "running" in DB
    can be detected and marked as "error" on next startup.

## Testing

- Unit tests for EventBus (emit, subscribe, catchup, concurrent subscribers).
- Unit tests for BackgroundTaskManager (start, get, cleanup, list_active).
- Integration tests for subscribe endpoint (catchup + live + reconnect).
- E2E test: start experiment, refresh page, verify progress resumes.
- E2E test: start chat, refresh, verify messages + tool calls resume.
