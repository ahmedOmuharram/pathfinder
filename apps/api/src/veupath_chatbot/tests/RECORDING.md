# VCR Cassette Recording Guide

## Overview

Integration tests use [VCR.py](https://vcrpy.readthedocs.io/) via
[pytest-recording](https://github.com/kiwicom/pytest-recording) to record
and replay HTTP interactions with VEuPathDB's WDK API.

Cassettes are YAML files in `cassettes/` that store request-response pairs.
Tests replay from cassettes by default (no network needed).

## Quick Reference

### Run tests (replay mode -- default)
```bash
cd apps/api
uv run pytest src/veupath_chatbot/tests/integration/ -v
```

### Record ALL cassettes from scratch
```bash
cd apps/api
WDK_AUTH_EMAIL=your@email.com WDK_AUTH_PASSWORD=yourpassword \
uv run pytest src/veupath_chatbot/tests/integration/ -v --record-mode=all -p no:xdist
```

### Record only new/missing cassettes
```bash
cd apps/api
WDK_AUTH_EMAIL=your@email.com WDK_AUTH_PASSWORD=yourpassword \
uv run pytest src/veupath_chatbot/tests/integration/test_your_file.py -v --record-mode=new_episodes
```

### Add a new VCR test
```bash
cd apps/api
WDK_AUTH_EMAIL=your@email.com WDK_AUTH_PASSWORD=yourpassword \
uv run pytest src/veupath_chatbot/tests/integration/test_your_new_file.py -v --record-mode=new_episodes
```

## Recording Modes

| Mode | When | Behavior |
|------|------|----------|
| `none` | CI, normal dev (default) | Replay only. Fails on unrecorded requests. |
| `all` | Refresh all cassettes | Re-record everything from scratch. |
| `new_episodes` | Adding new tests | Replay existing, record new. |

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `WDK_AUTH_EMAIL` | For recording | WDK account email |
| `WDK_AUTH_PASSWORD` | For recording | WDK account password |

Not needed for replay -- cassettes respond regardless of auth.

## Security

Cassettes are automatically scrubbed before storage:
- Auth cookies (Authorization, JSESSIONID, wdk_check_auth) -> `SCRUBBED`
- User IDs (`/users/{id}/`) -> `/users/0/`
- PII (email, name, org) -> generic test values
- JWTs -> `JWT_SCRUBBED`
- Login credentials (password, email in request bodies) -> scrubbed
- Large arrays (>25 items) -> trimmed to 25 items

## Maintenance Scripts

### Audit for leaked secrets
```bash
cd apps/api
uv run python scripts/audit_cassettes.py
```

### Trim oversized cassettes
```bash
cd apps/api
uv run python scripts/trim_cassettes.py --dry-run  # Preview
uv run python scripts/trim_cassettes.py             # Apply
```

## Writing New VCR Tests

```python
import pytest
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.tests.conftest import create_taxon_step, materialize_step


class TestMyFeature:
    @pytest.mark.vcr
    async def test_something(self, wdk_api: StrategyAPI) -> None:
        step = await create_taxon_step(wdk_api)
        await materialize_step(wdk_api, step.id)
        # ... test logic using wdk_api ...
```

### Available fixtures
- `wdk_api` -- Real `StrategyAPI` pointing at a deterministic VEuPathDB site
- `temp_results_api` -- Properly initialized `TemporaryResultsAPI`
- `wdk_test_site` -- Returns `(site_id, base_url)` tuple

### Shared helpers
- `create_taxon_step(api)` -- Creates a GenesByTaxon step for P. falciparum 3D7
- `materialize_step(api, step_id)` -- Creates a strategy to materialize step results
