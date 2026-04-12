# Alert Routing Strategy

Use the alert catalog labels as the stable routing contract across environments.

## Stable Labels

- `team`
  - owner of the alert
  - current value: `pathfinder`
- `surface`
  - the product or infrastructure area
  - examples: `pipeline`, `approval`, `sse`, `redis`, `wdk`, `site-search`
- `class`
  - the kind of operational problem
  - examples: `latency`, `availability`, `delivery`, `dependency`, `ux`, `backplane`

## Severity Guidance

- `warning`
  - something is degraded, trending badly, or likely to become user-visible soon
- `critical`
  - already user-visible or highly likely to cause active user harm without intervention

## Suggested Routing Policy

### Warning

- destination: team Slack or equivalent async channel
- expected response: business-hours triage
- purpose: catch drift before it becomes an outage

### Critical

- destination: on-call paging path
- expected response: immediate triage
- purpose: active incident or near-incident

## Cedar Compatibility

The VEuPathDB monorepo references Cedar as a server/workflow environment, not as a dedicated observability backend. Keep using this same metadata there as well:

- severity
- team
- surface
- class
- metric
- runbook

That keeps the alert intent portable even when routing and operational policy differ across local, staging, production, and Cedar-hosted environments.

## What Should Stay Environment-Specific

- notification channels
- on-call schedules
- escalation rules
- maintenance windows
- mute rules

Those details should not live in the shared observability pack.
