## Pathfinder Web (`apps/web`)

Next.js UI for PathFinder. It provides:

- **Chat interface**: unified streaming agent chat that researches, plans, and builds/edits strategy graphs
- **Strategy graph editing**: visual strategy builder with drag-and-drop nodes, combine operations, and parameter editing
- **Analysis & workbench**: experiment evaluation, enrichment analysis, cross-validation, AI-powered workbench for multi-experiment analysis

### Project structure

```
src/
  app/                          # Next.js App Router
    api/v1/                     #   API route proxies
    components/                 #   App-level components (TopBar, LoginModal, Providers)
    hooks/                      #   App-level hooks (useAuthCheck, useSidebarResize, useToasts)
    workbench/                  #   /workbench page
    layout.tsx                  #   Root layout
    page.tsx                    #   Main chat/strategy page
  features/                     # Feature modules (vertical slices)
    analysis/                   #   Experiment analysis and results
    chat/                       #   Chat UI and streaming
      components/               #     Chat component tree:
        UnifiedChatPanel.tsx    #       Main chat panel
        ChatMessageList.tsx     #       Message list with auto-scroll
        ChatEmptyState.tsx      #       Empty state with suggestions
        MessageComposer.tsx     #       Input bar with mention autocomplete
        message/                #       Message rendering (AssistantMessageParts, ChatMarkdown,
                                #         MentionAutocomplete, ReasoningToggle, ToolCallInspector)
        optimization/           #       Optimization UI (OptimizationProgressPanel, OptimizationChart,
                                #         OptimizationTrialList, optimizationFormatters)
        thinking/               #       Thinking/reasoning display (ThinkingPanel, ChatThinkingDetails,
                                #         ModelPicker, SubKaniStatusIcon)
        delegation/             #       Delegation draft viewer (DelegationDraftViewer,
                                #         DraftSelectionBar, NodeCard)
      handlers/                 #     SSE event handlers (message, strategy, tool events)
      hooks/                    #     Chat-specific hooks (useChatStreaming, useGraphSnapshot,
                                #       useThinkingState, useUnifiedChatDataLoading, etc.)
      streaming/                #     StreamingSession -- manages SSE lifecycle
      utils/                    #     Message parsing, graph snapshots, delegation drafts
      data/                     #     Static chat data (suggestedQuestions.json)
      sse_events.ts             #     SSE event type definitions
      stream.ts                 #     Stream initiation logic
      node_selection.ts         #     Strategy node selection from chat context
    settings/                   #   Settings page
      components/               #     SettingsPage, plus settings/ subdirectory
                                #       (GeneralSettings, DataSettings, AdvancedSettings,
                                #       SettingsField)
    sidebar/                    #   Navigation sidebar
      components/               #     ConversationSidebar, ConversationList, modals
      hooks/                    #     Sidebar data and action hooks
      services/                 #     Strategy sidebar workflows
      utils/                    #     Strategy items, helpers
    sites/                      #   Site selection and theming
      components/               #     Site picker UI
      hooks/                    #     Site data hooks
      siteBanners.ts            #     Per-site banner config
      siteTheme.ts              #     Per-site color themes
    strategy/                   #   Strategy graph and step editing
      editor/                   #     StepEditor and editor components
      graph/                    #     StrategyGraph visualization (dagre + ReactFlow)
        components/             #       Graph nodes, edges, layout, modals, toolbar
        hooks/                  #       Split graph hooks:
                                #         useStrategyGraph, useStrategyGraphNodes,
                                #         useStrategyGraphHandlers, useStrategyGraphLayout,
                                #         useGraphConnections, useGraphSelection, useGraphSave,
                                #         useAutoFitView, useUndoRedoHotkeys, etc.
        utils/                  #       Graph layout, node deletion, ortholog insert logic
      hooks/                    #     useBuildStrategy
      parameters/               #     Parameter coercion and spec helpers
      services/                 #     openAndHydrateDraftStrategy, step counts, WDK URL
      utils/                    #     Draft summaries
      validation/               #     Save validation, formatting, zero-result advisor
    workbench/                  #   AI workbench for multi-experiment analysis
  lib/                          # Shared utilities (not feature-specific)
    api/                        #   Split API client:
                                #     http.ts (base HTTP), client.ts (main client),
                                #     auth.ts, errors.ts, strategies.ts, genes.ts,
                                #     models.ts, plans.ts, sites.ts, veupathdb-auth.ts
    components/ui/              #   Reusable UI primitives (Button, Card, Badge, Tooltip,
                                #     Input, Label, Progress, Skeleton, Stepper, etc.)
    errors/                     #   AppError class
    hooks/                      #   Shared hooks (usePrevious)
    strategyGraph/              #   Strategy graph serialization, deserialization, display names
    types/                      #   Shared TypeScript type helpers (refs)
    utils/                      #   cn (classnames), isRecord, chartTheme, asyncAction
    sse.ts                      #   Low-level SSE parsing
    formatTime.ts               #   Time formatting utility
  state/                        # Global state (Zustand stores)
    useSessionStore.ts          #   Chat session state (messages, model)
    useSettingsStore.ts         #   User preferences
    useStrategySelectors.ts     #   Strategy selector hooks
    useStrategyStore.ts         #   Active strategy state (facade)
    strategy/                   #   Sliced strategy store
      store.ts                  #     Core strategy store
      draftSlice.ts             #     Draft strategy slice
      historySlice.ts           #     History/undo-redo slice
      listSlice.ts              #     Strategy list (sidebar)
      metaSlice.ts              #     Strategy metadata slice
      types.ts                  #     Type definitions
      helpers.ts                #     Helper functions
  styles/                       # Global CSS
    globals.css                 #   Tailwind imports and global styles
  typings/                      # Ambient type declarations
    dagre.d.ts                  #   Dagre graph layout types
    remark-gfm.d.ts             #   Remark GFM plugin types
```

