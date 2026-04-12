# PathFinder Dashboard Filters

SigNoz supports dashboard variables and dynamic filters in the UI. This guide names the most useful PathFinder dimensions so dashboards, alerts, and investigations all use the same vocabulary.

## Filter Glossary

### `site_host`

The VEuPathDB host serving a dependency request, such as plasmodb.org. Use this when latency or retries might be isolated to one site.

- Applies to: dependency-reliability

### `intent`

The classified turn intent, such as new_strategy, edit_strategy, or follow_up. Use this to separate behavior by user goal rather than by raw prompt text.

- Applies to: pipeline-overview, approval-and-execution

### `model`

The configured model handling the turn or phase. Use this to compare latency, errors, and token usage across model choices.

- Applies to: pipeline-overview, approval-and-execution

### `surface`

The user-facing workflow family. Today this distinguishes chat vs plan_action on pipeline metrics, and chat vs workbench-style streams on SSE metrics.

- Applies to: pipeline-overview, approval-and-execution, streaming-delivery

## Dashboard Recommendations

### PathFinder Pipeline Overview

End-to-end AI turn latency and throughput for chat and plan-action runs.

- Recommended filters: `intent`, `model`, `run_kind`, `surface`, `phase`, `type`

### PathFinder Approval And Execution

Operational view of approval latency, execution time, phase transitions, and recoveries.

- Recommended filters: `phase`, `status`, `kind`, `model`, `intent`, `run_kind`, `surface`

### PathFinder Streaming Delivery

Live delivery health for SSE subscriptions and user-visible streaming behavior.

- Recommended filters: `surface`, `operation_type`, `stream_kind`, `reason`, `event_type`, `resumed`

### PathFinder Dependency Reliability

Backplane and external dependency health across Redis Streams, WDK, and site-search.

- Recommended filters: `site_host`, `endpoint_group`, `method`, `status_family`, `outcome`, `error_kind`, `stream_kind`, `event_type`

