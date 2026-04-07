/**
 * Shared chat message reducer for workbench and main chat systems.
 *
 * Provides pure state transformations for common message operations:
 * append delta, set full message, set citations, start/end tool calls,
 * add user message, load history, end stream, and set error.
 *
 * The reducer is generic over `T extends BaseChatMessage` so it works
 * with both WorkbenchMessage (simple) and main chat Message (complex).
 *
 * Individual transform functions are also exported for systems that
 * manage state outside of useReducer (e.g. the main chat handler
 * architecture which uses setMessages + mutable context).
 */

// ── Base interface ──────────────────────────────────────────────────

/**
 * Minimal message shape that both WorkbenchMessage and the shared
 * Message type satisfy. The reducer operates on this contract.
 */
export interface BaseChatMessage {
  id?: string;
  role: "user" | "assistant";
  content: string;
  citations?: readonly { title: string; url?: string | null; snippet?: string | null }[];
  toolCalls?: readonly { id: string; name: string; result?: string | null }[];
}

// ── State ───────────────────────────────────────────────────────────

export interface ChatMessageState<T extends BaseChatMessage> {
  messages: T[];
  currentAssistantId: string | null;
  msgCounter: number;
}

export function initialChatMessageState<T extends BaseChatMessage>(): ChatMessageState<T> {
  return { messages: [], currentAssistantId: null, msgCounter: 0 };
}

// ── Actions ─────────────────────────────────────────────────────────

export type ChatMessageAction<T extends BaseChatMessage> =
  | { type: "append_delta"; delta: string; createMessage: (id: string, content: string) => T }
  | { type: "set_full_message"; content: string; createMessage: (id: string, content: string) => T }
  | { type: "set_citations"; citations: BaseChatMessage["citations"] }
  | { type: "start_tool_call"; id: string; name: string }
  | { type: "end_tool_call"; id: string; result?: string | null }
  | { type: "add_user_message"; message: T }
  | { type: "end_stream" }
  | { type: "load_history"; messages: T[]; counterStart: number }
  | { type: "set_error"; error: string; createMessage: (id: string, content: string) => T };

// ── ID generation ───────────────────────────────────────────────────

function nextId(state: ChatMessageState<BaseChatMessage>, prefix: string): string {
  return `${prefix}-${state.msgCounter + 1}`;
}

// ── Pure transform functions ────────────────────────────────────────

/**
 * Append a text delta to the current assistant message, or create a
 * new assistant message if none exists for this turn.
 */
export function appendDelta<T extends BaseChatMessage>(
  state: ChatMessageState<T>,
  delta: string,
  createMessage: (id: string, content: string) => T,
  idPrefix: string,
): ChatMessageState<T> {
  if (delta === "") return state;

  const messages = state.messages;
  const last = messages[messages.length - 1];

  if (
    last?.role === "assistant" &&
    last.id != null &&
    last.id === state.currentAssistantId
  ) {
    return {
      ...state,
      messages: [
        ...messages.slice(0, -1),
        { ...last, content: last.content + delta },
      ],
    };
  }

  const id = nextId(state, idPrefix);
  return {
    messages: [...messages, createMessage(id, delta)],
    currentAssistantId: id,
    msgCounter: state.msgCounter + 1,
  };
}

/**
 * Replace the full content of the current assistant message, or create
 * a new one if none exists for this turn.
 */
export function setFullMessage<T extends BaseChatMessage>(
  state: ChatMessageState<T>,
  content: string,
  createMessage: (id: string, content: string) => T,
  idPrefix: string,
): ChatMessageState<T> {
  if (content === "") return state;

  const messages = state.messages;
  const last = messages[messages.length - 1];

  if (
    last?.role === "assistant" &&
    last.id != null &&
    last.id === state.currentAssistantId
  ) {
    return {
      ...state,
      messages: [
        ...messages.slice(0, -1),
        { ...last, content },
      ],
    };
  }

  const id = nextId(state, idPrefix);
  return {
    messages: [...messages, createMessage(id, content)],
    currentAssistantId: id,
    msgCounter: state.msgCounter + 1,
  };
}

/**
 * Attach citations to the last assistant message.
 */