### Key patterns

**Feature-based organization**: Each feature (`chat`, `strategy`, `sidebar`, `analysis`, `workbench`, `sites`, `settings`) is a self-contained module with its own components, hooks, services, and utilities. Cross-feature imports go through `lib/` or `state/`.

**Unified agent**: There is no separate plan/execute mode. The backend agent autonomously decides when to research, think, or act. The chat UI streams the agent's output and renders tool calls, thinking steps, and strategy mutations in a single conversation flow.

**State management**: [Zustand](https://github.com/pmndrs/zustand) stores in `state/` hold global state. The strategy store is split into domain-specific slices (`draftSlice`, `historySlice`, `listSlice`, `metaSlice`) in `state/strategy/`, combined via a facade store (`useStrategyStore`). Selector hooks live in `useStrategySelectors.ts`. Session and settings each have their own top-level store.

**SSE streaming**: The chat uses Server-Sent Events. `features/chat/streaming/StreamingSession.ts` manages the connection lifecycle, and `features/chat/sse_events.ts` defines the event types. Events are dispatched to handlers that update Zustand stores.

**Strategy graph**: Strategy graphs are visualized using [ReactFlow](https://reactflow.dev/) with [dagre](https://github.com/dagrejs/dagre) for automatic layout. Serialization/deserialization lives in `lib/strategyGraph/`. Graph interaction hooks are split by concern (`useStrategyGraphNodes`, `useStrategyGraphHandlers`, `useStrategyGraphLayout`).

**API communication**: `lib/api/` contains a split HTTP client (`http.ts` for base requests, plus domain-specific modules like `strategies.ts`, `genes.ts`, `models.ts`). Next.js API routes in `app/api/v1/` proxy requests to the backend (see `next.config.js` rewrites).

**Styling**: [Tailwind CSS](https://tailwindcss.com/) with utility classes. Reusable UI primitives (Button, Card, Badge, Tooltip, etc.) live in `lib/components/ui/`. Per-site theming is handled by `features/sites/siteTheme.ts`.

**Shared types**: Types are imported from `@pathfinder/shared` (the `packages/shared-ts` workspace package) via TS path mapping. Next.js transpiles this package automatically (see `next.config.js`).

### Architecture & design decisions

**Zustand slice composition:** The strategy store is the most complex piece of state. Rather than a monolithic store, it's composed from 4 independent slices — `draftSlice` (current strategy mutations), `historySlice` (undo/redo stack), `listSlice` (sidebar strategy list), and `metaSlice` (validation cache). Each slice manages one concern; the composed store combines them via Zustand's create function. This enables local reasoning about state mutations while keeping a single reactive store.

**Signals for decoupled re-runs:** The session store uses monotonic version counters (`authVersion`, `chatPreviewVersion`) instead of deep object equality. Hooks subscribe to these signals and re-run expensive logic (data fetching, SSE subscriptions) only when the signal bumps. This avoids unnecessary re-renders from unrelated state changes.

**Hooks as mini-stores:** The chat feature uses ~18 custom hooks managing streaming state, SSE subscription lifecycle, event parsing, and UI coordination. These manage ephemeral, complex state that doesn't belong in a Zustand store (it's session-scoped and tightly coupled to the streaming connection). Each hook handles one concern: `useStreamLifecycle` manages the SSE connection, `useStreamEvents` parses raw events, `useThinkingState` tracks reasoning display.

**API validation at network boundary:** All API responses are validated against Zod schemas immediately upon fetch (`requestJsonValidated`). Contract drift between frontend and backend is caught at the network boundary, not deep in component logic. Business logic can assume clean data.

**Feature isolation:** Each feature (`chat`, `strategy`, `analysis`, `workbench`, `sidebar`, `sites`, `settings`) is self-contained with its own components, hooks, services, and utilities. Cross-feature imports go through `lib/` or `state/`. Feature-specific stores (workbench) live inside their feature directory.

**Real API + mock LLM for E2E:** Playwright tests call live VEuPathDB APIs for gene searches, enrichment, catalog browsing. Only the LLM chat call is mocked (via `PATHFINDER_CHAT_PROVIDER=mock`). This catches real integration bugs that unit tests with mocked APIs would miss. Worker isolation uses `/dev/login?user_id=worker-{N}` so parallel workers don't interfere.

**SSE over WebSocket:** Chat streaming uses Server-Sent Events (unidirectional server→client) rather than WebSockets. Messages are sent via POST; responses stream via SSE. This is simpler (HTTP/1.1 compatible, no upgrade handshake) and matches the request→stream response pattern. Next.js has compression disabled (`compress: false`) to ensure SSE events flush immediately.

**Workbench as analysis hub:** Analysis components (enrichment, distributions, confusion matrices) live in the `analysis` feature but are re-exported and wrapped in collapsible panels by the `workbench` feature. The workbench store coordinates panel visibility, active gene set, and experiment context. This separation means analysis components can be reused outside the workbench.

### How it talks to the API

The web app uses Next rewrites to proxy to the backend (see `next.config.js`), so UI requests like `/api/...` forward to the configured API base.

Required env:

- `NEXT_PUBLIC_API_URL` (see `.env.example`)

### Run locally

```bash
cd apps/web
yarn install
yarn dev
```

Open `http://localhost:3000`.

### Scripts

From `package.json`:

- `yarn dev`: start Next dev server
- `yarn build` / `yarn start`: production build + start
- `yarn lint`: ESLint
- `yarn typecheck`: TypeScript (`tsc --noEmit`)
- `yarn test`: Vitest
- `yarn check:boundaries`: repo-specific boundary checks
- `yarn test:e2e`: Playwright E2E tests
- `yarn test:e2e:ui`: Playwright E2E tests with UI mode

### E2E testing

PathFinder uses a 3-tier Playwright E2E test architecture:

- **Feature tests** (`e2e/feature/`) — Individual feature verification (chat, strategy graph, gene sets, settings). Run in parallel.
- **Cross-feature tests** (`e2e/cross-feature/`) — Multi-feature workflows (gene set analysis pipeline, chat-to-workbench integration). Run serially due to WDK rate limits.
- **Journey tests** (`e2e/journey/`) — Full researcher workflows across VEuPathDB databases (malaria drug resistance on PlasmoDB, Toxoplasma host invasion, Leishmania virulence). Run serially.

**Page Objects** (`e2e/pages/`) encapsulate selectors and interactions. **Fixtures** handle auth, API setup, and test data seeding.

All tests use real VEuPathDB APIs. Only the LLM is mocked via `PATHFINDER_CHAT_PROVIDER=mock`.
