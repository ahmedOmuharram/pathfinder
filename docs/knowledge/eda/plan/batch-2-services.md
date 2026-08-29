---
type: Plan
title: "EDA batch 2: services and catalog"
description: The study catalog with its embedding index, analysis authoring with one serialization call site, compute orchestration over the six-state job machine, and the parameter-presence predicate that finds an EDA-backed search - three implementers, two verifiers.
tags: [eda, pathfinder, plan, batch, services, catalog, embeddings, authoring, compute]
generated: { by: claude-code/opus-5, at: 2026-08-28T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-28T00:00:00Z }
status: accepted
---

# EDA batch 2: services and catalog

**Goal.** Put every EDA decision that is business logic - which study, which
filters, is the count real, which compute, which rows pass the thresholds, is
this WDK search EDA-backed - behind `services/eda/` and `services/catalog/`, so
the agent tools of batch 3 are thin wrappers with nothing to decide.

**Prerequisites.** Batch 1 closed by the session lead. Every name in batch 1's
Produces blocks exists and its tests are green.

**Read first:** [overview.md](overview.md), then
[batch-1-integration-foundation.md](batch-1-integration-foundation.md) (the
interfaces this batch consumes) and
[../pathfinder-architecture-fit.md](../pathfinder-architecture-fit.md) sections
1.3, 4.1, 4.2 and 4.3. The wire truths come from
[../genomics-and-wdk-relations.md](../genomics-and-wdk-relations.md),
[../eda-wdk-bridge.md](../eda-wdk-bridge.md),
[../computes-and-jobs.md](../computes-and-jobs.md),
[../visualizations.md](../visualizations.md),
[../notebook-presets.md](../notebook-presets.md),
[../data-model.md](../data-model.md) and
[../filters.md](../filters.md).

## Inherited constraints

- **TDD is non-negotiable.** Failing test first, always.
- **Pydantic maximalism.** No raw dicts across a boundary, no `isinstance`
  chains, no `getattr` with a default, no `hasattr`, no `dict.get` ladders.
  Matching a discriminated union with `match` is the union's own idiom and is
  allowed; branching on `type(x)` is not.
- **No type suppressions, no `noqa`, no `import as`, no backwards compatibility.**
- **Comments: 1 to 3 lines, ASD-STE100, near zero.** No history, no incidents,
  no narration.
- **ASCII punctuation only.**
- **Python 3.14.** `except ValueError, TypeError:` is valid.
- **Import-linter:** `pathfinder.services` may not import
  `pathfinder.transport` or `pathfinder.ai`. Services may import
  `pathfinder.integrations`, `pathfinder.domain` and `pathfinder.persistence`.
- **Only the LLM is mocked.** EDA fixtures are recorded real responses.
- **Never read a `.env` file.**
- **The serialization rule for this batch, and it is a hard one.**
  `services/eda/authoring.py::serialize_spec` is the ONLY place in the
  repository that turns an `EdaNewAnalysis` into the `eda_analysis_spec` string.
  One call site, so there is one answer to "what exactly went into the
  parameter". A second `model_dump_json` of an analysis anywhere is a FAIL.
- **Definition of done.** Gates green plus zero debt plus adjacent
  reconciliation plus tests that assert correctness. The recap leads with
  remaining debt.

**Gate ladder for every task:**

```bash
cd apps/api && uv run ruff check src/ \
  && uv run mypy --strict src/pathfinder/ \
  && uv run pyright src/pathfinder/ \
  && uv run pytest <the exact test files this task touched> -v
```

**Section-end:**

```bash
cd apps/api && uv run pytest src/pathfinder/tests/unit/ -v \
  && uv run pytest src/pathfinder/tests/integration/eda/ -v \
  && uv run lint-imports
```

---

## Implementer A: `services/eda/catalog.py` - the study catalog

### Files

| Action | Path |
|---|---|
| Create | `apps/api/src/pathfinder/services/eda/__init__.py` |
| Create | `apps/api/src/pathfinder/services/eda/catalog.py` |
| Create | `apps/api/src/pathfinder/integrations/embeddings/study_index.py` |
| Create | `apps/api/src/pathfinder/tests/unit/services/eda/__init__.py` |
| Create | `apps/api/src/pathfinder/tests/unit/services/eda/test_study_cache_key.py` |
| Create | `apps/api/src/pathfinder/tests/unit/services/eda/test_dataset_resolution.py` |
| Create | `apps/api/src/pathfinder/tests/unit/integrations/embeddings/test_study_index.py` |
| Create | `apps/api/src/pathfinder/tests/integration/eda/test_study_catalog.py` |

### Interfaces

**Consumes** (batch 1): `pathfinder.integrations.eda.factory.get_eda_client`,
`pathfinder.integrations.eda.client.EdaClient`, and from
`pathfinder.integrations.eda.models`: `EdaStudyOverview`, `EdaStudyDetail`,
`EdaPermissionEntry`, `EdaActionAuthorization`. From the repository:
`assistant_core.embeddings.model.MODEL_NAME`,
`assistant_core.embeddings.model.get_embedding_model`,
`assistant_core.embeddings.prefixes.SEARCH_DOCUMENT_PREFIX`,
`assistant_core.embeddings.prefixes.SEARCH_QUERY_PREFIX`,
`pathfinder.integrations.embeddings.semantic_index.set_cache_dir`.

**Produces:**

```python
# integrations/embeddings/study_index.py
@dataclass
class StudyIndexEntry:
    dataset_id: str
    enriched_text: str
    # no study id here: the index never resolves, only ranks
    @property
    def cache_key(self) -> str

@dataclass
class StudySemanticIndex:
    site_id: str = ""
    entries: list[StudyIndexEntry] = ...
    embeddings: NDArray[Any] | None = None
    async def build(self, studies: Sequence[EdaStudyOverview]) -> None
    def query(self, query_text: str, top_k: int = 10) -> list[tuple[str, float]]

def study_enriched_text(study: EdaStudyOverview) -> str

# services/eda/catalog.py
@dataclass(frozen=True, slots=True)
class StudyCard:
    dataset_id: str
    study_id: str
    display_name: str
    short_display_name: str
    description: str
    source_type: str
    relevance: float = 0.0
    can_subset: bool = False
    can_export_rows: bool = False

def study_cache_key(*, base_url: str, study: EdaStudyOverview) -> str
async def list_studies(site_id: str) -> list[EdaStudyOverview]
async def search_studies(site_id: str, query: str, limit: int = 10) -> list[StudyCard]
async def resolve_dataset(site_id: str, dataset_id: str) -> EdaPermissionEntry
async def get_study_detail(site_id: str, study: EdaStudyOverview) -> EdaStudyDetail
    # cached under study_cache_key: only the overview carries the version signal
async def get_study_detail_for_dataset(site_id: str, dataset_id: str
                                       ) -> tuple[EdaPermissionEntry, EdaStudyDetail]
def clear_study_caches() -> None

class UnknownEdaDatasetError(Exception)   # carries dataset_id and guidance
```

---

### Task A1 - the cache key, and the empty-`sha1hash` exception

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/services/eda/test_study_cache_key.py`:

```python
from __future__ import annotations

from pathfinder.integrations.eda.models import EdaStudyOverview
from pathfinder.services.eda.catalog import study_cache_key


def _study(*, sha: str, modified: str) -> EdaStudyOverview:
    return EdaStudyOverview(
        id="STUDY_x",
        dataset_id="DS_x",
        sha1hash=sha,
        source_type="curated" if sha else "user_submitted",
        display_name="x",
        last_modified=modified,
    )


def test_a_curated_study_keys_on_its_content_hash() -> None:
    key = study_cache_key(
        base_url="https://plasmodb.org/eda",
        study=_study(sha="abc123", modified="2026-05-27T20:00:00-04:00"),
    )
    assert "abc123" in key
    assert "2026-05-27" not in key


def test_a_user_study_keys_on_last_modified_because_the_hash_is_empty() -> None:
    """All 12 user_submitted studies live carry sha1hash == ""."""
    key = study_cache_key(
        base_url="https://plasmodb.org/eda",
        study=_study(sha="", modified="2026-05-27T20:00:00-04:00"),
    )
    assert "2026-05-27T20:00:00-04:00" in key


def test_the_base_url_is_part_of_the_key() -> None:
    """A study id is only meaningful together with its deployment."""
    plasmo = study_cache_key(
        base_url="https://plasmodb.org/eda",
        study=_study(sha="abc123", modified="m"),
    )
    clinepi = study_cache_key(
        base_url="https://clinepidb.org/eda",
        study=_study(sha="abc123", modified="m"),
    )
    assert plasmo != clinepi


def test_a_user_study_with_a_new_last_modified_gets_a_new_key() -> None:
    first = study_cache_key(
        base_url="b", study=_study(sha="", modified="2026-05-27T20:00:00-04:00")
    )
    second = study_cache_key(
        base_url="b", study=_study(sha="", modified="2026-05-28T20:00:00-04:00")
    )
    assert first != second
```

- [ ] **Run it.** Expect
      `ModuleNotFoundError: No module named 'pathfinder.services.eda'`.

- [ ] **Implementation.** Create
      `apps/api/src/pathfinder/services/eda/__init__.py` empty and
      `apps/api/src/pathfinder/services/eda/catalog.py` starting with:

```python
"""The EDA study catalog: browse, search, and resolve a dataset to a study."""

from __future__ import annotations

from pathfinder.integrations.eda.models import EdaStudyOverview


def study_cache_key(*, base_url: str, study: EdaStudyOverview) -> str:
    """Content address of a study's fetched metadata.

    A user study carries an empty ``sha1hash``, so ``lastModified`` is the only
    version signal it has.
    """
    version = study.sha1hash or study.last_modified
    return f"{base_url}|{study.id}|{version}"
```

- [ ] **Gates**, with
      `src/pathfinder/tests/unit/services/eda/test_study_cache_key.py`.

---

### Task A2 - dataset resolution through `/permissions` only

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/services/eda/test_dataset_resolution.py`:

```python
"""Dataset to study resolution, and the permission flags that gate an answer."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from pathfinder.integrations.eda.client import EdaClient
from pathfinder.services.eda import catalog
from pathfinder.platform.context import veupathdb_auth_token_ctx

FIXTURES = (
    Path(__file__).resolve().parents[2]
    / "integrations"
    / "eda"
    / "fixtures"
)

pytestmark = pytest.mark.asyncio


def _permissions() -> object:
    return json.loads((FIXTURES / "permissions.json").read_text())


@pytest.fixture(autouse=True)
def _clean_caches() -> None:
    catalog.clear_study_caches()


@pytest.fixture
def eda_client(monkeypatch: pytest.MonkeyPatch) -> EdaClient:
    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(
        httpx.MockTransport(lambda _r: httpx.Response(200, json=_permissions()))
    )
    monkeypatch.setattr(catalog, "get_eda_client", lambda _site: client)
    return client


@pytest.fixture(autouse=True)
def _token() -> None:
    token = veupathdb_auth_token_ctx.set("t")
    yield
    veupathdb_auth_token_ctx.reset(token)


async def test_a_known_dataset_resolves_to_its_study_id(eda_client: EdaClient) -> None:
    entry = await catalog.resolve_dataset("plasmodb", "DS_53f554ec6a")
    assert entry.study_id == "STUDY_53f554ec6a"
    await eda_client.close()


async def test_resolution_never_derives_the_study_id_from_the_dataset_id(
    eda_client: EdaClient,
) -> None:
    """STUDY_<suffix> equals DS_<suffix> for only 684 of 747 curated studies."""
    entry = await catalog.resolve_dataset("plasmodb", "DS_eeca6a5476")
    assert entry.study_id == "STUDY_fd06cb37d3"
    await eda_client.close()


async def test_an_unknown_dataset_raises_with_the_id_named(
    eda_client: EdaClient,
) -> None:
    with pytest.raises(catalog.UnknownEdaDatasetError) as excinfo:
        await catalog.resolve_dataset("plasmodb", "EDAUD_slI5M0RwIg0Zw")
    assert "EDAUD_slI5M0RwIg0Zw" in str(excinfo.value)
    await eda_client.close()


async def test_resolution_is_cached_per_site_so_one_call_serves_a_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json=_permissions())

    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(httpx.MockTransport(handler))
    monkeypatch.setattr(catalog, "get_eda_client", lambda _site: client)

    await catalog.resolve_dataset("plasmodb", "DS_53f554ec6a")
    await catalog.resolve_dataset("plasmodb", "DS_66f9e70b8a")
    await client.close()
    assert calls == ["/eda/permissions"]


async def test_clearing_the_cache_forces_a_refetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json=_permissions())

    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(httpx.MockTransport(handler))
    monkeypatch.setattr(catalog, "get_eda_client", lambda _site: client)

    await catalog.resolve_dataset("plasmodb", "DS_53f554ec6a")
    catalog.clear_study_caches()
    await catalog.resolve_dataset("plasmodb", "DS_53f554ec6a")
    await client.close()
    assert len(calls) == 2
```

- [ ] **Run it.** Expect
      `AttributeError: module ... has no attribute 'resolve_dataset'`.

- [ ] **Implementation.** Append to `services/eda/catalog.py`:

```python
class UnknownEdaDatasetError(Exception):
    """A dataset with no ``perDataset`` entry for this user.

    Resolution and authorization are the same call, so an inaccessible dataset
    and a nonexistent one are one case.
    """

    def __init__(self, dataset_id: str, known: Sequence[str]) -> None:
        self.dataset_id = dataset_id
        self.guidance = (
            f"Dataset {dataset_id!r} has no entry in this account's EDA "
            f"permissions, so it does not exist or is not accessible. "
            f"{len(known)} datasets are available; search for one by name "
            f"instead of guessing an id."
        )
        super().__init__(self.guidance)


@dataclass
class _SiteCaches:
    """Per-site reads that are stable for a turn."""

    permissions: dict[str, EdaPermissionEntry] | None = None
    studies: list[EdaStudyOverview] | None = None
    details: dict[str, EdaStudyDetail] = field(default_factory=dict)
    index: StudySemanticIndex | None = None


_caches: dict[str, _SiteCaches] = {}


def clear_study_caches() -> None:
    """Drop every cached EDA read. A test must not inherit one."""
    _caches.clear()


def _site_cache(site_id: str) -> _SiteCaches:
    return _caches.setdefault(site_id, _SiteCaches())


async def _permissions(site_id: str) -> dict[str, EdaPermissionEntry]:
    cache = _site_cache(site_id)
    if cache.permissions is None:
        cache.permissions = await get_eda_client(site_id).get_permissions()
    return cache.permissions


async def resolve_dataset(site_id: str, dataset_id: str) -> EdaPermissionEntry:
    """The dataset's permission entry, which carries its study id.

    Resolution goes through ``/permissions`` and nothing else. The id suffixes
    agree for most curated studies and not for all of them.
    """
    per_dataset = await _permissions(site_id)
    entry = per_dataset.get(dataset_id)
    if entry is None:
        raise UnknownEdaDatasetError(dataset_id, sorted(per_dataset))
    return entry


async def get_study_detail(site_id: str, study: EdaStudyOverview) -> EdaStudyDetail:
    """The full entity tree, cached per site for the turn."""
    cache = _site_cache(site_id)
    detail = cache.details.get(study_id)
    if detail is None:
        detail = await get_eda_client(site_id).get_study(study_id)
        cache.details[study_id] = detail
    return detail


async def get_study_detail_for_dataset(
    site_id: str,
    dataset_id: str,
) -> tuple[EdaPermissionEntry, EdaStudyDetail]:
    """The two reads every authoring call needs, in the one order that works."""
    entry = await resolve_dataset(site_id, dataset_id)
    return entry, await get_study_detail(site_id, entry.study_id)
```

  `per_dataset.get(dataset_id)` is a single lookup on a typed
  `dict[str, EdaPermissionEntry]`, not a `dict.get` ladder over untyped JSON.
  That is the allowed use.

  The `_caches` dictionary must be cleared between tests. Add an autouse
  fixture in `apps/api/src/pathfinder/tests/conftest.py` beside
  `_close_wdk_clients_after_test` that calls `clear_study_caches()`; a
  process-wide cache a test inherits is a flaky test.

- [ ] **Gates**, with
      `src/pathfinder/tests/unit/services/eda/test_dataset_resolution.py`.

**Traps named:**

- Never compute a study id from a dataset id. `DS_eeca6a5476` maps to
  `STUDY_fd06cb37d3`; 63 of 747 curated studies disagree on the suffix.
- `perDataset` is a superset of `/studies` (880 against 759 live), so a dataset
  that resolves may have no `/studies` row. `resolve_dataset` must not consult
  the study list.
- The `EDAUD_slI5M0RwIg0Zw` id in the test is the sentinel vocabulary term (see
  implementer C, task C3). It resolves to nothing, and the 400 upstream says
  "could not be found for this user".

---

### Task A3 - the study embedding index

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/integrations/embeddings/test_study_index.py`:

```python
"""The study index reuses the search index's content-addressed cache shape."""

from __future__ import annotations

from pathlib import Path

import pytest
from assistant_core.embeddings.model import MODEL_NAME
from assistant_core.embeddings.prefixes import SEARCH_DOCUMENT_PREFIX

from pathfinder.integrations.eda.models import EdaStudyOverview
from pathfinder.integrations.embeddings.study_index import (
    StudyIndexEntry,
    StudySemanticIndex,
    study_enriched_text,
)

pytestmark = pytest.mark.asyncio


def _study(
    *,
    dataset_id: str,
    display: str,
    short: str | None = None,
    description: str | None = None,
) -> EdaStudyOverview:
    return EdaStudyOverview(
        id=dataset_id.replace("DS_", "STUDY_"),
        dataset_id=dataset_id,
        sha1hash="h",
        source_type="curated",
        display_name=display,
        short_display_name=short,
        description=description,
    )


def test_the_enriched_text_joins_the_three_name_fields() -> None:
    text = study_enriched_text(
        _study(
            dataset_id="DS_1",
            display="Heat shock response in sensitive mutants",
            short="Heat shock",
            description="<b>General Description:</b> Illumina sequencing",
        )
    )
    assert "Heat shock response in sensitive mutants" in text
    assert "Heat shock" in text
    assert "Illumina sequencing" in text
    assert "<b>" not in text


def test_a_study_with_no_short_name_and_no_description_still_has_text() -> None:
    text = study_enriched_text(_study(dataset_id="DS_1", display="Only a name"))
    assert text == "Only a name"


def test_a_short_name_equal_to_the_display_name_is_not_repeated() -> None:
    text = study_enriched_text(
        _study(dataset_id="DS_1", display="Same", short="Same")
    )
    assert text == "Same"


def test_the_cache_key_binds_the_model_the_prefix_and_the_text() -> None:
    entry = StudyIndexEntry(
        dataset_id="DS_1", study_id="STUDY_1", enriched_text="abc"
    )
    other = StudyIndexEntry(
        dataset_id="DS_2", study_id="STUDY_2", enriched_text="abc"
    )
    assert entry.cache_key == other.cache_key
    assert MODEL_NAME
    assert SEARCH_DOCUMENT_PREFIX
    changed = StudyIndexEntry(
        dataset_id="DS_1", study_id="STUDY_1", enriched_text="abd"
    )
    assert entry.cache_key != changed.cache_key


async def test_the_index_ranks_a_study_by_its_own_words(tmp_path: Path) -> None:
    from pathfinder.integrations.embeddings.semantic_index import set_cache_dir

    set_cache_dir(tmp_path)
    index = StudySemanticIndex(site_id="plasmodb-eda")
    await index.build(
        [
            _study(
                dataset_id="DS_heat",
                display="Heat shock response in sensitive mutants",
                description="febrile temperature RNA-Seq",
            ),
            _study(
                dataset_id="DS_pheno",
                display="Rodent malaria phenotype survey",
                description="gene modification success by species",
            ),
        ]
    )
    hits = index.query("heat shock temperature experiment", top_k=2)
    assert hits
    assert hits[0][0] == "DS_heat"


async def test_an_empty_study_list_builds_an_empty_index() -> None:
    index = StudySemanticIndex(site_id="empty")
    await index.build([])
    assert index.query("anything") == []
```

- [ ] **Run it.** Expect `ModuleNotFoundError`.

- [ ] **Implementation.** Create
      `apps/api/src/pathfinder/integrations/embeddings/study_index.py`. Copy the
      shape of `integrations/embeddings/semantic_index.py` exactly:
      `_load_cached_rows`, `_save_cache`, `_encode` and `_embed` are already
      generic over an entry's `cache_key` and `enriched_text`, so import and
      reuse them rather than writing a second copy.

```python
"""Semantic index over EDA study names and descriptions."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from assistant_core.embeddings.model import MODEL_NAME, get_embedding_model
from assistant_core.embeddings.prefixes import (
    SEARCH_DOCUMENT_PREFIX,
    SEARCH_QUERY_PREFIX,
)
from assistant_core.platform.logging import get_logger
from numpy.typing import NDArray

from pathfinder.integrations.eda.models import EdaStudyOverview
from pathfinder.integrations.embeddings.semantic_index import (
    encode_texts,
    load_cached_rows,
    save_cache,
)

logger = get_logger(__name__)

_TAG = re.compile(r"<[^>]+>")


def study_enriched_text(study: EdaStudyOverview) -> str:
    """The text a study is indexed by: its names first, then its description."""
    parts = [study.display_name]
    short = study.short_display_name or ""
    if short and short != study.display_name:
        parts.append(short)
    if study.description:
        parts.append(_TAG.sub(" ", study.description))
    return " ".join(p.strip() for p in parts if p and p.strip()).strip()


@dataclass
class StudyIndexEntry:
    """One study's row in the index."""

    dataset_id: str
    study_id: str
    enriched_text: str

    @property
    def cache_key(self) -> str:
        """Content address of this row. The model, the prefix and the text decide it."""
        payload = "\n".join((MODEL_NAME, SEARCH_DOCUMENT_PREFIX, self.enriched_text))
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class StudySemanticIndex:
    """Cosine-similarity index over study text."""

    site_id: str = ""
    entries: list[StudyIndexEntry] = field(default_factory=list)
    embeddings: NDArray[Any] | None = None

    async def build(self, studies: Sequence[EdaStudyOverview]) -> None:
        self.entries = [
            StudyIndexEntry(
                dataset_id=s.dataset_id,
                study_id=s.id,
                enriched_text=study_enriched_text(s),
            )
            for s in studies
        ]
        if not self.entries:
            self.embeddings = None
            return
        # One catalog content gives one entry sequence and one stored file.
        self.entries.sort(key=lambda e: e.dataset_id)
        cached = load_cached_rows(self.site_id)
        pending = [e for e in self.entries if e.cache_key not in cached]
        fresh = iter(await encode_texts([e.enriched_text for e in pending]))
        store: dict[str, NDArray[Any]] = {}
        rows: list[NDArray[Any]] = []
        for entry in self.entries:
            row = cached[entry.cache_key] if entry.cache_key in cached else next(fresh)
            rows.append(row)
            store[entry.cache_key] = row
        self.embeddings = np.array(rows)
        if pending or set(cached) != set(store):
            save_cache(self.site_id, store)
        logger.info(
            "EDA study index ready",
            site_id=self.site_id,
            num_entries=len(self.entries),
            encoded=len(pending),
        )

    def query(self, query_text: str, top_k: int = 10) -> list[tuple[str, float]]:
        """The top-k dataset ids by similarity, best first."""
        if self.embeddings is None or not self.entries:
            return []
        model = get_embedding_model()
        query_row = np.array(
            list(model.embed([f"{SEARCH_QUERY_PREFIX}{query_text}"]))
        )
        similarities = (self.embeddings @ query_row.T).flatten()
        ranked = np.argsort(similarities)[::-1][:top_k]
        return [
            (self.entries[i].dataset_id, float(similarities[i]))
            for i in ranked
            if float(similarities[i]) > 0.0
        ]
```

- [ ] **Extract the three shared helpers.** `semantic_index.py` currently keeps
      `_load_cached_rows`, `_save_cache` and `_encode` private, and `_encode`
      takes `list[SearchIndexEntry]`. In the same task:
      rename them to `load_cached_rows(site_id)`, `save_cache(site_id, rows)`
      and `encode_texts(texts: Sequence[str]) -> list[NDArray[Any]]`; change
      `_encode`'s body to take texts and have `SemanticSearchIndex.build` pass
      `[e.enriched_text for e in pending]`; update every call site inside
      `semantic_index.py`. The document prefix is applied inside `encode_texts`,
      once, so neither index can forget it. Run
      `src/pathfinder/tests/unit/integrations/embeddings/` and
      `src/pathfinder/tests/unit/integrations/test_semantic_index_cache.py`
      after the rename - those tests are the regression guard for this edit.

- [ ] **Gates**, with both embedding test paths.

**Trap named:** the prefixes are asymmetric on purpose. A document goes in with
`search_document: `, a query with `search_query: `. Prefix the TEXT, never the
model. `SEARCH_DOCUMENT_PREFIX` must appear in `cache_key` and in
`encode_texts`, and `SEARCH_QUERY_PREFIX` only in `query`.

---

### Task A4 - `search_studies` and the permission-aware card

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/integration/eda/test_study_catalog.py`:

```python
"""The study catalog answers with permission-aware cards."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from pathfinder.integrations.eda.client import EdaClient
from pathfinder.integrations.embeddings.semantic_index import set_cache_dir
from pathfinder.platform.context import veupathdb_auth_token_ctx
from pathfinder.services.eda import catalog

FIXTURES = (
    Path(__file__).resolve().parents[2]
    / "unit"
    / "integrations"
    / "eda"
    / "fixtures"
)

pytestmark = pytest.mark.asyncio


def _fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text())


def _route(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/permissions"):
        return httpx.Response(200, json=_fixture("permissions.json"))
    if request.url.path.endswith("/studies"):
        return httpx.Response(200, json=_fixture("studies_list.json"))
    return httpx.Response(404, json={"status": "not-found"})


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> EdaClient:
    set_cache_dir(tmp_path)
    catalog.clear_study_caches()
    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(httpx.MockTransport(_route))
    monkeypatch.setattr(catalog, "get_eda_client", lambda _site: client)
    token = veupathdb_auth_token_ctx.set("t")
    yield client
    veupathdb_auth_token_ctx.reset(token)


async def test_a_search_returns_cards_ordered_by_relevance(wired: EdaClient) -> None:
    cards = await catalog.search_studies("plasmodb", "RNA-Seq expression", limit=5)
    await wired.close()
    assert cards
    assert len(cards) <= 5
    assert cards == sorted(cards, key=lambda c: -c.relevance)
    assert all(c.dataset_id.startswith(("DS_", "EDAUD_")) for c in cards)


async def test_a_card_carries_the_study_id_from_permissions(wired: EdaClient) -> None:
    cards = await catalog.search_studies("plasmodb", "phenotype", limit=20)
    await wired.close()
    by_dataset = {c.dataset_id: c for c in cards}
    if "DS_53f554ec6a" in by_dataset:
        assert by_dataset["DS_53f554ec6a"].study_id == "STUDY_53f554ec6a"


async def test_a_card_reports_the_two_permission_axes(wired: EdaClient) -> None:
    """subsetting gates a count; resultsAll gates row output."""
    cards = await catalog.search_studies("plasmodb", "RNA-Seq", limit=20)
    await wired.close()
    assert any(c.can_subset for c in cards)
    assert all(isinstance(c.can_export_rows, bool) for c in cards)


async def test_a_study_absent_from_permissions_is_dropped_from_the_cards(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A study the account cannot see resolves to nothing, so it is not offered."""
    set_cache_dir(tmp_path)
    catalog.clear_study_caches()

    def route(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/permissions"):
            return httpx.Response(200, json={"perDataset": {}})
        if request.url.path.endswith("/studies"):
            return httpx.Response(200, json=_fixture("studies_list.json"))
        return httpx.Response(404, json={"status": "not-found"})

    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(httpx.MockTransport(route))
    monkeypatch.setattr(catalog, "get_eda_client", lambda _site: client)
    token = veupathdb_auth_token_ctx.set("t")
    try:
        cards = await catalog.search_studies("plasmodb", "RNA-Seq", limit=5)
    finally:
        veupathdb_auth_token_ctx.reset(token)
        await client.close()
    assert cards == []


async def test_the_index_is_built_once_per_site(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    set_cache_dir(tmp_path)
    catalog.clear_study_caches()
    calls: list[str] = []

    def route(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return _route(request)

    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(httpx.MockTransport(route))
    monkeypatch.setattr(catalog, "get_eda_client", lambda _site: client)
    token = veupathdb_auth_token_ctx.set("t")
    try:
        await catalog.search_studies("plasmodb", "one", limit=3)
        await catalog.search_studies("plasmodb", "two", limit=3)
    finally:
        veupathdb_auth_token_ctx.reset(token)
        await client.close()
    assert calls.count("/eda/studies") == 1
    assert calls.count("/eda/permissions") == 1
```