export function setCitations<T extends BaseChatMessage>(
  state: ChatMessageState<T>,
  citations: BaseChatMessage["citations"],
): ChatMessageState<T> {
  if (citations == null || citations.length === 0) return state;

  const messages = state.messages;
  const last = messages[messages.length - 1];

  if (last?.role !== "assistant") return state;

  return {
    ...state,
    messages: [
      ...messages.slice(0, -1),
      { ...last, citations },
    ],
  };
}

/**
 * Add a tool call entry to the current assistant message's toolCalls.
 */
export function startToolCall<T extends BaseChatMessage>(
  state: ChatMessageState<T>,
  id: string,
  name: string,
): ChatMessageState<T> {
  const messages = state.messages;
  const last = messages[messages.length - 1];

  if (
    last?.role !== "assistant" ||
    last.id == null ||
    last.id !== state.currentAssistantId
  ) {
    return state;
  }

  const existing = last.toolCalls ?? [];
  return {
    ...state,
    messages: [
      ...messages.slice(0, -1),
      { ...last, toolCalls: [...existing, { id, name }] },
    ],
  };
}

/**
 * Set the result on a tool call by id in the last assistant message.
 */
export function endToolCall<T extends BaseChatMessage>(
  state: ChatMessageState<T>,
  id: string,
  result?: string | null,
): ChatMessageState<T> {
  const messages = state.messages;
  const last = messages[messages.length - 1];

  if (last?.role !== "assistant" || last.toolCalls == null) {
    return state;
  }

  return {
    ...state,
    messages: [
      ...messages.slice(0, -1),
      {
        ...last,
        toolCalls: last.toolCalls.map((tc) =>
          tc.id === id ? { ...tc, result: result ?? "" } : tc,
        ),
      },
    ],
  };
}

/**
 * Append a user message.
 */
export function addUserMessage<T extends BaseChatMessage>(
  state: ChatMessageState<T>,
  message: T,
): ChatMessageState<T> {
  return {
    messages: [...state.messages, message],
    currentAssistantId: null,
    msgCounter: state.msgCounter,
  };
}

/**
 * Clear the current assistant tracking (end of stream turn).
 */
export function endStream<T extends BaseChatMessage>(
  state: ChatMessageState<T>,
): ChatMessageState<T> {
  return { ...state, currentAssistantId: null };
}

/**
 * Load history (replaces all messages and resets counter).
 */
export function loadHistory<T extends BaseChatMessage>(
  state: ChatMessageState<T>,
  messages: T[],
  counterStart: number,
): ChatMessageState<T> {
  return {
    messages,
    currentAssistantId: null,
    msgCounter: counterStart,
  };
}

/**
 * Append an error message as an assistant turn.
 */
export function setError<T extends BaseChatMessage>(
  state: ChatMessageState<T>,
  error: string,
  createMessage: (id: string, content: string) => T,
  idPrefix: string,
): ChatMessageState<T> {
  const id = nextId(state, idPrefix);
  return {
    messages: [...state.messages, createMessage(id, error)],
    currentAssistantId: null,
    msgCounter: state.msgCounter + 1,
  };
}

// ── Reducer ─────────────────────────────────────────────────────────

const ID_PREFIX = "wb-msg";

export function chatMessageReducer<T extends BaseChatMessage>(
  state: ChatMessageState<T>,
  action: ChatMessageAction<T>,
): ChatMessageState<T> {
  switch (action.type) {
    case "append_delta":
      return appendDelta(state, action.delta, action.createMessage, ID_PREFIX);
    case "set_full_message":
      return setFullMessage(state, action.content, action.createMessage, ID_PREFIX);
    case "set_citations":
      return setCitations(state, action.citations);
    case "start_tool_call":
      return startToolCall(state, action.id, action.name);
    case "end_tool_call":
      return endToolCall(state, action.id, action.result);
    case "add_user_message":
      return addUserMessage(state, action.message);
    case "end_stream":
      return endStream(state);
    case "load_history":
      return loadHistory(state, action.messages, action.counterStart);
    case "set_error":
      return setError(state, action.error, action.createMessage, ID_PREFIX);
  }
}
