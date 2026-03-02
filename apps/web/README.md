## Pathfinder Web (`apps/web`)

Next.js UI for PathFinder. It provides:

- **Chat interface**: unified streaming agent chat that researches, plans, and builds/edits strategy graphs
- **Strategy graph editing**: visual strategy builder with drag-and-drop nodes, combine operations, and parameter editing
- **Experiment mode**: batch experiment management, multi-step builders, evaluation, and comparison

### Project structure

```
src/
  app/                          # Next.js App Router
    api/v1/                     #   API route proxies (chat, experiments)
    components/                 #   App-level components (TopBar, LoginModal, Providers, ToastContainer)
    experiments/                #   /experiments page
    hooks/                      #   App-level hooks (useAuthCheck, useSidebarResize, useToasts)
    layout.tsx                  #   Root layout
    page.tsx                    #   Main chat/strategy page
  features/                     # Feature modules (vertical slices)
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
    experiments/                #   Experiment mode
      api/                      #     Split API client (crud, streaming, analysis,
                                #       controlSets, index)
      components/               #     Experiment UI components, organized into subdirectories:
                                #       SetupWizard/, RunningPanel/, ResultsDashboard/,
                                #       MultiStepBuilder/, AiAssistantPanel/, steps/,
                                #       plus top-level (ExperimentList, CompareView,
                                #       GeneLookupPanel, ControlSetManager, etc.)
      store/                    #     Split Zustand stores:
        useExperimentRunStore   #       Runtime experiment state (active runs, streaming)
        useExperimentViewStore  #       View/UI state (selected experiments, comparison)
        index.ts                #       Re-exports
      utils/                    #     experimentStreamRunner, strategyAdapter
      constants.ts              #     Experiment constants
      types.ts                  #     Experiment-local types
      suggestionParser.ts       #     Parse AI suggestions for experiments
    settings/                   #   Settings page
      components/               #     SettingsPage, plus settings/ subdirectory
                                #       (GeneralSettings, DataSettings, AdvancedSettings,
                                #       SettingsField)
    sidebar/                    #   Conversation sidebar
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
    useStrategyListStore.ts     #   Sidebar strategy list
    useStrategyStore.ts         #   Active strategy state (graph, steps, counts)
                                #   Note: experiment stores live in features/experiments/store/
  styles/                       # Global CSS
    globals.css                 #   Tailwind imports and global styles
  typings/                      # Ambient type declarations
    dagre.d.ts                  #   Dagre graph layout types
    remark-gfm.d.ts             #   Remark GFM plugin types
```

### Key patterns

**Feature-based organization**: Each feature (`chat`, `strategy`, `sidebar`, `experiments`, `sites`, `settings`) is a self-contained module with its own components, hooks, services, and utilities. Cross-feature imports go through `lib/` or `state/`.

**Unified agent**: There is no separate plan/execute mode. The backend agent autonomously decides when to research, think, or act. The chat UI streams the agent's output and renders tool calls, thinking steps, and strategy mutations in a single conversation flow.

**State management**: [Zustand](https://github.com/pmndrs/zustand) stores in `state/` hold global state. Each store is a single hook (`useSessionStore`, `useStrategyStore`, etc.) with actions and selectors. Feature-specific stores (e.g., experiment run/view stores) live inside their feature directory.

**SSE streaming**: The chat uses Server-Sent Events. `features/chat/streaming/StreamingSession.ts` manages the connection lifecycle, and `features/chat/sse_events.ts` defines the event types. Events are dispatched to handlers that update Zustand stores.

**Strategy graph**: Strategy graphs are visualized using [ReactFlow](https://reactflow.dev/) with [dagre](https://github.com/dagrejs/dagre) for automatic layout. Serialization/deserialization lives in `lib/strategyGraph/`. Graph interaction hooks are split by concern (`useStrategyGraphNodes`, `useStrategyGraphHandlers`, `useStrategyGraphLayout`).

**API communication**: `lib/api/` contains a split HTTP client (`http.ts` for base requests, plus domain-specific modules like `strategies.ts`, `genes.ts`, `models.ts`). Next.js API routes in `app/api/v1/` proxy requests to the backend (see `next.config.js` rewrites).

**Styling**: [Tailwind CSS](https://tailwindcss.com/) with utility classes. Reusable UI primitives (Button, Card, Badge, Tooltip, etc.) live in `lib/components/ui/`. Per-site theming is handled by `features/sites/siteTheme.ts`.

**Shared types**: Types are imported from `@pathfinder/shared` (the `packages/shared-ts` workspace package) via TS path mapping. Next.js transpiles this package automatically (see `next.config.js`).

### How it talks to the API

The web app uses Next rewrites to proxy to the backend (see `next.config.js`), so UI requests like `/api/...` forward to the configured API base.

Required env:

- `NEXT_PUBLIC_API_URL` (see `.env.example`)

### Run locally

```bash
cd apps/web
npm ci
npm run dev
```

Open `http://localhost:3000`.

### Scripts

From `package.json`:

- `npm run dev`: start Next dev server
- `npm run build` / `npm run start`: production build + start
- `npm run lint`: ESLint
- `npm run typecheck`: TypeScript (`tsc --noEmit`)
- `npm test`: Vitest
- `npm run check:boundaries`: repo-specific boundary checks