- [ ] **Run it.** Expect
      `AttributeError: module ... has no attribute 'search_studies'`.

- [ ] **Implementation.** Append to `services/eda/catalog.py`:

```python
@dataclass(frozen=True, slots=True)
class StudyCard:
    """One study as the agent and the tab see it."""

    dataset_id: str
    study_id: str
    display_name: str
    short_display_name: str
    description: str
    source_type: str
    relevance: float = 0.0
    can_subset: bool = False
    can_export_rows: bool = False


async def list_studies(site_id: str) -> list[EdaStudyOverview]:
    """The browsable catalog. It is not the study universe and not the resolver."""
    cache = _site_cache(site_id)
    if cache.studies is None:
        cache.studies = await get_eda_client(site_id).list_studies()
    return cache.studies


async def _index(site_id: str) -> StudySemanticIndex:
    cache = _site_cache(site_id)
    if cache.index is None:
        index = StudySemanticIndex(site_id=f"{site_id}-eda-studies")
        await index.build(await list_studies(site_id))
        cache.index = index
    return cache.index


async def search_studies(
    site_id: str,
    query: str,
    limit: int = 10,
) -> list[StudyCard]:
    """Rank the studies this account can see against a natural-language query."""
    per_dataset = await _permissions(site_id)
    by_dataset = {s.dataset_id: s for s in await list_studies(site_id)}
    index = await _index(site_id)
    cards: list[StudyCard] = []
    for dataset_id, score in index.query(query, top_k=limit * 3):
        entry = per_dataset.get(dataset_id)
        overview = by_dataset.get(dataset_id)
        if entry is None or overview is None:
            continue
        cards.append(
            StudyCard(
                dataset_id=dataset_id,
                study_id=entry.study_id,
                display_name=overview.display_name,
                short_display_name=overview.short_display_name or "",
                description=_plain(overview.description),
                source_type=overview.source_type,
                relevance=score,
                can_subset=entry.action_authorization.subsetting,
                can_export_rows=entry.action_authorization.results_all,
            )
        )
        if len(cards) >= limit:
            break
    return cards


def _plain(description: str | None) -> str:
    """The description without its inline markup, trimmed for a tool payload."""
    if not description:
        return ""
    return _TAG.sub(" ", description).strip()[:600]
```

  `_TAG` is the same compiled pattern as `study_index.py`; import
  `study_enriched_text`'s module-level `_TAG` is a private name, so declare the
  pattern once in `study_index.py` as a public `strip_markup(text: str) -> str`
  and call it from both. One answer to "remove the HTML".

  `per_dataset.get` and `by_dataset.get` are lookups on typed dictionaries the
  models produced, not `dict.get` over untyped JSON.

- [ ] **Gates**, with
      `src/pathfinder/tests/integration/eda/test_study_catalog.py`.

**Traps named:**

- `/studies` and `/permissions` are two calls with two purposes. The index is
  built from `/studies` and MUST NOT be used to resolve a dataset. 121 datasets
  live have a `studyId` and no `/studies` row.
- A card is only produced for a dataset present in BOTH answers. A study with no
  permission entry is not offered, because the account cannot subset it.
- `resultsAll` gates row output; `subsetting` gates a count. A study can be
  fully countable and refuse rows with a 403.

---

### Task A5 - section end

- [ ] Run the section-end ladder. Confirm the two new autouse fixtures
      (`clear_study_caches`, EDA client close) exist in
      `apps/api/src/pathfinder/tests/conftest.py` and that
      `uv run pytest src/pathfinder/tests/unit/ -v` passes twice in a row with
      `-p no:randomly` off and on, so no cache leaks between tests.

---

## Implementer B: `services/eda/authoring.py` and `services/eda/compute.py`

### Files

| Action | Path |
|---|---|
| Create | `apps/api/src/pathfinder/services/eda/authoring.py` |
| Create | `apps/api/src/pathfinder/services/eda/compute.py` |
| Create | `apps/api/src/pathfinder/tests/unit/services/eda/test_serialize_spec.py` |
| Create | `apps/api/src/pathfinder/tests/unit/services/eda/test_step_request.py` |
| Create | `apps/api/src/pathfinder/tests/unit/services/eda/test_volcano_thresholds.py` |
| Create | `apps/api/src/pathfinder/tests/integration/eda/test_authoring.py` |
| Create | `apps/api/src/pathfinder/tests/integration/eda/test_compute_polling.py` |

### Interfaces

**Consumes** (batch 1 and implementer A): every model from
`pathfinder.integrations.eda.models`; `EdaClient` and its methods;
`pathfinder.domain.eda` (`validate_filters`, `validate_compute_config`,
`find_gene_entity`, `walk_entities`, `DeclaredRanges`,
`GENE_EXPRESSION_VALUE_IDS`, `VEUPATHDB_GENE_ID`);
`pathfinder.services.eda.catalog` (`resolve_dataset`,
`get_study_detail_for_dataset`, `StudyCard`).

**Produces:**

```python
# services/eda/authoring.py
@dataclass(frozen=True, slots=True)
class SubsetPreview:
    entity_id: str
    entity_display_name: str
    count: int
    unfiltered_count: int
    distribution: EdaDistributionResponse | None

@dataclass(frozen=True, slots=True)
class AuthoringRejection:
    errors: list[str]

def new_analysis(*, dataset_id: str, display_name: str,
                 filters: Sequence[EdaFilter] = (),
                 computation: EdaComputation | None = None) -> EdaNewAnalysis
def declared_ranges(study: EdaStudyDetail) -> DeclaredRanges
def serialize_spec(analysis: EdaNewAnalysis) -> str
async def validate_subset(site_id: str, *, dataset_id: str,
                          filters: Sequence[EdaFilter]) -> list[str]
async def verified_count(site_id: str, *, dataset_id: str, entity_id: str,
                         filters: Sequence[EdaFilter]) -> int
async def preview_subset(site_id: str, *, dataset_id: str, entity_id: str,
                         filters: Sequence[EdaFilter],
                         distribution_variable_id: str | None = None) -> SubsetPreview
async def open_analysis(site_id: str, *, dataset_id: str,
                        display_name: str) -> str          # analysis id
async def apply_filters(site_id: str, *, analysis_id: str, dataset_id: str,
                        filters: Sequence[EdaFilter]) -> EdaAnalysisDetail
async def apply_computation(site_id: str, *, analysis_id: str, dataset_id: str,
                            computation: EdaComputation) -> EdaAnalysisDetail

class EdaStepRequest(CamelModel):
    eda_dataset_id: str
    eda_analysis_spec: str
    # @model_validator(mode="after") enforces spec.studyId == eda_dataset_id
    def wdk_parameters(self) -> dict[str, str]

# services/eda/compute.py
@dataclass(frozen=True, slots=True)
class RetainedSummary:
    total_rows: int
    unparseable_rows: int
    retained: int
    retained_up: int
    retained_down: int

TERMINAL_STATUSES: frozenset[EdaJobStatus]
RUNNING_STATUSES: frozenset[EdaJobStatus]

def retained_summary(stats: VolcanoStatsResponse, *,
                     effect_size_threshold: float,
                     significance_threshold: float,
                     effect_direction: str = "upAndDown") -> RetainedSummary
def retained_point_ids(stats: VolcanoStatsResponse, *,
                       effect_size_threshold: float,
                       significance_threshold: float,
                       effect_direction: str = "upAndDown") -> list[str]
async def lookup_job(site_id: str, *, compute_name: str, study_id: str,
                     config: EdaDifferentialExpressionConfig,
                     filters: Sequence[EdaFilter]) -> EdaComputeJob
async def submit_compute(...) -> EdaComputeJob            # autostart=True
async def poll_job(site_id: str, *, job_id: str) -> EdaComputeJob
async def read_statistics(...) -> VolcanoStatsResponse
```

---

### Task B1 - `serialize_spec`, the one call site

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/services/eda/test_serialize_spec.py`:

```python
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pathfinder.integrations.eda.models import (
    EdaComparator,
    EdaComputation,
    EdaComputationDescriptor,
    EdaDifferentialExpressionConfig,
    EdaLabeledRange,
    EdaStringSetFilter,
    EdaVariableSpec,
    EdaVisualization,
    EdaVolcanoConfiguration,
    EdaVolcanoDescriptor,
)
from pathfinder.services.eda.authoring import new_analysis, serialize_spec

REPO = Path(__file__).resolve().parents[6]


def test_no_filters_serializes_to_the_empty_string_not_a_json_object() -> None:
    """An empty eda_analysis_spec is legal and means no filters."""
    analysis = new_analysis(dataset_id="DS_x", display_name="x")
    assert serialize_spec(analysis) == ""


def test_a_filter_makes_the_spec_a_json_string_naming_the_dataset_id() -> None:
    analysis = new_analysis(
        dataset_id="DS_53f554ec6a",
        display_name="berghei subset",
        filters=[
            EdaStringSetFilter(
                entity_id="GENE_PHENOTYPE_DATA_ENTITY",
                variable_id="VAR_035294d0",
                string_set=["P. berghei"],
            )
        ],
    )
    spec = serialize_spec(analysis)
    parsed = json.loads(spec)
    assert parsed["studyId"] == "DS_53f554ec6a"
    assert parsed["descriptor"]["subset"]["descriptor"][0]["stringSet"] == [
        "P. berghei"
    ]


def test_the_serialized_spec_carries_no_null_valued_key() -> None:
    analysis = new_analysis(dataset_id="DS_x", display_name="x",
                            filters=[
                                EdaStringSetFilter(
                                    entity_id="E", variable_id="V", string_set=["a"]
                                )
                            ])
    parsed = json.loads(serialize_spec(analysis))
    assert _no_nulls(parsed)


def _no_nulls(node: object) -> bool:
    if isinstance(node, dict):
        return all(v is not None and _no_nulls(v) for v in node.values())
    if isinstance(node, list):
        return all(_no_nulls(v) for v in node)
    return True


def test_a_computation_serializes_with_its_volcano_thresholds() -> None:
    analysis = new_analysis(
        dataset_id="DS_e973eadd57",
        display_name="de",
        computation=EdaComputation(
            computation_id="de1",
            descriptor=EdaComputationDescriptor(
                configuration=EdaDifferentialExpressionConfig(
                    identifier_variable=EdaVariableSpec(
                        entity_id="ENT_fd574cd6", variable_id="VEUPATHDB_GENE_ID"
                    ),
                    value_variable=EdaVariableSpec(
                        entity_id="ENT_fd574cd6",
                        variable_id="SEQUENCE_READ_COUNT_SENSE",
                    ),
                    comparator=EdaComparator(
                        variable=EdaVariableSpec(
                            entity_id="ENT_8151325d", variable_id="VAR_081ab087"
                        ),
                        group_a=[EdaLabeledRange(label="normal")],
                        group_b=[EdaLabeledRange(label="febrile")],
                    ),
                )
            ),
            visualizations=[
                EdaVisualization(
                    visualization_id="v1",
                    display_name="Volcano",
                    descriptor=EdaVolcanoDescriptor(
                        configuration=EdaVolcanoConfiguration(
                            effect_size_threshold=1.0,
                            significance_threshold=0.05,
                        )
                    ),
                )
            ],
        ),
    )
    parsed = json.loads(serialize_spec(analysis))
    viz = parsed["descriptor"]["computations"][0]["visualizations"][0]["descriptor"]
    assert viz["type"] == "volcanoplot"
    assert viz["configuration"]["effectSizeThreshold"] == 1.0
    assert viz["configuration"]["significanceThreshold"] == 0.05
    assert viz["configuration"]["effectDirection"] == "upAndDown"


def test_serialize_spec_is_the_only_place_an_analysis_is_dumped_to_json() -> None:
    """One call site, so there is one answer to what went into the parameter."""
    hits = subprocess.run(
        [
            "grep",
            "-rn",
            "model_dump_json",
            "apps/api/src/pathfinder/services/eda",
            "apps/api/src/pathfinder/ai",
            "apps/api/src/pathfinder/jobs",
            "apps/api/src/pathfinder/transport",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.splitlines()
    analysis_dumps = [line for line in hits if "authoring.py" not in line]
    assert analysis_dumps == [], analysis_dumps
```

- [ ] **Run it.** Expect `ModuleNotFoundError: ...services.eda.authoring`.

- [ ] **Implementation.** Create
      `apps/api/src/pathfinder/services/eda/authoring.py`:

```python
"""Authoring an EDA analysis, and the one place its spec becomes a string."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from assistant_core.platform.pydantic_base import CamelModel
from pydantic import model_validator

from pathfinder.integrations.eda.models import (
    EdaAnalysisDescriptor,
    EdaComputation,
    EdaFilter,
    EdaNewAnalysis,
    EdaSubsetDescriptor,
)


def new_analysis(
    *,
    dataset_id: str,
    display_name: str,
    filters: Sequence[EdaFilter] = (),
    computation: EdaComputation | None = None,
) -> EdaNewAnalysis:
    """Build the analysis document. ``dataset_id`` lands in the misnamed field."""
    return EdaNewAnalysis(
        study_id=dataset_id,
        display_name=display_name,
        descriptor=EdaAnalysisDescriptor(
            subset=EdaSubsetDescriptor(descriptor=list(filters)),
            computations=[computation] if computation is not None else [],
        ),
    )


def serialize_spec(analysis: EdaNewAnalysis) -> str:
    """The ``eda_analysis_spec`` parameter value for this analysis.

    An analysis with no filters and no computation serializes to the empty
    string: the plugin synthesizes a full empty descriptor, and the literal
    ``{}`` is not what it expects.
    """
    descriptor = analysis.descriptor
    if not descriptor.subset.descriptor and not descriptor.computations:
        return ""
    return analysis.model_dump_json(by_alias=True, exclude_none=True)
```

- [ ] **Gates**, with
      `src/pathfinder/tests/unit/services/eda/test_serialize_spec.py`.

**Traps named:**

- The empty case is the empty string, never `"{}"`, never `"null"`.
- `exclude_none=True` is what keeps `studyVersion` and `apiVersion` out of the
  string when they are unset. Do not swap it for `exclude_unset`.
- The `grep` test is a real gate. Any second `model_dump_json` on an analysis
  fails it, including one added in batch 3.

---

### Task B2 - `EdaStepRequest` and the `studyId` equality validator

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/services/eda/test_step_request.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from pathfinder.integrations.eda.models import EdaStringSetFilter
from pathfinder.services.eda.authoring import (
    EdaStepRequest,
    new_analysis,
    serialize_spec,
)


def _spec(dataset_id: str) -> str:
    return serialize_spec(
        new_analysis(
            dataset_id=dataset_id,
            display_name="x",
            filters=[
                EdaStringSetFilter(entity_id="E", variable_id="V", string_set=["a"])
            ],
        )
    )


def test_a_matching_dataset_id_is_accepted() -> None:
    request = EdaStepRequest(
        eda_dataset_id="DS_53f554ec6a", eda_analysis_spec=_spec("DS_53f554ec6a")
    )
    assert request.eda_dataset_id == "DS_53f554ec6a"


def test_a_mismatched_dataset_id_is_refused_before_wdk_sees_it() -> None:
    """The plugin requires spec.studyId to equal eda_dataset_id."""
    with pytest.raises(ValidationError) as excinfo:
        EdaStepRequest(
            eda_dataset_id="DS_66f9e70b8a", eda_analysis_spec=_spec("DS_53f554ec6a")
        )
    message = str(excinfo.value)
    assert "DS_66f9e70b8a" in message
    assert "DS_53f554ec6a" in message


def test_an_empty_spec_is_accepted_and_means_no_filters() -> None:
    request = EdaStepRequest(eda_dataset_id="DS_x", eda_analysis_spec="")
    assert request.eda_analysis_spec == ""


def test_a_study_id_in_the_spec_is_refused_because_both_are_dataset_ids() -> None:
    with pytest.raises(ValidationError) as excinfo:
        EdaStepRequest(
            eda_dataset_id="DS_e973eadd57",
            eda_analysis_spec=_spec("STUDY_e973eadd57"),
        )
    assert "dataset id" in str(excinfo.value)


def test_the_wdk_parameters_are_two_strings() -> None:
    request = EdaStepRequest(
        eda_dataset_id="DS_53f554ec6a", eda_analysis_spec=_spec("DS_53f554ec6a")
    )
    params = request.wdk_parameters()
    assert set(params) == {"eda_dataset_id", "eda_analysis_spec"}
    assert all(isinstance(v, str) for v in params.values())


def test_unparseable_spec_json_is_refused() -> None:
    with pytest.raises(ValidationError):
        EdaStepRequest(eda_dataset_id="DS_x", eda_analysis_spec="{not json")
```

- [ ] **Run it.** Expect `ImportError: cannot import name 'EdaStepRequest'`.

- [ ] **Implementation.** Append to `authoring.py`:

```python
_DATASET_PREFIXES = ("DS_", "EDAUD_")


class EdaStepRequest(CamelModel):
    """The two WDK parameters that carry an EDA subset into a step."""

    eda_dataset_id: str
    eda_analysis_spec: str

    @model_validator(mode="after")
    def _spec_names_the_same_dataset(self) -> EdaStepRequest:
        if not self.eda_analysis_spec:
            return self
        spec = EdaNewAnalysis.model_validate_json(self.eda_analysis_spec)
        if spec.study_id == self.eda_dataset_id:
            return self
        msg = (
            f"The analysis spec names {spec.study_id!r} and the step names "
            f"{self.eda_dataset_id!r}. Both values are a dataset id, not a "
            f"study id."
        )
        raise ValueError(msg)

    def wdk_parameters(self) -> dict[str, str]:
        """The step's ``parameters`` map, ready for ``WDKSearchConfig``."""
        return {
            "eda_dataset_id": self.eda_dataset_id,
            "eda_analysis_spec": self.eda_analysis_spec,
        }
```

  `EdaNewAnalysis.model_validate_json` also covers the unparseable case: a bad
  string is a `ValidationError` from the nested model, which is exactly the
  refusal the test asserts. The "dataset id" phrase must appear in the message,
  because the `STUDY_` case is the one a model gets wrong and the message is what
  teaches it.

- [ ] **Gates**, with
      `src/pathfinder/tests/unit/services/eda/test_step_request.py`.

---

### Task B3 - validation and `verified_count`

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/integration/eda/test_authoring.py`:

```python
"""Authoring runs the pure predicates, then verifies with a real count."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from pathfinder.integrations.eda.client import EdaClient
from pathfinder.integrations.eda.models import EdaStringSetFilter
from pathfinder.platform.context import veupathdb_auth_token_ctx
from pathfinder.services.eda import authoring, catalog

FIXTURES = (
    Path(__file__).resolve().parents[2]
    / "unit"
    / "integrations"
    / "eda"
    / "fixtures"
)

pytestmark = pytest.mark.asyncio

_DATASET = "DS_53f554ec6a"
_STUDY = "STUDY_53f554ec6a"
_ENTITY = "GENE_PHENOTYPE_DATA_ENTITY"


def _fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text())


def _route(counts: list[int]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/permissions"):
            return httpx.Response(200, json=_fixture("permissions.json"))
        if path == f"/eda/studies/{_STUDY}":
            return httpx.Response(200, json=_fixture("study_detail_phenotype.json"))
        if path.endswith("/count"):
            return httpx.Response(200, json={"count": counts.pop(0)})
        if path.endswith("/distribution"):
            return httpx.Response(
                200, json=_fixture("distribution_categorical.json")
            )
        return httpx.Response(404, json={"status": "not-found"})

    return httpx.MockTransport(handler)


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch) -> EdaClient:
    catalog.clear_study_caches()
    client = EdaClient(base_url="https://plasmodb.org/eda")
    monkeypatch.setattr(catalog, "get_eda_client", lambda _s: client)
    monkeypatch.setattr(authoring, "get_eda_client", lambda _s: client)
    token = veupathdb_auth_token_ctx.set("t")
    yield client
    veupathdb_auth_token_ctx.reset(token)


def _species(value: str) -> EdaStringSetFilter:
    return EdaStringSetFilter(
        entity_id=_ENTITY, variable_id="VAR_035294d0", string_set=[value]
    )


async def test_a_valid_filter_array_reports_no_errors(wired: EdaClient) -> None:
    wired.install_transport(_route([]))
    errors = await authoring.validate_subset(
        "plasmodb", dataset_id=_DATASET, filters=[_species("P. berghei")]
    )
    await wired.close()
    assert errors == []


async def test_an_out_of_vocabulary_value_is_reported_without_a_wire_call(
    wired: EdaClient,
) -> None:
    """The service would answer 200 with count 0, so validation is the only guard."""
    wired.install_transport(_route([]))
    errors = await authoring.validate_subset(
        "plasmodb", dataset_id=_DATASET, filters=[_species("P. vivax")]
    )
    await wired.close()
    assert len(errors) == 1
    assert "P. vivax" in errors[0]


async def test_the_verified_count_is_the_service_answer(wired: EdaClient) -> None:
    wired.install_transport(_route([4011]))
    count = await authoring.verified_count(
        "plasmodb",
        dataset_id=_DATASET,
        entity_id=_ENTITY,
        filters=[_species("P. berghei")],
    )
    await wired.close()
    assert count == 4011


async def test_a_verified_count_of_zero_is_reported_not_swallowed(
    wired: EdaClient,
) -> None:
    wired.install_transport(_route([0]))
    count = await authoring.verified_count(
        "plasmodb",
        dataset_id=_DATASET,
        entity_id=_ENTITY,
        filters=[_species("P. berghei")],
    )
    await wired.close()
    assert count == 0


async def test_the_preview_carries_both_counts_and_a_distribution(
    wired: EdaClient,
) -> None:
    wired.install_transport(_route([4011, 4279]))
    preview = await authoring.preview_subset(
        "plasmodb",
        dataset_id=_DATASET,
        entity_id=_ENTITY,
        filters=[_species("P. berghei")],
        distribution_variable_id="VAR_035294d0",
    )
    await wired.close()
    assert preview.count == 4011
    assert preview.unfiltered_count == 4279
    assert preview.distribution is not None
    assert preview.distribution.statistics.subset_size == 4279
    assert preview.entity_display_name


async def test_the_preview_omits_the_distribution_when_no_variable_is_named(
    wired: EdaClient,
) -> None:
    wired.install_transport(_route([4011, 4279]))
    preview = await authoring.preview_subset(
        "plasmodb",
        dataset_id=_DATASET,
        entity_id=_ENTITY,
        filters=[_species("P. berghei")],
    )
    await wired.close()
    assert preview.distribution is None


async def test_a_filter_on_an_unknown_entity_is_reported_with_its_id(
    wired: EdaClient,
) -> None:
    wired.install_transport(_route([]))
    errors = await authoring.validate_subset(
        "plasmodb",
        dataset_id=_DATASET,
        filters=[
            EdaStringSetFilter(
                entity_id="ENT_nope", variable_id="V", string_set=["x"]
            )
        ],
    )
    await wired.close()
    assert len(errors) == 1
    assert "ENT_nope" in errors[0]
```

- [ ] **Run it.** Expect
      `AttributeError: module ... has no attribute 'validate_subset'`.

- [ ] **Implementation.** Append to `authoring.py`:

```python
@dataclass(frozen=True, slots=True)
class SubsetPreview:
    """A subset's size against the study's, plus one variable's distribution."""

    entity_id: str
    entity_display_name: str
    count: int
    unfiltered_count: int
    distribution: EdaDistributionResponse | None


def declared_ranges(study: EdaStudyDetail) -> DeclaredRanges:
    """The numeric bounds the study declares, keyed by (entity, variable)."""
    ranges: dict[tuple[str, str], tuple[float, float]] = {}
    for entity in walk_entities(study.root_entity):
        for variable in entity.variables:
            match variable:
                case EdaNumberVariable() | EdaIntegerVariable():
                    low = variable.distribution_defaults.range_min
                    high = variable.distribution_defaults.range_max
                    if low is not None and high is not None:
                        ranges[(entity.id, variable.id)] = (low, high)
                case _:
                    continue
    return ranges


async def validate_subset(
    site_id: str,
    *,
    dataset_id: str,
    filters: Sequence[EdaFilter],
) -> list[str]:
    """Every reason this filter array will not mean what it says."""
    _entry, study = await get_study_detail_for_dataset(site_id, dataset_id)
    return validate_filters(study, list(filters), declared_ranges(study))


async def verified_count(
    site_id: str,
    *,
    dataset_id: str,
    entity_id: str,
    filters: Sequence[EdaFilter],
) -> int:
    """The service's own count for this subset. Zero is a real answer."""
    entry = await resolve_dataset(site_id, dataset_id)
    return await get_eda_client(site_id).count(
        study_id=entry.study_id,
        entity_id=entity_id,
        filters=filters,
    )


async def preview_subset(
    site_id: str,
    *,
    dataset_id: str,
    entity_id: str,
    filters: Sequence[EdaFilter],
    distribution_variable_id: str | None = None,
) -> SubsetPreview:
    """The filtered and unfiltered counts, and one variable's histogram."""
    entry, study = await get_study_detail_for_dataset(site_id, dataset_id)
    client = get_eda_client(site_id)
    entity = entity_by_id(study.root_entity, entity_id)
    if entity is None:
        msg = f"Study {entry.study_id} has no entity {entity_id!r}."
        raise ValueError(msg)
    filtered = await client.count(
        study_id=entry.study_id, entity_id=entity_id, filters=filters
    )
    unfiltered = await client.count(
        study_id=entry.study_id, entity_id=entity_id, filters=[]
    )
    distribution = None
    if distribution_variable_id is not None:
        distribution = await client.distribution(
            study_id=entry.study_id,
            entity_id=entity_id,
            variable_id=distribution_variable_id,
            filters=filters,
            bin_spec=None,
        )
    return SubsetPreview(
        entity_id=entity_id,
        entity_display_name=entity.display_name,
        count=filtered,
        unfiltered_count=unfiltered,
        distribution=distribution,
    )
```

- [ ] **Note on `bin_spec`.** A `binSpec` is required for a `continuous`
      variable and refused for any other, and a continuous variable with no
      `binSpec` is a bare 500. `preview_subset` passes `bin_spec=None`, so the
      caller must only name a non-continuous variable. Enforce it here rather
      than letting the 500 happen: read the variable, and when its `dataShape`
      is `continuous`, build an `EdaBinSpec` from
      `distributionDefaults.rangeMin`/`rangeMax`/`binWidth` and pass it. When
      those are absent, skip the distribution and say so in the preview. Add the
      two tests for those branches before writing the code.

- [ ] **Gates**, with
      `src/pathfinder/tests/integration/eda/test_authoring.py`.

---

### Task B4 - the upstream analysis, and the co-edit PATCH helpers

- [ ] **Failing test.** Append to
      `apps/api/src/pathfinder/tests/integration/eda/test_authoring.py`:

```python
async def test_open_analysis_creates_the_upstream_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog.clear_study_caches()
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.path
        if path.endswith("/permissions"):
            return httpx.Response(200, json=_fixture("permissions.json"))
        if path == f"/eda/studies/{_STUDY}":
            return httpx.Response(200, json=_fixture("study_detail_phenotype.json"))
        if path.endswith("/users/current"):
            return httpx.Response(200, json={"id": 1216062453, "isGuest": False})
        if "/analyses/" in path and request.method == "POST":
            return httpx.Response(200, json={"analysisId": "t4fszEJ"})
        return httpx.Response(404, json={"status": "not-found"})

    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(httpx.MockTransport(handler))
    monkeypatch.setattr(catalog, "get_eda_client", lambda _s: client)
    monkeypatch.setattr(authoring, "get_eda_client", lambda _s: client)
    monkeypatch.setattr(authoring, "resolve_eda_user_id", _fake_user_id)

    token = veupathdb_auth_token_ctx.set("t")
    try:
        analysis_id = await authoring.open_analysis(
            "plasmodb", dataset_id=_DATASET, display_name="berghei subset"
        )
    finally:
        veupathdb_auth_token_ctx.reset(token)
        await client.close()

    assert analysis_id == "t4fszEJ"
    posts = [r for r in seen if r.method == "POST" and "/analyses/" in r.url.path]
    assert posts
    assert posts[0].url.path == "/eda/users/1216062453/analyses/PlasmoDB"
    body = json.loads(posts[0].content)
    assert body["studyId"] == _DATASET


async def _fake_user_id(_site_id: str) -> str:
    return "1216062453"


async def test_apply_filters_patches_the_descriptor_and_returns_the_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog.clear_study_caches()
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.path
        if path.endswith("/permissions"):
            return httpx.Response(200, json=_fixture("permissions.json"))
        if path == f"/eda/studies/{_STUDY}":
            return httpx.Response(200, json=_fixture("study_detail_phenotype.json"))
        if request.method == "PATCH":
            return httpx.Response(204)
        if request.method == "GET" and "/analyses/" in path:
            return httpx.Response(
                200,
                json={
                    "analysisId": "t4fszEJ",
                    "displayName": "berghei subset",
                    "studyId": _DATASET,
                    "numFilters": 1,
                    "numComputations": 0,
                    "descriptor": {
                        "subset": {
                            "descriptor": [
                                {
                                    "entityId": _ENTITY,
                                    "variableId": "VAR_035294d0",
                                    "type": "stringSet",
                                    "stringSet": ["P. berghei"],
                                }
                            ],
                            "uiSettings": {},
                        },
                        "computations": [],
                        "starredVariables": [],
                        "dataTableConfig": {},
                        "derivedVariables": [],
                    },
                },
            )
        return httpx.Response(404, json={"status": "not-found"})

    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(httpx.MockTransport(handler))
    monkeypatch.setattr(catalog, "get_eda_client", lambda _s: client)
    monkeypatch.setattr(authoring, "get_eda_client", lambda _s: client)
    monkeypatch.setattr(authoring, "resolve_eda_user_id", _fake_user_id)

    token = veupathdb_auth_token_ctx.set("t")
    try:
        detail = await authoring.apply_filters(
            "plasmodb",
            analysis_id="t4fszEJ",
            dataset_id=_DATASET,
            filters=[_species("P. berghei")],
        )
    finally:
        veupathdb_auth_token_ctx.reset(token)
        await client.close()

    assert detail.num_filters == 1
    patches = [r for r in seen if r.method == "PATCH"]
    assert len(patches) == 1
    assert set(json.loads(patches[0].content)) == {"descriptor"}


async def test_apply_filters_refuses_an_invalid_array_before_patching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog.clear_study_caches()
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.method)
        path = request.url.path
        if path.endswith("/permissions"):
            return httpx.Response(200, json=_fixture("permissions.json"))
        if path == f"/eda/studies/{_STUDY}":
            return httpx.Response(200, json=_fixture("study_detail_phenotype.json"))
        return httpx.Response(404, json={"status": "not-found"})

    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(httpx.MockTransport(handler))
    monkeypatch.setattr(catalog, "get_eda_client", lambda _s: client)
    monkeypatch.setattr(authoring, "get_eda_client", lambda _s: client)
    monkeypatch.setattr(authoring, "resolve_eda_user_id", _fake_user_id)

    token = veupathdb_auth_token_ctx.set("t")
    try:
        with pytest.raises(authoring.SubsetRejectedError) as excinfo:
            await authoring.apply_filters(
                "plasmodb",
                analysis_id="t4fszEJ",
                dataset_id=_DATASET,
                filters=[_species("P. vivax")],
            )
    finally:
        veupathdb_auth_token_ctx.reset(token)
        await client.close()

    assert "P. vivax" in str(excinfo.value)
    assert "PATCH" not in seen
```

- [ ] **Run it.** Expect
      `AttributeError: module ... has no attribute 'open_analysis'`.

- [ ] **Implementation.** Append to `authoring.py`:

```python
class SubsetRejectedError(Exception):
    """The filter array does not describe the subset it claims to."""

    def __init__(self, errors: Sequence[str]) -> None:
        self.errors = list(errors)
        super().__init__(" ".join(self.errors))


async def resolve_eda_user_id(site_id: str) -> str:
    """The numeric WDK user id the analysis routes are keyed by."""
    return await get_eda_analyses_client(site_id).resolve_user_id(
        get_wdk_client(site_id)
    )


async def open_analysis(
    site_id: str,
    *,
    dataset_id: str,
    display_name: str,
) -> str:
    """Create the upstream analysis this conversation edits. Returns its id."""
    await resolve_dataset(site_id, dataset_id)
    analyses = get_eda_analyses_client(site_id)
    created = await analyses.create(
        user_id=await resolve_eda_user_id(site_id),
        analysis=new_analysis(dataset_id=dataset_id, display_name=display_name),
    )
    return created.analysis_id


async def apply_filters(
    site_id: str,
    *,
    analysis_id: str,
    dataset_id: str,
    filters: Sequence[EdaFilter],
) -> EdaAnalysisDetail:
    """Replace the analysis's subset. The upstream document stays the SSOT."""
    errors = await validate_subset(site_id, dataset_id=dataset_id, filters=filters)
    if errors:
        raise SubsetRejectedError(errors)
    return await _patch(
        site_id,
        analysis_id=analysis_id,
        mutate=lambda current: current.model_copy(
            update={"subset": EdaSubsetDescriptor(descriptor=list(filters))},
        ),
    )


async def apply_computation(
    site_id: str,
    *,
    analysis_id: str,
    dataset_id: str,
    computation: EdaComputation,
) -> EdaAnalysisDetail:
    """Replace the analysis's single computation, after checking its config."""
    _entry, study = await get_study_detail_for_dataset(site_id, dataset_id)
    errors = validate_compute_config(study, computation.descriptor.configuration)
    if errors:
        raise SubsetRejectedError(errors)
    return await _patch(
        site_id,
        analysis_id=analysis_id,
        mutate=lambda current: current.model_copy(
            update={"computations": [computation]},
        ),
    )


async def _patch(
    site_id: str,
    *,
    analysis_id: str,
    mutate: Callable[[EdaAnalysisDescriptor], EdaAnalysisDescriptor],
) -> EdaAnalysisDetail:
    """Read the upstream descriptor, apply one change, write it back, re-read.

    Upstream owns the document, so the read after the write is what both
    surfaces render.
    """
    analyses = get_eda_analyses_client(site_id)
    user_id = await resolve_eda_user_id(site_id)
    current = await analyses.get(user_id=user_id, analysis_id=analysis_id)
    await analyses.patch_descriptor(
        user_id=user_id,
        analysis_id=analysis_id,
        descriptor=mutate(current.descriptor),
    )
    return await analyses.get(user_id=user_id, analysis_id=analysis_id)
```

  `_patch` reads before it writes so a co-edit from the tab is not overwritten
  by a stale descriptor. That read-modify-write is the whole co-edit story on
  the backend side; the frontend re-renders from the emitted part.

  Note the test above monkeypatches `authoring.resolve_eda_user_id`. Keep that
  function at module level for exactly that reason, and do not inline it.

- [ ] **Gates**, with
      `src/pathfinder/tests/integration/eda/test_authoring.py`.

---

### Task B5 - the volcano threshold helper

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/services/eda/test_volcano_thresholds.py`:

```python
"""Thresholding is the consumer's job: the viz endpoint sends every row."""

from __future__ import annotations

import json
from pathlib import Path

from pathfinder.integrations.eda.models import VolcanoStatsResponse
from pathfinder.services.eda.compute import retained_point_ids, retained_summary

FIXTURES = (
    Path(__file__).resolve().parents[2]
    / "integrations"
    / "eda"
    / "fixtures"
)


def _stats(rows: list[dict[str, str]]) -> VolcanoStatsResponse:
    return VolcanoStatsResponse.model_validate(
        {"effectSizeLabel": "log2(Fold Change)", "statistics": rows}
    )


def test_a_row_at_the_effect_size_threshold_is_retained() -> None:
    """The bridge plugin's test is inclusive on the absolute effect size."""
    summary = retained_summary(
        _stats([{"effectSize": "1.0", "pValue": "0.01", "pointID": "A"}]),
        effect_size_threshold=1.0,
        significance_threshold=0.05,
    )
    assert summary.retained == 1
    assert summary.retained_up == 1
    assert summary.retained_down == 0


def test_a_row_at_the_significance_threshold_is_retained() -> None:
    summary = retained_summary(
        _stats([{"effectSize": "2.0", "pValue": "0.05", "pointID": "A"}]),
        effect_size_threshold=1.0,
        significance_threshold=0.05,
    )
    assert summary.retained == 1


def test_a_row_above_the_p_value_threshold_is_dropped() -> None:
    summary = retained_summary(
        _stats([{"effectSize": "5.0", "pValue": "0.06", "pointID": "A"}]),
        effect_size_threshold=1.0,
        significance_threshold=0.05,
    )
    assert summary.retained == 0


def test_a_negative_effect_size_counts_as_down() -> None:
    summary = retained_summary(
        _stats([{"effectSize": "-3.0", "pValue": "0.01", "pointID": "A"}]),
        effect_size_threshold=1.0,
        significance_threshold=0.05,
    )
    assert summary.retained == 1
    assert summary.retained_down == 1


def test_up_only_keeps_the_positive_side() -> None:
    rows = [
        {"effectSize": "3.0", "pValue": "0.01", "pointID": "UP"},
        {"effectSize": "-3.0", "pValue": "0.01", "pointID": "DOWN"},
    ]
    ids = retained_point_ids(
        _stats(rows),
        effect_size_threshold=1.0,
        significance_threshold=0.05,
        effect_direction="upOnly",
    )
    assert ids == ["UP"]


def test_down_only_keeps_the_negative_side() -> None:
    rows = [
        {"effectSize": "3.0", "pValue": "0.01", "pointID": "UP"},
        {"effectSize": "-3.0", "pValue": "0.01", "pointID": "DOWN"},
    ]
    ids = retained_point_ids(
        _stats(rows),
        effect_size_threshold=1.0,
        significance_threshold=0.05,
        effect_direction="downOnly",
    )
    assert ids == ["DOWN"]


def test_a_row_with_no_p_value_is_counted_as_unparseable_and_dropped() -> None:
    """One of 5511 live rows omits pValue; the plugin drops such a row."""
    summary = retained_summary(
        _stats(
            [
                {"effectSize": "-1.49447459261845", "pointID": "PF3D7_MIT04200"},
                {"effectSize": "3.0", "pValue": "0.01", "pointID": "A"},
            ]
        ),
        effect_size_threshold=1.0,
        significance_threshold=0.05,
    )
    assert summary.total_rows == 2
    assert summary.unparseable_rows == 1
    assert summary.retained == 1


def test_a_non_numeric_string_is_counted_as_unparseable() -> None:
    summary = retained_summary(
        _stats([{"effectSize": "NA", "pValue": "NA", "pointID": "A"}]),
        effect_size_threshold=1.0,
        significance_threshold=0.05,
    )
    assert summary.unparseable_rows == 1
    assert summary.retained == 0


def test_the_recorded_statistics_reproduce_the_measured_gene_counts() -> None:
    """1543 genes pass, 529 up and 1014 down, on the full recorded response."""
    raw = json.loads((FIXTURES / "volcano_statistics.json").read_text())
    stats = VolcanoStatsResponse.model_validate(raw)
    summary = retained_summary(
        stats, effect_size_threshold=1.0, significance_threshold=0.05
    )
    assert summary.retained == summary.retained_up + summary.retained_down
    assert summary.total_rows == len(stats.statistics)
```

  The last test asserts internal consistency because the fixture is trimmed to
  200 rows. Add a second, live-lane test in
  `apps/api/src/pathfinder/tests/integration/eda/test_compute_polling.py` that
  fetches the whole statistics response and asserts the measured
  `1543 == 529 + 1014` exactly. That is the number the WDK step returns as
  `displayTotalCount`, so a disagreement means the export would disagree with
  the plot.

- [ ] **Run it.** Expect `ModuleNotFoundError: ...services.eda.compute`.

- [ ] **Implementation.** Create
      `apps/api/src/pathfinder/services/eda/compute.py`:

```python
"""Compute orchestration: submit, poll, read, and threshold."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from pathfinder.integrations.eda.factory import get_eda_client
from pathfinder.integrations.eda.models import (
    EdaComputeJob,
    EdaDifferentialExpressionConfig,
    EdaFilter,
    EdaJobStatus,
    VolcanoStatsResponse,
    VolcanoStatsRow,
)

TERMINAL_STATUSES: frozenset[EdaJobStatus] = frozenset(
    {"complete", "failed", "expired", "no-such-job"}
)
RUNNING_STATUSES: frozenset[EdaJobStatus] = frozenset({"queued", "in-progress"})


@dataclass(frozen=True, slots=True)
class RetainedSummary:
    """How many points pass the thresholds, and how many could not be read."""

    total_rows: int
    unparseable_rows: int
    retained: int
    retained_up: int
    retained_down: int


def _numbers(row: VolcanoStatsRow) -> tuple[float, float] | None:
    """The row's effect size and p-value, or None when either cannot be read."""
    if row.p_value is None:
        return None
    try:
        return float(row.effect_size), float(row.p_value)
    except ValueError:
        return None


def _retained(
    stats: VolcanoStatsResponse,
    *,
    effect_size_threshold: float,
    significance_threshold: float,
    effect_direction: str,
) -> Iterator[tuple[VolcanoStatsRow, float]]:
    for row in stats.statistics:
        numbers = _numbers(row)
        if numbers is None:
            continue
        effect, p_value = numbers
        if abs(effect) < effect_size_threshold:
            continue
        if p_value > significance_threshold:
            continue
        if effect_direction == "upOnly" and effect <= 0:
            continue
        if effect_direction == "downOnly" and effect >= 0:
            continue
        yield row, effect


def retained_summary(
    stats: VolcanoStatsResponse,
    *,
    effect_size_threshold: float,
    significance_threshold: float,
    effect_direction: str = "upAndDown",
) -> RetainedSummary:
    """Count the points the WDK step would deliver for these thresholds."""
    unparseable = sum(1 for row in stats.statistics if _numbers(row) is None)
    up = 0
    down = 0
    for _row, effect in _retained(
        stats,
        effect_size_threshold=effect_size_threshold,
        significance_threshold=significance_threshold,
        effect_direction=effect_direction,
    ):
        if effect > 0:
            up += 1
        else:
            down += 1
    return RetainedSummary(
        total_rows=len(stats.statistics),
        unparseable_rows=unparseable,
        retained=up + down,
        retained_up=up,
        retained_down=down,
    )


def retained_point_ids(
    stats: VolcanoStatsResponse,
    *,
    effect_size_threshold: float,
    significance_threshold: float,
    effect_direction: str = "upAndDown",
) -> list[str]:
    """The point ids that pass, in the order the service sent them."""
    return [
        row.point_id
        for row, _effect in _retained(
            stats,
            effect_size_threshold=effect_size_threshold,
            significance_threshold=significance_threshold,
            effect_direction=effect_direction,
        )
    ]
```

- [ ] **Gates**, with
      `src/pathfinder/tests/unit/services/eda/test_volcano_thresholds.py`.

**Traps named:**

- Both comparisons are inclusive on the threshold, and the effect-size test is
  on the ABSOLUTE value. The measured agreement between the client-side count
  and the WDK step's `displayTotalCount` is what pins that.
- A row with no `pValue` is dropped and counted, not treated as significant and
  not treated as zero. The bridge plugin catches the parse failure per row.
- `effectDirection` defaults to `upAndDown`. That is the review card's default
  upstream, and a missing value must not mean "up only".

---

### Task B6 - submit, poll, and read

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/integration/eda/test_compute_polling.py`:

```python
"""The six-state job machine, and the read that follows completion."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from pathfinder.integrations.eda.client import EdaClient
from pathfinder.integrations.eda.models import (
    EdaComparator,
    EdaDifferentialExpressionConfig,
    EdaLabeledRange,
    EdaVariableSpec,
)
from pathfinder.platform.context import veupathdb_auth_token_ctx
from pathfinder.services.eda import compute

FIXTURES = (
    Path(__file__).resolve().parents[2]
    / "unit"
    / "integrations"
    / "eda"
    / "fixtures"
)

pytestmark = pytest.mark.asyncio

_STUDY = "STUDY_e973eadd57"


def _config() -> EdaDifferentialExpressionConfig:
    return EdaDifferentialExpressionConfig(
        identifier_variable=EdaVariableSpec(
            entity_id="ENT_fd574cd6", variable_id="VEUPATHDB_GENE_ID"
        ),
        value_variable=EdaVariableSpec(
            entity_id="ENT_fd574cd6", variable_id="SEQUENCE_READ_COUNT_SENSE"
        ),
        comparator=EdaComparator(
            variable=EdaVariableSpec(
                entity_id="ENT_8151325d", variable_id="VAR_081ab087"
            ),
            group_a=[EdaLabeledRange(label="normal")],
            group_b=[EdaLabeledRange(label="febrile")],
        ),
    )


@pytest.fixture
def token() -> None:
    handle = veupathdb_auth_token_ctx.set("t")
    yield
    veupathdb_auth_token_ctx.reset(handle)


async def test_a_lookup_never_starts_a_job(
    monkeypatch: pytest.MonkeyPatch, token: None
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200, json={"jobID": "a" * 32, "status": "no-such-job"}
        )

    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(httpx.MockTransport(handler))
    monkeypatch.setattr(compute, "get_eda_client", lambda _s: client)

    job = await compute.lookup_job(
        "plasmodb",
        compute_name="differentialexpression",
        study_id=_STUDY,
        config=_config(),
        filters=[],
    )
    await client.close()
    assert job.status == "no-such-job"
    assert seen[0].url.params["autostart"] == "false"


async def test_a_submit_starts_a_job(
    monkeypatch: pytest.MonkeyPatch, token: None
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"jobID": "a" * 32, "status": "queued"})

    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(httpx.MockTransport(handler))
    monkeypatch.setattr(compute, "get_eda_client", lambda _s: client)

    job = await compute.submit_compute(
        "plasmodb",
        compute_name="differentialexpression",
        study_id=_STUDY,
        config=_config(),
        filters=[],
    )
    await client.close()
    assert job.status == "queued"
    assert seen[0].url.params["autostart"] == "true"


async def test_the_lookup_and_the_submit_address_the_same_job_id(
    monkeypatch: pytest.MonkeyPatch, token: None
) -> None:
    """The job id is an MD5 of the plugin name plus the key-sorted body."""
    bodies: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(request.content.decode())
        return httpx.Response(200, json={"jobID": "a" * 32, "status": "complete"})

    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(httpx.MockTransport(handler))
    monkeypatch.setattr(compute, "get_eda_client", lambda _s: client)

    await compute.lookup_job(
        "plasmodb",
        compute_name="differentialexpression",
        study_id=_STUDY,
        config=_config(),
        filters=[],
    )
    await compute.submit_compute(
        "plasmodb",
        compute_name="differentialexpression",
        study_id=_STUDY,
        config=_config(),
        filters=[],
    )
    await compute.read_statistics(
        "plasmodb",
        compute_name="differentialexpression",
        study_id=_STUDY,
        config=_config(),
        filters=[],
    )
    await client.close()
    assert len(set(bodies)) == 1


async def test_the_status_sets_are_exhaustive_over_the_six_states() -> None:
    assert compute.TERMINAL_STATUSES | compute.RUNNING_STATUSES == {
        "queued",
        "in-progress",
        "complete",
        "failed",
        "expired",
        "no-such-job",
    }
    assert not (compute.TERMINAL_STATUSES & compute.RUNNING_STATUSES)


async def test_read_statistics_retries_a_502_right_after_completion(
    monkeypatch: pytest.MonkeyPatch, token: None
) -> None:
    """A read failure immediately after completion is retryable, not a failed job."""
    attempts: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(502, text="<html>Bad Gateway</html>")
        return httpx.Response(200, json=_fixture_stats())

    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(httpx.MockTransport(handler))
    monkeypatch.setattr(compute, "get_eda_client", lambda _s: client)

    stats = await compute.read_statistics(
        "plasmodb",
        compute_name="differentialexpression",
        study_id=_STUDY,
        config=_config(),
        filters=[],
    )
    await client.close()
    assert len(attempts) == 2
    assert stats.statistics


def _fixture_stats() -> object:
    return json.loads((FIXTURES / "volcano_statistics.json").read_text())


@pytest.mark.live_wdk
async def test_the_live_thresholds_reproduce_the_measured_counts(
    require_wdk_creds: str,
) -> None:
    """1543 genes pass at effectSize 1 and significance 0.05: 529 up, 1014 down."""
    handle = veupathdb_auth_token_ctx.set(require_wdk_creds)
    try:
        job = await compute.submit_compute(
            "plasmodb",
            compute_name="differentialexpression",
            study_id=_STUDY,
            config=_config(),
            filters=[],
        )
        assert job.status in compute.RUNNING_STATUSES | {"complete"}
        stats = await compute.read_statistics(
            "plasmodb",
            compute_name="differentialexpression",
            study_id=_STUDY,
            config=_config(),
            filters=[],
        )
    finally:
        veupathdb_auth_token_ctx.reset(handle)
    summary = compute.retained_summary(
        stats, effect_size_threshold=1.0, significance_threshold=0.05
    )
    assert summary.total_rows == 5511
    assert summary.unparseable_rows == 1
    assert summary.retained == 1543
    assert summary.retained_up == 529
    assert summary.retained_down == 1014
```

  The live test submits and then reads without waiting, so it only passes when
  the job is already cached from an earlier run. Make the wait explicit: poll
  `compute.poll_job` until the status leaves `RUNNING_STATUSES` or 120 seconds
  pass, with `asyncio.sleep(2)` between polls, and fail with the last status if
  it times out. Write that loop in the test, not in `compute.py`; the worker
  impl of batch 3 owns the production polling loop and it reports progress,
  which a test does not.

- [ ] **Run it.** Expect
      `AttributeError: module ... has no attribute 'lookup_job'`.

- [ ] **Implementation.** Append to `compute.py`:

```python
_READ_ATTEMPTS = 3
_READ_BACKOFF_SECONDS = 2.0


async def lookup_job(
    site_id: str,
    *,
    compute_name: str,
    study_id: str,
    config: EdaDifferentialExpressionConfig,
    filters: Sequence[EdaFilter],
) -> EdaComputeJob:
    """Ask whether this exact configuration has been computed, without starting it."""
    return await get_eda_client(site_id).submit_compute(
        compute_name=compute_name,
        study_id=study_id,
        config=config,
        filters=filters,
        autostart=False,
    )


async def submit_compute(
    site_id: str,
    *,
    compute_name: str,
    study_id: str,
    config: EdaDifferentialExpressionConfig,
    filters: Sequence[EdaFilter],
) -> EdaComputeJob:
    """Start the job, or adopt the running one this configuration already addresses."""
    return await get_eda_client(site_id).submit_compute(
        compute_name=compute_name,
        study_id=study_id,
        config=config,
        filters=filters,
        autostart=True,
    )


async def poll_job(site_id: str, *, job_id: str) -> EdaComputeJob:
    """One status read. There is no push channel and no ETag."""
    return await get_eda_client(site_id).get_job(job_id)


async def read_statistics(
    site_id: str,
    *,
    compute_name: str,
    study_id: str,
    config: EdaDifferentialExpressionConfig,
    filters: Sequence[EdaFilter],
) -> VolcanoStatsResponse:
    """The completed job's statistics.

    A read right after completion can fail at the proxy, so a 5xx is retried
    and the last attempt raises whatever it raises.
    """
    client = get_eda_client(site_id)
    for attempt in range(_READ_ATTEMPTS - 1):
        try:
            return await client.compute_statistics(
                compute_name=compute_name,
                study_id=study_id,
                config=config,
                filters=filters,
            )
        except EdaError as exc:
            if exc.status < _RETRYABLE_STATUS:
                raise
            await asyncio.sleep(_READ_BACKOFF_SECONDS * (attempt + 1))
    return await client.compute_statistics(
        compute_name=compute_name,
        study_id=study_id,
        config=config,
        filters=filters,
    )
```

  The last attempt sits outside the loop, so there is no stored exception to
  re-raise and no unreachable branch. `_RETRYABLE_STATUS = 500` is a module
  constant beside `_READ_ATTEMPTS`, and `EdaError` plus `asyncio` join the
  imports.

- [ ] **Gates**, with
      `src/pathfinder/tests/integration/eda/test_compute_polling.py`.

- [ ] **Section end.** Run the section-end ladder.

---

## Implementer C: EDA-backed search detection and the sentinel guard

### Files

| Action | Path |
|---|---|
| Create | `apps/api/src/pathfinder/services/catalog/eda_backed.py` |
| Modify | `apps/api/src/pathfinder/services/catalog/__init__.py` (export the two predicates) |
| Modify | `apps/api/src/pathfinder/services/catalog/param_sheet.py` or `param_formatting.py` (the sentinel guard - see task C3 for which) |
| Create | `apps/api/src/pathfinder/tests/unit/services/catalog/test_eda_backed.py` |
| Create | `apps/api/src/pathfinder/tests/unit/services/catalog/test_upload_sentinel.py` |
| Create | `apps/api/src/pathfinder/tests/integration/eda/test_eda_backed_live.py` |

### Interfaces

**Consumes:** `pathfinder.integrations.veupathdb.wdk_models.WDKSearch` (its
`param_names`, `query_name`, `properties`, `url_segment` fields),
`pathfinder.services.catalog.searches.get_raw_searches`,
`pathfinder.domain.parameters.wdk_vocab.WDKVocabulary`.

**Produces:**

```python
# services/catalog/eda_backed.py
EDA_ANALYSIS_SPEC_PARAM = "eda_analysis_spec"
EDA_DATASET_ID_PARAM = "eda_dataset_id"
COMPUTE_QUERY = "GenesByEdaVizWithCompute"
SUBSET_QUERY = "GenesByEdaSubset"
WGCNA_QUERY = "GenesByWGCNAModule"
EDA_NOTEBOOK_TYPE_PROPERTY = "edaNotebookType"

@dataclass(frozen=True, slots=True)
class EdaBackedSearch:
    search_name: str
    display_name: str
    query_name: str
    notebook_type: str | None
    reads_the_spec: bool
    needs_dataset_id: bool
    is_compute_backed: bool
    default_dataset_id: str | None

def is_eda_backed(search: WDKSearch) -> bool
def eda_backed_search(search: WDKSearch) -> EdaBackedSearch | None
async def list_eda_backed(site_id: str, record_type: str = "transcript"
                          ) -> list[EdaBackedSearch]

UPLOAD_SENTINEL_PREFIX = "Upload a"
def is_upload_sentinel_vocabulary(vocabulary: WDKVocabulary | None) -> bool
```

---

### Task C1 - `is_eda_backed`: parameter presence, never the name

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/services/catalog/test_eda_backed.py`:

```python
"""An EDA-backed search is identified by its parameters, never by its name."""

from __future__ import annotations

from pathfinder.integrations.veupathdb.wdk_models import WDKSearch
from pathfinder.services.catalog.eda_backed import (
    eda_backed_search,
    is_eda_backed,
)


def _search(
    *,
    name: str,
    params: list[str],
    query: str = "",
    notebook: str | None = None,
) -> WDKSearch:
    properties: dict[str, list[str]] = {}
    if notebook is not None:
        properties["edaNotebookType"] = [notebook]
    return WDKSearch(
        url_segment=name,
        display_name=name,
        param_names=params,
        query_name=query,
        properties=properties,
    )


def test_a_search_with_the_spec_parameter_is_eda_backed_without_eda_in_its_name() -> None:
    """52 of the 68 are named GenesByRNASeq<dataset>DESeq."""
    search = _search(
        name="GenesByRNASeqpfal3D7_Febrile_temps_RNASeq_ebi_rnaSeq_RSRCDESeq",
        params=["eda_dataset_id", "eda_analysis_spec"],
        query="GenesByEdaVizWithCompute",
        notebook="differentialExpressionNotebook",
    )
    assert is_eda_backed(search) is True


def test_a_search_with_eda_in_its_name_and_no_spec_parameter_is_not_eda_backed() -> None:
    search = _search(name="GenesByEdaSomethingElse", params=["organism"])
    assert is_eda_backed(search) is False


def test_a_plain_search_is_not_eda_backed() -> None:
    assert is_eda_backed(_search(name="GenesByText", params=["text_search_organism"])) is False


def test_the_generic_subset_search_needs_the_dataset_id_set() -> None:
    """GenesByEdaSubsetGeneric hides the parameter; the caller must supply it."""
    described = eda_backed_search(
        _search(
            name="GenesByPhenotypeEdaSubset_X",
            params=["eda_dataset_id", "eda_analysis_spec"],
            query="GenesByEdaSubsetGeneric",
        )
    )
    assert described is not None
    assert described.needs_dataset_id is True
    assert described.is_compute_backed is False


def test_a_compute_backed_search_is_marked_as_such() -> None:
    described = eda_backed_search(
        _search(
            name="GenesByRNASeqXDESeq",
            params=["eda_dataset_id", "eda_analysis_spec"],
            query="GenesByEdaVizWithCompute",
            notebook="differentialExpressionNotebook",
        )
    )
    assert described is not None
    assert described.is_compute_backed is True
    assert described.notebook_type == "differentialExpressionNotebook"


def test_the_wgcna_search_declares_the_spec_and_never_reads_it() -> None:
    """Its query is a plain sqlQuery; setting the spec changes nothing."""
    described = eda_backed_search(
        _search(
            name="GenesByRNASeqXWGCNAModules",
            params=[
                "eda_dataset_id",
                "eda_analysis_spec",
                "wgcnaParam",
                "wgcna_correlation_cutoff",
            ],
            query="GenesByWGCNAModule",
            notebook="wgcnaCorrelationNotebook",
        )
    )
    assert described is not None
    assert described.reads_the_spec is False


def test_a_subset_search_reads_the_spec() -> None:
    described = eda_backed_search(
        _search(
            name="GenesByPhenotypeEdaSubset_X",
            params=["eda_dataset_id", "eda_analysis_spec"],
            query="GenesByEdaSubsetGeneric",
        )
    )
    assert described is not None
    assert described.reads_the_spec is True


def test_a_search_that_is_not_eda_backed_describes_as_none() -> None:
    assert eda_backed_search(_search(name="GenesByText", params=["x"])) is None


def test_a_name_filter_would_find_far_fewer_than_the_predicate() -> None:
    """13 of 68 live have Eda in the name. The predicate is the invariant."""
    searches = [
        _search(name=f"GenesByRNASeqDataset{i}DESeq",
                params=["eda_dataset_id", "eda_analysis_spec"],
                query="GenesByEdaVizWithCompute")
        for i in range(52)
    ] + [
        _search(name="GenesByPhenotypeEdaSubset_X",
                params=["eda_dataset_id", "eda_analysis_spec"],
                query="GenesByEdaSubsetGeneric")
    ]
    by_predicate = [s for s in searches if is_eda_backed(s)]
    by_name = [s for s in searches if "Eda" in s.url_segment]
    assert len(by_predicate) == 53
    assert len(by_name) == 1
```

- [ ] **Run it.** Expect `ModuleNotFoundError`.

- [ ] **Implementation.** Create
      `apps/api/src/pathfinder/services/catalog/eda_backed.py`:

```python
"""Which WDK searches carry an EDA subset, and what each one needs."""

from __future__ import annotations

from dataclasses import dataclass

from pathfinder.integrations.veupathdb.wdk_models import WDKSearch
from pathfinder.services.catalog.searches import get_raw_searches

EDA_ANALYSIS_SPEC_PARAM = "eda_analysis_spec"
EDA_DATASET_ID_PARAM = "eda_dataset_id"

SUBSET_QUERY = "GenesByEdaSubset"
COMPUTE_QUERY = "GenesByEdaVizWithCompute"
WGCNA_QUERY = "GenesByWGCNAModule"

EDA_NOTEBOOK_TYPE_PROPERTY = "edaNotebookType"

# The one query that declares the spec parameter and never reads it.
_SPEC_IS_INERT = frozenset({WGCNA_QUERY})

_COMPUTE_QUERIES = frozenset({COMPUTE_QUERY})


@dataclass(frozen=True, slots=True)
class EdaBackedSearch:
    """One EDA-backed search, and what a caller must supply to run it."""

    search_name: str
    display_name: str
    query_name: str
    notebook_type: str | None
    reads_the_spec: bool
    needs_dataset_id: bool
    is_compute_backed: bool
    default_dataset_id: str | None


def is_eda_backed(search: WDKSearch) -> bool:
    """True when the search declares the analysis-spec parameter.

    68 of 359 transcript searches declare it live and 13 have Eda in the name,
    so the parameter is the only reliable test.
    """
    return EDA_ANALYSIS_SPEC_PARAM in search.param_names


def eda_backed_search(search: WDKSearch) -> EdaBackedSearch | None:
    """Describe an EDA-backed search, or None when it is not one."""
    if not is_eda_backed(search):
        return None
    notebook = search.properties.get(EDA_NOTEBOOK_TYPE_PROPERTY, [])
    return EdaBackedSearch(
        search_name=search.url_segment,
        display_name=search.display_name,
        query_name=search.query_name,
        notebook_type=notebook[0] if notebook else None,
        reads_the_spec=search.query_name not in _SPEC_IS_INERT,
        needs_dataset_id=EDA_DATASET_ID_PARAM in search.param_names,
        is_compute_backed=search.query_name in _COMPUTE_QUERIES,
        default_dataset_id=_dataset_default(search),
    )


async def list_eda_backed(
    site_id: str,
    record_type: str = "transcript",
) -> list[EdaBackedSearch]:
    """Every EDA-backed search on a record type, ordered by name."""
    searches = await get_raw_searches(site_id, record_type)
    described = [eda_backed_search(s) for s in searches]
    return sorted(
        (d for d in described if d is not None),
        key=lambda d: d.search_name,
    )
```

  `_dataset_default(search)` reads the `eda_dataset_id` parameter's
  `defaultValue` from `search.parameters` when the expanded definition is
  present, and returns `None` otherwise. `WDKSearch.parameters` is
  `list[WDKParameter] | None`, so the body is a generator over the list with a
  name compare, and `None` when the list is absent. No `getattr`.

  `search.properties.get(...)` is a lookup on a typed
  `dict[str, list[str]]` the model produced, which is the allowed use.

- [ ] **Export the predicates.** Add `is_eda_backed`, `eda_backed_search`,
      `list_eda_backed` and `EdaBackedSearch` to
      `services/catalog/__init__.py`'s imports and `__all__`, keeping the
      alphabetical order the file already holds.

- [ ] **Gates**, with
      `src/pathfinder/tests/unit/services/catalog/test_eda_backed.py`.

---

### Task C2 - route an EDA-backed search away from generic param resolution

- [ ] **Failing test.** Append to
      `apps/api/src/pathfinder/tests/unit/services/catalog/test_eda_backed.py`:

```python
def test_an_eda_backed_search_names_the_two_parameters_it_needs() -> None:
    described = eda_backed_search(
        _search(
            name="GenesByPhenotypeEdaSubset_X",
            params=["eda_dataset_id", "eda_analysis_spec"],
            query="GenesByEdaSubsetGeneric",
        )
    )
    assert described is not None
    assert described.needs_dataset_id
    assert described.reads_the_spec


def test_the_guidance_tells_the_model_to_use_the_eda_tools() -> None:
    from pathfinder.services.catalog.eda_backed import eda_backed_guidance

    described = eda_backed_search(
        _search(
            name="GenesByRNASeqXDESeq",
            params=["eda_dataset_id", "eda_analysis_spec"],
            query="GenesByEdaVizWithCompute",
            notebook="differentialExpressionNotebook",
        )
    )
    assert described is not None
    guidance = eda_backed_guidance(described)
    assert "eda_analysis_spec" in guidance
    assert "create_eda_step" in guidance
    assert "run_eda_compute" in guidance
    assert "set_criterion" not in guidance


def test_the_subset_guidance_does_not_mention_a_compute() -> None:
    from pathfinder.services.catalog.eda_backed import eda_backed_guidance

    described = eda_backed_search(
        _search(
            name="GenesByPhenotypeEdaSubset_X",
            params=["eda_dataset_id", "eda_analysis_spec"],
            query="GenesByEdaSubsetGeneric",
        )
    )
    assert described is not None
    guidance = eda_backed_guidance(described)
    assert "run_eda_compute" not in guidance
    assert "open_eda_analysis" in guidance
```

- [ ] **Implementation.** Append to `eda_backed.py`:

```python
def eda_backed_guidance(search: EdaBackedSearch) -> str:
    """What to do instead of proposing values for the two EDA parameters.

    The spec is a JSON document, not a value a parameter sheet can propose, so
    the EDA tools author it and the step-creation tool serializes it once.
    """
    lines = [
        f"{search.search_name} is EDA-backed: its {EDA_ANALYSIS_SPEC_PARAM} "
        f"parameter carries a whole EDA analysis document, so do not propose a "
        f"value for it.",
        "Instead: search_eda_studies, then describe_eda_study, then "
        "open_eda_analysis, then set_eda_filters, then preview_eda_subset.",
    ]
    if search.is_compute_backed:
        lines.append(
            "This search exports the genes that pass a volcano plot's "
            "thresholds, so run_eda_compute must complete before create_eda_step."
        )
    if not search.reads_the_spec:
        lines.append(
            "This search declares the parameter and never reads it; its gene "
            "list comes from its own parameters."
        )
    lines.append("create_eda_step builds the step from the open analysis.")
    return " ".join(lines)
```

- [ ] **Wire the guidance in.** `services/catalog/search_inspection.py`
      `inspect_search` returns a `SearchInspection` whose `overview` is built by
      `format_search_overview`. Add the guidance to the overview when
      `eda_backed_search(definition)` is not None. Find the exact field on
      `SearchOverviewResult` (`services/catalog/overview_formatting.py`) and
      either append to its existing notes field or add one named
      `eda_guidance: str = ""`. Whichever you choose, add a test in
      `apps/api/src/pathfinder/tests/unit/services/catalog/` asserting that
      `inspect_search` on an EDA-backed definition carries the guidance and that
      a plain search carries the empty string. Do not add a field nothing reads.

- [ ] **Gates**, with the two catalog test files and
      `src/pathfinder/tests/unit/services/catalog/`.

---

### Task C3 - the `EDAUD_` upload sentinel

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/services/catalog/test_upload_sentinel.py`:

```python
"""A one-term vocabulary whose display starts with 'Upload a' is an empty state."""

from __future__ import annotations

from pathfinder.domain.parameters.wdk_vocab import WDKVocabTerm
from pathfinder.services.catalog.eda_backed import is_upload_sentinel_vocabulary


def _terms(*pairs: tuple[str, str]) -> list[WDKVocabTerm]:
    return [WDKVocabTerm((t, d, None)) for t, d in pairs]  # the WDK wire triple


def test_the_live_sentinel_is_recognised() -> None:
    vocabulary = _terms(
        (
            "EDAUD_slI5M0RwIg0Zw",
            "Upload a Phenotype User Dataset in My Workspace",
        )
    )
    assert is_upload_sentinel_vocabulary(vocabulary) is True


def test_a_real_single_dataset_vocabulary_is_not_a_sentinel() -> None:
    vocabulary = _terms(("EDAUD_realid", "My RNA-Seq counts"))
    assert is_upload_sentinel_vocabulary(vocabulary) is False


def test_two_terms_are_never_a_sentinel() -> None:
    vocabulary = _terms(
        ("EDAUD_a", "Upload a Phenotype User Dataset in My Workspace"),
        ("EDAUD_b", "My dataset"),
    )
    assert is_upload_sentinel_vocabulary(vocabulary) is False


def test_an_empty_vocabulary_is_not_a_sentinel() -> None:
    assert is_upload_sentinel_vocabulary([]) is False


def test_none_is_not_a_sentinel() -> None:
    assert is_upload_sentinel_vocabulary(None) is False


def test_the_raw_counts_sentinel_is_recognised_too() -> None:
    vocabulary = _terms(
        ("EDAUD_slI5M0RwIg0Zw", "Upload an RNA-Seq Raw Counts Dataset in My Workspace")
    )
    assert is_upload_sentinel_vocabulary(vocabulary) is True
```

  The last test's display text is the raw-counts arm's wording. The measured
  phenotype arm reads "Upload a Phenotype User Dataset in My Workspace"; the
  raw-counts arm's exact wording was not recorded. Match on `Upload a` case
  insensitively with the word boundary, so both "Upload a" and "Upload an" fire,
  and say that in one comment.

- [ ] **Implementation.** Append to `eda_backed.py`:

```python
_UPLOAD_SENTINEL = re.compile(r"^upload an?\b", re.IGNORECASE)


def is_upload_sentinel_vocabulary(vocabulary: WDKVocabulary | None) -> bool:
    """True when a one-term vocabulary is an empty state, not a choice.

    Both user-dataset vocabulary queries end with a UNION ALL arm that fires
    only when the user owns no installed dataset. Running the search with that
    term is a 400.
    """
    if not isinstance(vocabulary, list) or len(vocabulary) != 1:
        return False
    return bool(_UPLOAD_SENTINEL.match(vocabulary[0].display))
```

  `WDKVocabulary` is a union of a list of terms, a tree node and a dict, so the
  list case must be selected. Do that with `match vocabulary: case [single]:`
  rather than an `isinstance` call - structural pattern matching over the union
  is the idiom, and it also binds the single term:

```python
def is_upload_sentinel_vocabulary(vocabulary: WDKVocabulary | None) -> bool:
    match vocabulary:
        case [WDKVocabTerm() as single]:
            return bool(_UPLOAD_SENTINEL.match(single.display))
        case _:
            return False
```

- [ ] **Wire the guard in.** The vocabulary a model chooses from is built by
      `services/catalog/param_sheet.py::build_sheet` (its `SheetEntry.vocabulary`
      and `vocabulary_note` fields) from
      `services/catalog/param_formatting.py::format_param_info_typed`. Add the
      guard where the sheet entry is built: when
      `is_upload_sentinel_vocabulary` is true, emit an EMPTY `vocabulary` and set
      `vocabulary_note` to the one sentence that says the account owns no
      installed dataset for this search and the search cannot run. An empty
      vocabulary with a note is what makes the model ask the user instead of
      picking the sentinel and getting a 400.

- [ ] **Test the wiring.** Add to
      `apps/api/src/pathfinder/tests/unit/services/catalog/test_upload_sentinel.py`
      a test that drives `build_sheet` over a `WDKParameter` whose vocabulary is
      the sentinel and asserts the resulting `SheetEntry.vocabulary == []` and
      that `vocabulary_note` names the empty state. Read `build_sheet`'s real
      signature first and construct its input from the real `WDKParameter`
      model, not from a dict.

- [ ] **Gates**, with
      `src/pathfinder/tests/unit/services/catalog/`.

---

### Task C4 - the live census

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/integration/eda/test_eda_backed_live.py`:

```python
"""The census the predicate is built on, re-measured.

Gated on WDK_TEST_TOKEN, or WDK_TEST_EMAIL/WDK_TEST_PASSWORD (skipped unset).
"""

from __future__ import annotations

import pytest

from pathfinder.platform.context import veupathdb_auth_token_ctx
from pathfinder.services.catalog.eda_backed import list_eda_backed
from pathfinder.services.catalog.searches import get_raw_searches

pytestmark = [pytest.mark.live_wdk, pytest.mark.asyncio]


async def test_the_predicate_finds_far_more_than_a_name_filter(
    require_wdk_creds: str,
) -> None:
    handle = veupathdb_auth_token_ctx.set(require_wdk_creds)
    try:
        searches = await get_raw_searches("plasmodb", "transcript")
        described = await list_eda_backed("plasmodb", "transcript")
    finally:
        veupathdb_auth_token_ctx.reset(handle)
    by_name = [s for s in searches if "Eda" in s.url_segment]
    assert len(described) >= 60
    assert len(described) > len(by_name) * 3


async def test_the_compute_backed_searches_are_the_majority(
    require_wdk_creds: str,
) -> None:
    handle = veupathdb_auth_token_ctx.set(require_wdk_creds)
    try:
        described = await list_eda_backed("plasmodb", "transcript")
    finally:
        veupathdb_auth_token_ctx.reset(handle)
    compute_backed = [d for d in described if d.is_compute_backed]
    assert len(compute_backed) >= 50


async def test_exactly_one_search_declares_the_spec_and_never_reads_it(
    require_wdk_creds: str,
) -> None:
    handle = veupathdb_auth_token_ctx.set(require_wdk_creds)
    try:
        described = await list_eda_backed("plasmodb", "transcript")
    finally:
        veupathdb_auth_token_ctx.reset(handle)
    inert = [d for d in described if not d.reads_the_spec]
    assert len(inert) == 1
    assert inert[0].query_name == "GenesByWGCNAModule"
```

  The thresholds are lower bounds, not the measured exact numbers, because the
  catalog grows. The exact live measurement on 2026-08-27 was 68 EDA-backed of
  359 transcript searches, 13 with `Eda` in the name, 58 on
  `GenesByEdaVizWithCompute`, and 1 on `GenesByWGCNAModule`. A test that pins 68
  exactly would fail on the next dataset load, which is drift in the data, not
  in the code. The inert count IS pinned at exactly 1, because a second inert
  search would mean a new upstream query and the routing rules would need to
  change.

- [ ] **Run it** with credentials, then confirm it skips without them.

- [ ] **Section end.** Run the section-end ladder.

---

## Verifier 1 - covers implementers A and B

### Re-run

```bash
cd apps/api
uv run ruff check src/
uv run mypy --strict src/pathfinder/
uv run pyright src/pathfinder/
uv run lint-imports
uv run pytest src/pathfinder/tests/unit/services/eda/ -v
uv run pytest src/pathfinder/tests/unit/integrations/embeddings/ -v
uv run pytest src/pathfinder/tests/integration/eda/ -v
uv run pytest src/pathfinder/tests/unit/ -v
uv run pytest src/pathfinder/tests/unit/ -v   # twice: a leaked cache shows here
```

### Traps to hunt, by name

1. **Reject a resolve that derives `STUDY_` from `DS_`.** Grep
   `services/eda/catalog.py` for `replace(`, `removeprefix`, `f"STUDY_` and
   `[3:]`. `resolve_dataset` must read `/permissions` and nothing else.
2. **Reject a `resolve_dataset` that consults `/studies`.** `perDataset` is a
   superset; a dataset that resolves may have no study row.
3. **Reject a study cache keyed on `sha1hash` alone.** A user study's hash is
   the empty string, so the key must fall back to `lastModified`.
4. **Reject a cache key with no base URL.** A study id means nothing without
   its deployment.
5. **Reject a serialize path with two call sites.** The grep test in
   `test_serialize_spec.py` must be present and passing. Run the grep by hand
   too:
   `grep -rn "model_dump_json" apps/api/src/pathfinder/services apps/api/src/pathfinder/ai apps/api/src/pathfinder/jobs`
   and confirm the only analysis dump is in `authoring.py`.
6. **Reject `"{}"` or `"null"` for an empty spec.** It must be `""`.
7. **Reject an `EdaStepRequest` whose validator is a call-site `if`.** It must
   be a `@model_validator(mode="after")` on the model.
8. **Reject a threshold test that is not inclusive, or that omits `abs()`.**
9. **Reject a row with no `pValue` being treated as significant.**
10. **Reject `effectDirection` defaulting to anything but `upAndDown`.**
11. **Reject a `read_statistics` that retries a 4xx**, and reject one that
    stores an exception and re-raises it after the loop (that is the
    unreachable-branch debt the plan text names).
12. **Reject a compute submit that is retried.** `autostart=true` starts work.
13. **Reject a second `_compute_body`.** The submit body addresses the job.
14. **Reject a search index used as a resolver.** `search_studies` must read
    `/permissions` for the study id, never `EdaStudyOverview.id` alone... and it
    must ALSO drop a study with no permission entry. Read the loop.
15. **Reject a missing document/query prefix.** `SEARCH_DOCUMENT_PREFIX` in
    `cache_key` and in `encode_texts`; `SEARCH_QUERY_PREFIX` only in `query`.
16. **Reject a duplicated cache implementation.** `study_index.py` must import
    `load_cached_rows`, `save_cache` and `encode_texts` from
    `semantic_index.py`, not carry copies. Grep both files for `np.savez`.
17. **Reject any `isinstance` chain, `getattr` with a default, `hasattr`,
    `dict.get` over untyped JSON, `# type: ignore`, `noqa` or `import as` in
    production code.** Three things are allowed and must be named in the report
    so the lead can check the judgment: a `match` over a discriminated union, a
    `.get` on a dictionary a Pydantic model produced, and an `isinstance` inside
    a test helper that walks arbitrary decoded JSON (`_no_nulls` in
    `test_serialize_spec.py` is the only one this batch introduces).
18. **Reject a leaked cache.** Running the unit suite twice must give the same
    result, and `clear_study_caches` must be autouse in
    `tests/conftest.py`.

### Report format

One block per task (A1 to A5, B1 to B6), with an `evidence:` line naming the
command and its result, a `read:` line naming the file and lines, and a
`traps checked:` line naming the numbers above. A FAIL names the file, the line
and the rule.

---

## Verifier 2 - covers implementer C, plus the cross-check

### Re-run

```bash
cd apps/api
uv run ruff check src/
uv run mypy --strict src/pathfinder/
uv run pyright src/pathfinder/
uv run lint-imports
uv run pytest src/pathfinder/tests/unit/services/catalog/ -v
uv run pytest src/pathfinder/tests/unit/ -v
uv run pytest src/pathfinder/tests/integration/eda/test_eda_backed_live.py -v
```

### Traps to hunt, by name

1. **Reject a name-based detection anywhere.** Grep
   `services/catalog/eda_backed.py` for `"Eda" in`, `startswith("GenesByEda`,
   and `endswith("DESeq")`. Detection is `eda_analysis_spec in param_names`.
2. **Reject a search-name allowlist.** 52 of the 68 are per-dataset generated
   names that change with every dataset load.
3. **Reject `reads_the_spec` that is not false for `GenesByWGCNAModule`.**
4. **Reject `is_compute_backed` that is true for a subset query.** Only
   `GenesByEdaVizWithCompute` is compute-backed.
5. **Reject guidance that tells the model to use `set_criterion`** on an
   EDA-backed search. That is the routing the whole predicate exists for.
6. **Reject a `SearchOverviewResult` field nothing reads.** If the guidance was
   added as a new field, find its consumer; if there is none yet, it must be
   consumed in batch 3 and the batch-3 document must name it. Otherwise it is
   debt.
7. **Reject a sentinel check that matches only "Upload a".** The raw-counts arm
   may read "Upload an". The regex must cover both.
8. **Reject a sentinel check that fires on a vocabulary of two or more.** A real
   dataset list can begin with a name starting "Upload"; only a size-one
   vocabulary is an empty state.
9. **Reject a sentinel guard that leaves the term in the vocabulary.** The whole
   point is that the model cannot pick it. `vocabulary == []` plus a note.
10. **Reject a live census test that pins 68 exactly.** That is data drift, not
    a code failure. The inert count IS pinned at 1.
11. **Reject any `isinstance` on `WDKVocabulary`.** Use `match`.

### The cross-check - the one thing only this verifier does

- [ ] Confirm the three modules agree on every shared type, by reading, not by
      grep:
      - `services/eda/authoring.py` builds `EdaNewAnalysis` only through
        `new_analysis`, and `EdaStepRequest` only from `serialize_spec`'s output.
      - `services/eda/compute.py` takes the same
        `EdaDifferentialExpressionConfig` instance that
        `authoring.apply_computation` validated, and never rebuilds one.
      - `services/catalog/eda_backed.py` names `eda_dataset_id` and
        `eda_analysis_spec` with the same two string constants
        `authoring.EdaStepRequest.wdk_parameters` emits. If the strings are
        written twice, one of them is wrong the day the other changes: the
        constants live in `eda_backed.py` and `authoring.py` imports them, or
        the reverse. Pick one and say which in the report.
- [ ] Confirm `domain/eda.py` is still not imported by anything in
      `integrations/`, and that `services/eda/authoring.py` is the only module
      calling `validate_filters` and `validate_compute_config`. A second caller
      means the validation is not a single gate.

### Report format

Same as verifier 1, one block per task C1 to C4, plus one block for the
cross-check with the constants decision stated.

---

## Exit criteria

1. `cd apps/api && uv run ruff check src/ && uv run mypy --strict src/pathfinder/ && uv run pyright src/pathfinder/ && uv run lint-imports && uv run pytest src/pathfinder/tests/ -v` is green, run by the lead.
2. The unit suite passes twice in a row: no cache leaks between tests, and
   `clear_study_caches` plus the EDA client close are autouse in
   `apps/api/src/pathfinder/tests/conftest.py`.
3. `grep -rn "model_dump_json" apps/api/src/pathfinder/services apps/api/src/pathfinder/ai apps/api/src/pathfinder/jobs apps/api/src/pathfinder/transport`
   shows exactly one analysis dump, in `services/eda/authoring.py`.
4. `grep -rn "STUDY_" apps/api/src/pathfinder/services/eda/catalog.py` shows no
   string construction, only comparisons in comments or none at all.
5. `services/catalog/eda_backed.py` contains no search-name test.
6. The live lane runs green with credentials and skips with a named reason
   without them, for both `test_compute_polling.py` and
   `test_eda_backed_live.py`.
7. The measured live volcano counts (5511 rows, 1 unparseable, 1543 retained,
   529 up, 1014 down) are asserted by the live test and it passed at least once.
8. `semantic_index.py`'s three helpers are public and shared, and
   `study_index.py` carries no second cache implementation.
9. Both verifier reports are PASS on every task, with evidence lines, and the
   lead has spot-read `authoring.py`, `compute.py`, `catalog.py` and
   `eda_backed.py` against this document.
10. Zero debt. The recap leads with that sentence or the batch stays open.
