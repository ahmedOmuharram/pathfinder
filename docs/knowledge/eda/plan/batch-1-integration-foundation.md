---
type: Plan
title: "EDA batch 1: integration foundation"
description: The typed EDA wire mirror, the async client over its REST surface, and the pure predicates that decide whether a subset is worth exporting - three implementers, two verifiers, pinned wire fixtures as the drift gate.
tags: [eda, pathfinder, plan, batch, integrations, domain, pydantic, fixtures]
generated: { by: claude-code/opus-5, at: 2026-08-28T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-28T00:00:00Z }
status: accepted
---

# EDA batch 1: integration foundation

**Goal.** Give PathFinder a typed, tested, hermetically-verifiable mirror of the
EDA REST surface plus the pure predicates that decide whether a filter array is
valid, so every later batch talks to EDA through one client and one model set.

**Prerequisites.** None. This is the first batch.

**Read first:** [overview.md](overview.md) (the pinned shared contract - names
there are law), then
[../pathfinder-architecture-fit.md](../pathfinder-architecture-fit.md) sections
1.1, 1.2, 4.1, 4.4 and 5. The wire truths come from
[../rest-surface.md](../rest-surface.md),
[../data-model.md](../data-model.md),
[../filters.md](../filters.md),
[../computes-and-jobs.md](../computes-and-jobs.md),
[../subsetting-and-tabular.md](../subsetting-and-tabular.md),
[../visualizations.md](../visualizations.md),
[../derived-variables-and-merging.md](../derived-variables-and-merging.md),
[../eda-wdk-bridge.md](../eda-wdk-bridge.md) and
[../genomics-and-wdk-relations.md](../genomics-and-wdk-relations.md).

## Inherited constraints

Copied here so an implementer needs no other file. Every one of these is a
failure condition, not a preference.

- **TDD is non-negotiable.** No production code without a failing test first.
  Red, then green, then refactor. "Just moving code" is not an exemption.
- **Pydantic maximalism.** Every boundary is a Pydantic model. No raw dicts, no
  `isinstance` chains, no `getattr(obj, "field", default)`, no `hasattr`, no
  `dict.get` ladders at call sites. Use `model_validate`, `extra="ignore"`,
  `Discriminator("type")`, `@field_validator(mode="before")`,
  `@model_validator(mode="after")`, `TypeAdapter[T]`.
- **No type suppressions.** No `# type: ignore`, no `noqa`, no
  `cast` used to silence a real error. Fix the root cause.
- **No `import as`.** Never `import X as Y` or `from X import Y as Z`. The one
  exception is a genuine third-party name conflict.
- **No backwards compatibility.** PathFinder has not shipped. No aliases, no
  re-exports, no `TYPE_CHECKING` imports. Delete aggressively.
- **Comments: 1 to 3 lines, ASD-STE100, near zero.** No module docstring that
  tells a story. Never name a person, a date, an incident, an environment
  variable or a metric from a run. Never narrate the next line.
- **ASCII punctuation only**, in code strings and in prose. No em-dashes, no
  curly quotes, no unicode ellipsis.
- **Python 3.14.** `except ValueError, TypeError:` without parentheses is valid
  (PEP 758) and appears throughout this codebase. Do not "fix" it.
- **Import-linter contracts are law** (`apps/api/pyproject.toml` lines 250-324):
  - `pathfinder.domain` may not import `pathfinder.integrations`,
    `pathfinder.services`, `pathfinder.transport`, `pathfinder.persistence`,
    `pathfinder.ai`, `httpx`, `sqlalchemy`, `asyncpg` or `fastapi`.
  - `pathfinder.integrations` may not import `pathfinder.services`,
    `pathfinder.transport` or `pathfinder.ai`.
- **Only the LLM is mocked.** EDA wire fixtures are recorded real responses.
  A hermetic test validates against the fixture; a live test re-fetches.
- **Never read a `.env` file.** Do not `cat`, `head`, `grep` or `echo` any
  `.env*` file. Source it in the shell and reference `$VAR`.
- **Definition of done.** Gates green is not done. Done means: gates green, zero
  debt from this task (no dead code, no unused arguments, no always-true
  branches, no temporary instrumentation, no new TODOs), adjacent
  reconciliation, tests that assert correctness rather than existence, and a
  recap that leads with remaining debt.

**Gate ladder for every task in this batch:**

```bash
cd apps/api && uv run ruff check src/ \
  && uv run mypy --strict src/pathfinder/ \
  && uv run pyright src/pathfinder/ \
  && uv run pytest <the exact test files this task touched> -v
```

**Section-end full suite:**

```bash
cd apps/api && uv run pytest src/pathfinder/tests/unit/ -v \
  && uv run lint-imports
```

---

## Implementer A: `integrations/eda/models.py` and the pinned wire fixtures

### Files

| Action | Path |
|---|---|
| Create | `apps/api/src/pathfinder/integrations/eda/__init__.py` |
| Create | `apps/api/src/pathfinder/integrations/eda/models.py` |
| Create | `apps/api/src/pathfinder/tests/unit/integrations/eda/__init__.py` |
| Create | `apps/api/src/pathfinder/tests/unit/integrations/eda/fixtures/*.json` (11 files, listed in task A1) |
| Create | `apps/api/src/pathfinder/tests/unit/integrations/eda/test_study_models.py` |
| Create | `apps/api/src/pathfinder/tests/unit/integrations/eda/test_variable_union.py` |
| Create | `apps/api/src/pathfinder/tests/unit/integrations/eda/test_filter_union.py` |
| Create | `apps/api/src/pathfinder/tests/unit/integrations/eda/test_analysis_models.py` |
| Create | `apps/api/src/pathfinder/tests/unit/integrations/eda/test_compute_models.py` |
| Create | `apps/api/src/pathfinder/tests/unit/integrations/eda/test_fixtures_validate.py` |

### Interfaces

**Consumes:** nothing from this plan. From the repository:
`assistant_core.platform.pydantic_base.CamelModel`,
`assistant_core.platform.types.JSONObject`.

**Produces** (implementers B and C, and batches 2, 3 and 4 rely on these exact
names in `pathfinder.integrations.eda.models`):

```python
EdaModel
EdaVariableSpec, EdaCollectionSpec
EdaStudyOverview, EdaStudiesResponse
EdaStudyDetail, EdaStudyDetailResponse
EdaEntity
EdaVariable            # Annotated union, Discriminator("type")
EdaStringVariable, EdaIntegerVariable, EdaNumberVariable,
EdaDateVariable, EdaLongitudeVariable, EdaCategoryVariable
EdaNumberDistributionDefaults, EdaDateDistributionDefaults
EdaCollection
EdaFilter              # Annotated union, Discriminator("type")
EdaStringSetFilter, EdaNumberSetFilter, EdaDateSetFilter,
EdaNumberRangeFilter, EdaDateRangeFilter, EdaLongitudeRangeFilter,
EdaMultiFilter, EdaSubFilter
EdaActionAuthorization, EdaPermissionEntry, EdaPermissionsResponse
EdaLabeledRange, EdaComparator, EdaDifferentialExpressionConfig
EdaComputationDescriptor, EdaVolcanoConfiguration, EdaVolcanoDescriptor,
EdaVisualization, EdaComputation
EdaSubsetDescriptor, EdaAnalysisDescriptor, EdaNewAnalysis,
EdaAnalysisSummary, EdaAnalysisDetail, EdaCreateAnalysisResponse
EdaJobStatus, EdaComputeJob
EdaVisualizationOverview, EdaAppInfo, EdaAppsResponse
VolcanoStatsRow, VolcanoStatsResponse
EdaCountResponse
EdaHistogramBin, EdaDistributionStatistics, EdaDistributionResponse
TABULAR_JSON = TypeAdapter(list[list[str]])
```

---

### Task A1 - record the wire fixtures

This task writes data, not code. Its output is the drift gate every later task
validates against ([../pathfinder-architecture-fit.md](../pathfinder-architecture-fit.md)
section 4.4: pinned wire samples, not a fetched RAML).

- [ ] **Log in.** In a shell, source the gitignored dev env file and use the
      variables by name. Never print them.

  ```bash
  cd /Users/ahmedmuharram/repos/pathfinder
  set -a; . ./.env.dev; set +a
  TOK=$(curl -s -i -X POST https://plasmodb.org/plasmo/service/login \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$WDK_DEV_EMAIL\",\"password\":\"$WDK_DEV_PASSWORD\",\"redirectUrl\":\"/\"}" \
    | grep -i '^set-cookie: Authorization=' | head -1 \
    | sed 's/^[Ss]et-[Cc]ookie: Authorization=//; s/;.*$//')
  test -n "$TOK" && echo "login ok"
  ```

  The login shape is `integrations/veupathdb/auth_login.py::password_login`: a
  JSON POST to `{service_url}/login`, and the credential is the non-guest
  `Authorization` cookie from `Set-Cookie`. Guest calls to `/eda` are 401
  ([../rest-surface.md](../rest-surface.md), Authentication).

- [ ] **Record eleven fixtures** into
      `apps/api/src/pathfinder/tests/unit/integrations/eda/fixtures/`. `E=https://plasmodb.org/eda`,
      `F=apps/api/src/pathfinder/tests/unit/integrations/eda/fixtures`.

  | File | Call |
  |---|---|
  | `studies_list.json` | `GET $E/studies` |
  | `study_detail_de.json` | `GET $E/studies/STUDY_e973eadd57` |
  | `study_detail_phenotype.json` | `GET $E/studies/STUDY_53f554ec6a` |
  | `permissions.json` | `GET $E/permissions` |
  | `count_unfiltered.json` | `POST $E/studies/STUDY_53f554ec6a/entities/GENE_PHENOTYPE_DATA_ENTITY/count` body `{"filters":[]}` |
  | `count_filtered.json` | same, body `{"filters":[{"entityId":"GENE_PHENOTYPE_DATA_ENTITY","variableId":"VAR_035294d0","type":"stringSet","stringSet":["P. berghei"]}]}` |
  | `distribution_categorical.json` | `POST $E/studies/STUDY_53f554ec6a/entities/GENE_PHENOTYPE_DATA_ENTITY/variables/VAR_035294d0/distribution` body `{"filters":[],"valueSpec":"count"}` |
  | `tabular_json.json` | `POST $E/studies/STUDY_53f554ec6a/entities/GENE_PHENOTYPE_DATA_ENTITY/tabular` body `{"filters":[],"outputVariableIds":["VEUPATHDB_GENE_ID"],"reportConfig":{"paging":{"numRows":5,"offset":0}}}` with `-H 'Accept: application/json'` |
  | `apps.json` | `GET $E/apps` |
  | `compute_job_lookup.json` | `POST "$E/computes/differentialexpression?autostart=false"` with the `de_body.json` of [../computes-and-jobs.md](../computes-and-jobs.md) "The lifecycle" |
  | `volcano_statistics.json` | `POST $E/computes/differentialexpression/statistics` with the same body |

  Example, and the `Accept` header matters: content negotiation is one exact
  string comparison, so `application/json, */*` yields TSV
  ([../subsetting-and-tabular.md](../subsetting-and-tabular.md), TSV or JSON).

  ```bash
  curl -s -H "Cookie: Authorization=$TOK" "$E/studies" \
    | python3 -m json.tool > $F/studies_list.json
  curl -s -H "Cookie: Authorization=$TOK" -H 'Accept: application/json' \
    -H 'Content-Type: application/json' \
    -X POST "$E/studies/STUDY_53f554ec6a/entities/GENE_PHENOTYPE_DATA_ENTITY/tabular" \
    -d '{"filters":[],"outputVariableIds":["VEUPATHDB_GENE_ID"],"reportConfig":{"paging":{"numRows":5,"offset":0}}}' \
    | python3 -m json.tool > $F/tabular_json.json
  ```

- [ ] **Trim the two large fixtures so the suite stays fast.** `studies_list.json`
      keeps the first 40 `studies` entries plus every entry whose `sha1hash` is
      the empty string (the `user_submitted` rows, which are the exception the
      cache key must handle). `volcano_statistics.json` keeps the first 200
      `statistics` rows plus the one row that omits `pValue`
      (`PF3D7_MIT04200` in the recorded run,
      [../visualizations.md](../visualizations.md)). `permissions.json` keeps
      the first 40 `perDataset` entries plus every entry missing
      `shortDisplayName` or `description` (24 of 880 live). Do the trim with a
      Python script under the scratchpad, never by hand.

- [ ] **Record what was trimmed.** Add a plain-text
      `fixtures/README.txt` naming, per file, the endpoint, the study id and
      the trim rule. One line each, no history, no dates.

- [ ] Verify: `ls $F` shows eleven `.json` files plus `README.txt`, and
      `python3 -c "import json,sys,glob; [json.load(open(p)) for p in glob.glob('$F/*.json')]"`
      exits 0.

**Trap:** do not record from `clinepidb.org`. The genomics deployment and the
ClinEpi deployment are different EDA instances with different id conventions
([../data-model.md](../data-model.md), "Two deployments"). Batch 1 pins the
genomics wire because that is the one the gene bridge uses.

---

### Task A2 - `EdaModel`, the study catalog and the permissions map

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/integrations/eda/test_study_models.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from pathfinder.integrations.eda.models import (
    EdaPermissionsResponse,
    EdaStudiesResponse,
    EdaStudyOverview,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> object:
    return json.loads((FIXTURES / name).read_text())


def test_study_overview_tolerates_a_missing_short_display_name() -> None:
    """shortDisplayName and description are declared required and are absent live."""
    overview = EdaStudyOverview.model_validate(
        {
            "id": "STUDY_ccab256dfb",
            "datasetId": "DS_ccab256dfb",
            "sha1hash": "ccab256dfb7c9562dfa35f36345348ad2f2d5dfa",
            "sourceType": "curated",
            "displayName": "S. cerevisiae transcriptomes",
            "lastModified": "2026-05-27T20:00:00-04:00",
        }
    )
    assert overview.short_display_name is None
    assert overview.description is None
    assert overview.dataset_id == "DS_ccab256dfb"


def test_study_overview_keeps_the_lowercase_sha1hash_key() -> None:
    """/studies spells it sha1hash; /permissions spells it sha1Hash."""
    overview = EdaStudyOverview.model_validate(
        {
            "id": "STUDY_x",
            "datasetId": "DS_x",
            "sha1hash": "abc",
            "sourceType": "curated",
            "displayName": "x",
            "lastModified": "2026-05-27T20:00:00-04:00",
        }
    )
    assert overview.sha1hash == "abc"
    assert overview.model_dump(by_alias=True)["sha1hash"] == "abc"


def test_a_user_study_carries_an_empty_sha1hash() -> None:
    parsed = EdaStudiesResponse.model_validate(_load("studies_list.json"))
    user_studies = [s for s in parsed.studies if s.source_type == "user_submitted"]
    assert user_studies
    assert all(s.sha1hash == "" for s in user_studies)
    assert all(s.dataset_id.startswith("EDAUD_") for s in user_studies)


def test_permission_entry_spells_the_hash_with_a_capital_h() -> None:
    parsed = EdaPermissionsResponse.model_validate(_load("permissions.json"))
    entry = parsed.per_dataset["DS_53f554ec6a"]
    assert entry.study_id == "STUDY_53f554ec6a"
    assert entry.sha1_hash
    assert entry.action_authorization.results_all is True


def test_permission_entries_that_omit_declared_required_fields_still_parse() -> None:
    """24 of 880 live entries omit shortDisplayName or description."""
    parsed = EdaPermissionsResponse.model_validate(_load("permissions.json"))
    sparse = [
        e
        for e in parsed.per_dataset.values()
        if e.short_display_name is None or e.description is None
    ]
    assert sparse, "the trimmed fixture must retain the sparse entries"


def test_an_unmodelled_extra_field_is_ignored() -> None:
    overview = EdaStudyOverview.model_validate(
        {
            "id": "STUDY_x",
            "datasetId": "DS_x",
            "sha1hash": "",
            "sourceType": "user_submitted",
            "displayName": "x",
            "lastModified": "2026-05-27T20:00:00-04:00",
            "somethingUpstreamAddedLater": 1,
        }
    )
    assert not hasattr(overview, "somethingUpstreamAddedLater")
```

- [ ] **Run it and read the failure.** Expect
      `ModuleNotFoundError: No module named 'pathfinder.integrations.eda'`.

  ```bash
  cd apps/api && uv run pytest src/pathfinder/tests/unit/integrations/eda/test_study_models.py -v
  ```

- [ ] **Minimal implementation.** Create
      `apps/api/src/pathfinder/integrations/eda/__init__.py` empty, and
      `apps/api/src/pathfinder/integrations/eda/models.py`:

```python
"""Pydantic mirrors of the EDA REST wire shapes.

Python field names are snake_case; the camelCase keys come from the alias
generator. Two field names carry an upstream spelling the generator cannot
reach and name it explicitly.
"""

from __future__ import annotations

from typing import Annotated, Literal

from assistant_core.platform.pydantic_base import CamelModel
from assistant_core.platform.types import JSONObject
from pydantic import (
    AliasChoices,
    ConfigDict,
    Discriminator,
    Field,
    TypeAdapter,
)
from pydantic.alias_generators import to_camel


class EdaModel(CamelModel):
    """Base for all EDA REST wire models."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="ignore",
        frozen=True,
    )


class EdaVariableSpec(EdaModel):
    entity_id: str
    variable_id: str


class EdaCollectionSpec(EdaModel):
    entity_id: str
    collection_id: str


EdaSourceType = Literal["curated", "user_submitted"]


class EdaStudyOverview(EdaModel):
    """One element of ``GET /studies``. ``id`` is a study id, never parseable."""

    id: str
    dataset_id: str
    sha1hash: str = ""
    source_type: EdaSourceType
    display_name: str
    short_display_name: str | None = None
    description: str | None = None
    last_modified: str = ""


class EdaStudiesResponse(EdaModel):
    studies: list[EdaStudyOverview] = Field(default_factory=list)


class EdaActionAuthorization(EdaModel):
    study_metadata: bool = False
    subsetting: bool = False
    visualizations: bool = False
    results_first_page: bool = False
    results_all: bool = False


class EdaPermissionEntry(EdaModel):
    """One ``perDataset`` entry. The hash key is ``sha1Hash`` here."""

    study_id: str
    sha1_hash: str = Field(
        default="",
        validation_alias=AliasChoices("sha1Hash", "sha1_hash"),
    )
    is_user_study: bool = False
    display_name: str = ""
    short_display_name: str | None = None
    description: str | None = None
    type: str = ""
    action_authorization: EdaActionAuthorization = Field(
        default_factory=EdaActionAuthorization,
    )
    is_manager: bool = False
    access_request_status: str = ""


class EdaPermissionsResponse(EdaModel):
    per_dataset: dict[str, EdaPermissionEntry] = Field(default_factory=dict)
```

  `sha1hash` needs no alias: `to_camel("sha1hash")` is `sha1hash`. `sha1_hash`
  would generate `sha1Hash` on its own, and the explicit `AliasChoices` states
  the disagreement at the one place it matters. `validation_alias` is the form
  already used in this repository (`integrations/veupathdb/site_router.py`
  `SiteInfo.id`); a bare `alias=` is banned by the `CamelModel` docstring.

- [ ] **Gates.**

  ```bash
  cd apps/api && uv run ruff check src/ \
    && uv run mypy --strict src/pathfinder/ \
    && uv run pyright src/pathfinder/ \
    && uv run pytest src/pathfinder/tests/unit/integrations/eda/test_study_models.py -v
  ```

---

### Task A3 - the entity tree, the six-member variable union, the collection

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/integrations/eda/test_variable_union.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from pathfinder.integrations.eda.models import (
    EdaCategoryVariable,
    EdaCollection,
    EdaEntity,
    EdaLongitudeVariable,
    EdaNumberVariable,
    EdaStringVariable,
    EdaStudyDetailResponse,
    EdaVariable,
)

FIXTURES = Path(__file__).parent / "fixtures"
VARIABLE = TypeAdapter(EdaVariable)


def test_type_discriminates_a_string_variable() -> None:
    parsed = VARIABLE.validate_python(
        {
            "id": "VAR_035294d0",
            "parentId": "GENE_PHENOTYPE_DATA_ENTITY",
            "providerLabel": "No Provider Label available",
            "displayName": "Species",
            "displayType": "default",
            "type": "string",
            "hideFrom": [],
            "dataShape": "categorical",
            "vocabulary": ["P. berghei", "P. falciparum", "P. yoelii"],
            "distinctValuesCount": 3,
            "isMultiValued": True,
        }
    )
    assert isinstance(parsed, EdaStringVariable)
    assert parsed.is_multi_valued is True
    assert parsed.vocabulary == ["P. berghei", "P. falciparum", "P. yoelii"]


def test_a_category_variable_carries_no_value_fields() -> None:
    parsed = VARIABLE.validate_python(
        {
            "id": "EUPATH_0000321",
            "parentId": "EUPATH_0000308",
            "providerLabel": "No Provider Label available",
            "displayName": "Diagnosis at discharge",
            "displayType": "multifilter",
            "displayOrder": 4,
            "type": "category",
            "hideFrom": [],
        }
    )
    assert isinstance(parsed, EdaCategoryVariable)
    assert not hasattr(parsed, "vocabulary")
    assert not hasattr(parsed, "data_shape")


def test_is_category_is_not_modelled() -> None:
    """Declared required in the RAML, absent on all 66664 variables scanned."""
    parsed = VARIABLE.validate_python(
        {
            "id": "V",
            "displayName": "v",
            "providerLabel": "p",
            "displayType": "default",
            "type": "category",
            "hideFrom": [],
            "isCategory": "true",
        }
    )
    assert not hasattr(parsed, "is_category")


def test_distribution_defaults_carry_only_three_of_six_keys() -> None:
    parsed = VARIABLE.validate_python(
        {
            "id": "SEQUENCE_READ_COUNT",
            "displayName": "read count",
            "providerLabel": "p",
            "displayType": "default",
            "type": "number",
            "hideFrom": [],
            "dataShape": "continuous",
            "distributionDefaults": {
                "rangeMin": 0,
                "rangeMax": 1684173,
                "binWidth": 54329,
            },
        }
    )
    assert isinstance(parsed, EdaNumberVariable)
    assert parsed.distribution_defaults.display_range_min is None
    assert parsed.distribution_defaults.range_max == 1684173


def test_scale_is_not_modelled() -> None:
    parsed = VARIABLE.validate_python(
        {
            "id": "V",
            "displayName": "v",
            "providerLabel": "p",
            "displayType": "default",
            "type": "number",
            "hideFrom": [],
            "scale": "log2",
        }
    )
    assert not hasattr(parsed, "scale")


def test_longitude_is_its_own_type() -> None:
    parsed = VARIABLE.validate_python(
        {
            "id": "OBI_0001621",
            "displayName": "longitude",
            "providerLabel": "p",
            "displayType": "longitude",
            "type": "longitude",
            "hideFrom": [],
            "precision": 1.0,
        }
    )
    assert isinstance(parsed, EdaLongitudeVariable)


def test_an_unknown_variable_type_is_refused() -> None:
    with pytest.raises(ValidationError):
        VARIABLE.validate_python(
            {
                "id": "V",
                "displayName": "v",
                "providerLabel": "p",
                "displayType": "default",
                "type": "geoaggregator",
                "hideFrom": [],
            }
        )


def test_the_entity_tree_is_recursive_and_children_are_optional() -> None:
    raw = json.loads((FIXTURES / "study_detail_de.json").read_text())
    detail = EdaStudyDetailResponse.model_validate(raw).study
    root = detail.root_entity
    assert root.id_column_name.endswith("_stable_id")
    assert root.children, "the DE study has a child counts entity"
    leaf = root.children[0]
    assert leaf.children == []
    assert isinstance(leaf, EdaEntity)


def test_normalization_method_null_is_a_string_value_not_absence() -> None:
    collection = EdaCollection.model_validate(
        {
            "id": "EUPATH_0005051",
            "displayName": "Eigengene",
            "type": "number",
            "dataShape": "continuous",
            "memberVariableIds": ["VAR_a", "VAR_b"],
            "imputeZero": False,
            "normalizationMethod": "NULL",
            "isCompositional": False,
            "isProportion": False,
            "member": "eigengene",
            "memberPlural": "eigengenes",
        }
    )
    assert collection.normalization_method == "NULL"
```

- [ ] **Run it.** Expect `ImportError: cannot import name 'EdaEntity'`.

- [ ] **Implementation.** Append to `models.py`:

```python
EdaVariableDataShape = Literal["continuous", "categorical", "ordinal", "binary"]
EdaVariableDisplayType = Literal[
    "default",
    "hidden",
    "multifilter",
    "geoaggregator",
    "latitude",
    "longitude",
]
EdaBinUnits = Literal["day", "week", "month", "year"]


class EdaNumberDistributionDefaults(EdaModel):
    display_range_min: float | None = None
    display_range_max: float | None = None
    range_min: float | None = None
    range_max: float | None = None
    bin_width: float | None = None
    bin_width_override: float | None = None


class EdaDateDistributionDefaults(EdaModel):
    display_range_min: str | None = None
    display_range_max: str | None = None
    range_min: str | None = None
    range_max: str | None = None
    bin_width: int | None = None
    bin_width_override: int | None = None
    bin_units: EdaBinUnits | None = None


class EdaVariableBase(EdaModel):
    id: str
    parent_id: str | None = None
    provider_label: str = ""
    display_name: str = ""
    definition: str | None = None
    display_type: EdaVariableDisplayType = "default"
    display_order: int | None = None
    hide_from: list[str] = Field(default_factory=list)


class EdaValueVariableBase(EdaVariableBase):
    data_shape: EdaVariableDataShape | None = None
    vocabulary: list[str] | None = None
    distinct_values_count: int = 0
    is_temporal: bool = False
    is_featured: bool = False
    is_merge_key: bool = False
    is_multi_valued: bool = False
    impute_zero: bool = False
    has_study_dependent_vocabulary: bool | None = None
    variable_spec_to_impute_zeroes_for: EdaVariableSpec | None = None


class EdaStringVariable(EdaValueVariableBase):
    type: Literal["string"] = "string"


class EdaIntegerVariable(EdaValueVariableBase):
    type: Literal["integer"] = "integer"
    distribution_defaults: EdaNumberDistributionDefaults = Field(
        default_factory=EdaNumberDistributionDefaults,
    )
    units: str | None = None


class EdaNumberVariable(EdaValueVariableBase):
    type: Literal["number"] = "number"
    distribution_defaults: EdaNumberDistributionDefaults = Field(
        default_factory=EdaNumberDistributionDefaults,
    )
    units: str | None = None
    precision: float | None = None


class EdaDateVariable(EdaValueVariableBase):
    type: Literal["date"] = "date"
    distribution_defaults: EdaDateDistributionDefaults = Field(
        default_factory=EdaDateDistributionDefaults,
    )


class EdaLongitudeVariable(EdaValueVariableBase):
    type: Literal["longitude"] = "longitude"
    precision: float | None = None


class EdaCategoryVariable(EdaVariableBase):
    """A tree node with no data. ``multifilter`` display makes it a filter target."""

    type: Literal["category"] = "category"


EdaVariable = Annotated[
    EdaStringVariable
    | EdaIntegerVariable
    | EdaNumberVariable
    | EdaDateVariable
    | EdaLongitudeVariable
    | EdaCategoryVariable,
    Discriminator("type"),
]


EdaCollectionType = Literal["number", "date", "integer", "string"]


class EdaCollection(EdaModel):
    """Same-typed variables on one entity. Reference it as (entityId, collectionId)."""

    id: str
    display_name: str = ""
    type: EdaCollectionType
    data_shape: EdaVariableDataShape | None = None
    vocabulary: list[str] | None = None
    distinct_values_count: int | None = None
    member_variable_ids: list[str] = Field(default_factory=list)
    impute_zero: bool = False
    normalization_method: str | None = None
    is_compositional: bool = False
    is_proportion: bool = False
    variable_spec_to_impute_zeroes_for: EdaVariableSpec | None = None
    member: str = ""
    member_plural: str = ""
    units: str | None = None
    precision: float | None = None


class EdaEntity(EdaModel):
    """One table of records. ``children`` is present only in the study call."""

    id: str
    id_column_name: str = ""
    display_name: str = ""
    display_name_plural: str = ""
    description: str = ""
    is_many_to_one_with_parent: bool = False
    variables: list[EdaVariable] = Field(default_factory=list)
    collections: list[EdaCollection] = Field(default_factory=list)
    children: list[EdaEntity] = Field(default_factory=list)


class EdaStudyDetail(EdaModel):
    """``GET /studies/{studyId}``. Carries no datasetId and no displayName."""

    id: str
    is_user_study: bool = False
    has_map: bool = False
    root_entity: EdaEntity


class EdaStudyDetailResponse(EdaModel):
    study: EdaStudyDetail
```

  `id_column_name` and `is_many_to_one_with_parent` default rather than being
  required because `GET /studies/{s}/entities/{e}` omits both. The client never
  calls that endpoint (task B4), and the default keeps the model honest about
  the one response that does.

- [ ] **Gates**, as in task A2, with
      `src/pathfinder/tests/unit/integrations/eda/test_variable_union.py`.

---

### Task A4 - the seven-member filter union

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/integrations/eda/test_filter_union.py`:

```python
from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from pathfinder.integrations.eda.models import (
    EdaFilter,
    EdaLongitudeRangeFilter,
    EdaMultiFilter,
    EdaStringSetFilter,
)

FILTER = TypeAdapter(EdaFilter)
FILTERS = TypeAdapter(list[EdaFilter])


def test_string_set_round_trips_the_wire_shape() -> None:
    raw = {
        "entityId": "GENE_PHENOTYPE_DATA_ENTITY",
        "variableId": "VAR_035294d0",
        "type": "stringSet",
        "stringSet": ["P. berghei"],
    }
    parsed = FILTER.validate_python(raw)
    assert isinstance(parsed, EdaStringSetFilter)
    assert parsed.model_dump(by_alias=True, exclude_none=True) == raw


def test_an_empty_string_set_is_refused_before_the_wire() -> None:
    """The service answers 400 'String set filter: >0 strings must be specified'."""
    with pytest.raises(ValidationError):
        FILTER.validate_python(
            {
                "entityId": "E",
                "variableId": "V",
                "type": "stringSet",
                "stringSet": [],
            }
        )


def test_longitude_range_uses_left_and_right() -> None:
    parsed = FILTER.validate_python(
        {
            "entityId": "GAZ_00000448",
            "variableId": "OBI_0001621",
            "type": "longitudeRange",
            "left": 15.0,
            "right": 16.0,
        }
    )
    assert isinstance(parsed, EdaLongitudeRangeFilter)
    assert parsed.left == 15.0
    assert parsed.right == 16.0


def test_multi_filter_sub_filters_carry_no_entity_and_no_type() -> None:
    raw = {
        "entityId": "EUPATH_0000096",
        "variableId": "EUPATH_0000321",
        "type": "multiFilter",
        "operation": "union",
        "subFilters": [
            {"variableId": "EUPATH_0015135", "stringSet": ["Yes"]},
            {"variableId": "EUPATH_0033376", "stringSet": ["Yes"]},
        ],
    }
    parsed = FILTER.validate_python(raw)
    assert isinstance(parsed, EdaMultiFilter)
    assert parsed.operation == "union"
    assert parsed.model_dump(by_alias=True, exclude_none=True) == raw


def test_multi_filter_refuses_an_empty_sub_filter_list() -> None:
    with pytest.raises(ValidationError):
        FILTER.validate_python(
            {
                "entityId": "E",
                "variableId": "V",
                "type": "multiFilter",
                "operation": "union",
                "subFilters": [],
            }
        )


def test_multi_filter_refuses_an_operation_outside_the_two() -> None:
    with pytest.raises(ValidationError):
        FILTER.validate_python(
            {
                "entityId": "E",
                "variableId": "V",
                "type": "multiFilter",
                "operation": "xor",
                "subFilters": [{"variableId": "C", "stringSet": ["Yes"]}],
            }
        )


def test_string_prefix_set_is_refused() -> None:
    """Schema-present, source-present, wire-absent: the deployed build 422s it."""
    with pytest.raises(ValidationError):
        FILTER.validate_python(
            {
                "entityId": "E",
                "variableId": "V",
                "type": "stringPrefixSet",
                "prefixSet": ["ab"],
            }
        )


def test_an_extra_property_on_a_filter_is_dropped() -> None:
    parsed = FILTER.validate_python(
        {
            "entityId": "E",
            "variableId": "V",
            "type": "stringSet",
            "stringSet": ["yes"],
            "extraJunk": 1,
        }
    )
    assert "extraJunk" not in parsed.model_dump(by_alias=True)


def test_a_filter_array_serializes_as_a_bare_list() -> None:
    raw = [
        {
            "entityId": "E",
            "variableId": "V1",
            "type": "stringSet",
            "stringSet": ["a"],
        },
        {
            "entityId": "E",
            "variableId": "V2",
            "type": "numberRange",
            "min": 0.0,
            "max": 100.0,
        },
    ]
    parsed = FILTERS.validate_python(raw)
    assert FILTERS.dump_python(parsed, by_alias=True, exclude_none=True) == raw
```

- [ ] **Run it.** Expect `ImportError: cannot import name 'EdaFilter'`.

- [ ] **Implementation.** Append to `models.py`:

```python
class EdaFilterBase(EdaModel):
    """Every filter names one variable on one entity."""

    entity_id: str
    variable_id: str


class EdaStringSetFilter(EdaFilterBase):
    type: Literal["stringSet"] = "stringSet"
    string_set: list[str] = Field(min_length=1)


class EdaNumberSetFilter(EdaFilterBase):
    type: Literal["numberSet"] = "numberSet"
    number_set: list[float] = Field(min_length=1)


class EdaDateSetFilter(EdaFilterBase):
    type: Literal["dateSet"] = "dateSet"
    date_set: list[str] = Field(min_length=1)


class EdaNumberRangeFilter(EdaFilterBase):
    type: Literal["numberRange"] = "numberRange"
    min: float
    max: float


class EdaDateRangeFilter(EdaFilterBase):
    """Bounds carry a time: a bare YYYY-MM-DD is a server error."""

    type: Literal["dateRange"] = "dateRange"
    min: str
    max: str


class EdaLongitudeRangeFilter(EdaFilterBase):
    """``left == right`` is a no-op that keeps every row."""

    type: Literal["longitudeRange"] = "longitudeRange"
    left: float
    right: float


class EdaSubFilter(EdaModel):
    """A multiFilter child. The parent's entity applies and the set is a string set."""

    variable_id: str
    string_set: list[str] = Field(min_length=1)


class EdaMultiFilter(EdaFilterBase):
    """The one nested type, and the only way to express OR."""

    type: Literal["multiFilter"] = "multiFilter"
    operation: Literal["union", "intersect"]
    sub_filters: list[EdaSubFilter] = Field(min_length=1)


EdaFilter = Annotated[
    EdaStringSetFilter
    | EdaNumberSetFilter
    | EdaDateSetFilter
    | EdaNumberRangeFilter
    | EdaDateRangeFilter
    | EdaLongitudeRangeFilter
    | EdaMultiFilter,
    Discriminator("type"),
]
```

- [ ] **Gates**, with
      `src/pathfinder/tests/unit/integrations/eda/test_filter_union.py`.

**Trap named:** `min` and `max` are the wire names. Do not rename them to
`minimum`/`maximum`; `longitudeRange` deliberately uses `left`/`right` instead,
and that asymmetry is upstream's, not a mistake to smooth over.

---

### Task A5 - the analysis document, its computation and the volcano descriptor

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/integrations/eda/test_analysis_models.py`:

```python
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from pathfinder.integrations.eda.models import (
    EdaAnalysisDescriptor,
    EdaComparator,
    EdaComputation,
    EdaComputationDescriptor,
    EdaDifferentialExpressionConfig,
    EdaLabeledRange,
    EdaNewAnalysis,
    EdaStringSetFilter,
    EdaSubsetDescriptor,
    EdaVariableSpec,
    EdaVisualization,
    EdaVolcanoConfiguration,
    EdaVolcanoDescriptor,
)


def _config() -> EdaDifferentialExpressionConfig:
    return EdaDifferentialExpressionConfig(
        identifier_variable=EdaVariableSpec(
            entity_id="ENT_fd574cd6", variable_id="VEUPATHDB_GENE_ID"
        ),
        value_variable=EdaVariableSpec(
            entity_id="ENT_fd574cd6", variable_id="SEQUENCE_READ_COUNT_ANTISENSE"
        ),
        comparator=EdaComparator(
            variable=EdaVariableSpec(
                entity_id="ENT_8151325d", variable_id="VAR_081ab087"
            ),
            group_a=[EdaLabeledRange(label="normal")],
            group_b=[EdaLabeledRange(label="febrile")],
        ),
    )


def test_study_id_holds_a_dataset_id_and_keeps_the_upstream_name() -> None:
    analysis = EdaNewAnalysis(
        study_id="DS_e973eadd57", display_name="probe"
    )
    dumped = analysis.model_dump(by_alias=True, exclude_none=True)
    assert dumped["studyId"] == "DS_e973eadd57"
    assert "datasetId" not in dumped


def test_derived_variables_hold_ids_not_specs() -> None:
    descriptor = EdaAnalysisDescriptor(derived_variables=["dv-abc-123"])
    assert descriptor.model_dump(by_alias=True)["derivedVariables"] == ["dv-abc-123"]


def test_a_derived_variable_spec_object_is_refused() -> None:
    """An inline object in that array is a 422 upstream."""
    with pytest.raises(ValidationError):
        EdaAnalysisDescriptor.model_validate(
            {"derivedVariables": [{"entityId": "E", "variableId": "V"}]}
        )


def test_an_empty_analysis_serializes_the_full_descriptor_skeleton() -> None:
    analysis = EdaNewAnalysis(study_id="DS_x", display_name="x")
    dumped = analysis.model_dump(by_alias=True, exclude_none=True)
    assert dumped["descriptor"] == {
        "subset": {"descriptor": [], "uiSettings": {}},
        "computations": [],
        "starredVariables": [],
        "dataTableConfig": {},
        "derivedVariables": [],
    }


def test_the_bridge_spec_round_trips_byte_for_byte() -> None:
    """The recorded spec of the measured 202-then-200 sequence."""
    analysis = EdaNewAnalysis(
        study_id="DS_e973eadd57",
        display_name="...",
        description="",
        is_public=False,
        descriptor=EdaAnalysisDescriptor(
            subset=EdaSubsetDescriptor(),
            computations=[
                EdaComputation(
                    computation_id="de2",
                    descriptor=EdaComputationDescriptor(configuration=_config()),
                    visualizations=[
                        EdaVisualization(
                            visualization_id="v2",
                            display_name="Volcano",
                            descriptor=EdaVolcanoDescriptor(
                                configuration=EdaVolcanoConfiguration(
                                    effect_size_threshold=1.0,
                                    significance_threshold=0.05,
                                ),
                            ),
                        )
                    ],
                )
            ],
        ),
    )
    dumped = json.loads(
        analysis.model_dump_json(by_alias=True, exclude_none=True)
    )
    computation = dumped["descriptor"]["computations"][0]
    assert computation["descriptor"]["type"] == "differentialexpression"
    assert (
        computation["descriptor"]["configuration"]["differentialExpressionMethod"]
        == "DESeq"
    )
    assert computation["descriptor"]["configuration"]["pValueFloor"] == "1e-200"
    viz = computation["visualizations"][0]["descriptor"]
    assert viz["type"] == "volcanoplot"
    assert viz["configuration"]["effectSizeThreshold"] == 1.0
    assert viz["configuration"]["significanceThreshold"] == 0.05
    assert viz["configuration"]["effectDirection"] == "upAndDown"


def test_deseq2_is_not_a_wire_value() -> None:
    """The frontend display name is DESeq2; the wire enum is DESeq."""
    with pytest.raises(ValidationError):
        EdaDifferentialExpressionConfig.model_validate(
            {
                "identifierVariable": {"entityId": "E", "variableId": "V"},
                "valueVariable": {"entityId": "E", "variableId": "W"},
                "comparator": {
                    "variable": {"entityId": "P", "variableId": "C"},
                    "groupA": [{"label": "a"}],
                    "groupB": [{"label": "b"}],
                },
                "differentialExpressionMethod": "DESeq2",
            }
        )


def test_a_labeled_range_may_carry_a_label_alone() -> None:
    group = EdaLabeledRange.model_validate({"label": "normal"})
    assert group.min is None
    assert group.max is None
    assert group.model_dump(by_alias=True, exclude_none=True) == {"label": "normal"}


def test_a_comparator_group_may_not_be_empty() -> None:
    with pytest.raises(ValidationError):
        EdaComparator.model_validate(
            {
                "variable": {"entityId": "P", "variableId": "C"},
                "groupA": [],
                "groupB": [{"label": "b"}],
            }
        )


def test_a_subset_descriptor_holds_the_typed_filter_array() -> None:
    subset = EdaSubsetDescriptor.model_validate(
        {
            "descriptor": [
                {
                    "entityId": "GENE_PHENOTYPE_DATA_ENTITY",
                    "variableId": "VAR_035294d0",
                    "type": "stringSet",
                    "stringSet": ["P. berghei"],
                }
            ],
            "uiSettings": {},
        }
    )
    assert isinstance(subset.descriptor[0], EdaStringSetFilter)
```

- [ ] **Run it.** Expect `ImportError: cannot import name 'EdaNewAnalysis'`.

- [ ] **Implementation.** Append to `models.py`:

```python
class EdaLabeledRange(EdaModel):
    """A comparator bin. ``min``/``max`` are declared required and are optional."""

    label: str
    min: str | None = None
    max: str | None = None


class EdaComparator(EdaModel):
    variable: EdaVariableSpec
    group_a: list[EdaLabeledRange] = Field(min_length=1)
    group_b: list[EdaLabeledRange] = Field(min_length=1)


class EdaDifferentialExpressionConfig(EdaModel):
    """The compute's own configuration. There is no collectionVariable here."""

    identifier_variable: EdaVariableSpec
    value_variable: EdaVariableSpec
    comparator: EdaComparator
    differential_expression_method: Literal["DESeq", "limma"] = "DESeq"
    p_value_floor: str = "1e-200"


class EdaComputationDescriptor(EdaModel):
    type: Literal["differentialexpression"] = "differentialexpression"
    configuration: EdaDifferentialExpressionConfig


class EdaVolcanoConfiguration(EdaModel):
    """The thresholds the WDK bridge plugin requires on the visualization."""

    effect_size_threshold: float
    significance_threshold: float
    effect_direction: Literal["upOnly", "downOnly", "upAndDown"] = "upAndDown"


class EdaVolcanoDescriptor(EdaModel):
    type: Literal["volcanoplot"] = "volcanoplot"
    configuration: EdaVolcanoConfiguration
    current_plot_filters: list[EdaFilter] = Field(default_factory=list)


class EdaVisualization(EdaModel):
    visualization_id: str
    display_name: str = ""
    descriptor: EdaVolcanoDescriptor


class EdaComputation(EdaModel):
    computation_id: str
    display_name: str = ""
    descriptor: EdaComputationDescriptor
    visualizations: list[EdaVisualization] = Field(default_factory=list)


class EdaSubsetDescriptor(EdaModel):
    descriptor: list[EdaFilter] = Field(default_factory=list)
    ui_settings: JSONObject = Field(default_factory=dict)


class EdaAnalysisDescriptor(EdaModel):
    """The whole semantic state. ``derivedVariables`` holds ids, not specs."""

    subset: EdaSubsetDescriptor = Field(default_factory=EdaSubsetDescriptor)
    computations: list[EdaComputation] = Field(default_factory=list)
    starred_variables: list[EdaVariableSpec] = Field(default_factory=list)
    data_table_config: JSONObject = Field(default_factory=dict)
    derived_variables: list[str] = Field(default_factory=list)


class EdaNewAnalysis(EdaModel):
    """``studyId`` holds a DATASET id and must equal ``eda_dataset_id``."""

    study_id: str
    display_name: str
    description: str = ""
    is_public: bool = False
    study_version: str | None = None
    api_version: str | None = None
    descriptor: EdaAnalysisDescriptor = Field(
        default_factory=EdaAnalysisDescriptor,
    )


class EdaAnalysisSummary(EdaModel):
    analysis_id: str
    display_name: str = ""
    description: str | None = None
    study_id: str = ""
    is_public: bool = False
    creation_time: str = ""
    modification_time: str = ""
    num_filters: int = 0
    num_computations: int = 0


class EdaAnalysisDetail(EdaAnalysisSummary):
    descriptor: EdaAnalysisDescriptor = Field(
        default_factory=EdaAnalysisDescriptor,
    )


class EdaCreateAnalysisResponse(EdaModel):
    analysis_id: str
```

  `EdaVisualization.descriptor` is typed to the volcano descriptor alone, not to
  an open union, because `GeneEdaVizWithComputePlugin.findVolcanoComputation`
  accepts a computation only if it carries a `volcanoplot` visualization whose
  configuration has both thresholds, and throws otherwise
  ([../notebook-presets.md](../notebook-presets.md), "The compute bridge
  supports volcano plots only"). A second visualization type is a new WSF plugin
  upstream, not a configuration change here.

- [ ] **Gates**, with
      `src/pathfinder/tests/unit/integrations/eda/test_analysis_models.py`.

---

### Task A6 - jobs, apps, statistics, count and distribution

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/integrations/eda/test_compute_models.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from pathfinder.integrations.eda.models import (
    TABULAR_JSON,
    EdaAppsResponse,
    EdaComputeJob,
    EdaCountResponse,
    EdaDistributionResponse,
    VolcanoStatsResponse,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> object:
    return json.loads((FIXTURES / name).read_text())


def test_the_job_id_key_is_capital_i_capital_d() -> None:
    job = EdaComputeJob.model_validate(_load("compute_job_lookup.json"))
    assert len(job.job_id) == 32
    assert job.status in {
        "queued",
        "in-progress",
        "complete",
        "failed",
        "expired",
        "no-such-job",
    }


def test_queue_position_is_absent_when_a_job_starts_at_once() -> None:
    job = EdaComputeJob.model_validate({"jobID": "a" * 32, "status": "queued"})
    assert job.queue_position is None


def test_volcano_numbers_arrive_as_strings() -> None:
    parsed = VolcanoStatsResponse.model_validate(_load("volcano_statistics.json"))
    first = parsed.statistics[0]
    assert isinstance(first.effect_size, str)
    assert isinstance(first.p_value, str)
    assert parsed.effect_size_label == "log2(Fold Change)"
    assert parsed.p_value_floor == "1e-200"
    assert parsed.adjusted_p_value_floor is None


def test_a_volcano_row_may_omit_both_p_values() -> None:
    parsed = VolcanoStatsResponse.model_validate(
        {
            "effectSizeLabel": "log2(Fold Change)",
            "statistics": [
                {"effectSize": "-1.49447459261845", "pointID": "PF3D7_MIT04200"}
            ],
        }
    )
    row = parsed.statistics[0]
    assert row.point_id == "PF3D7_MIT04200"
    assert row.p_value is None
    assert row.adjusted_p_value is None


def test_the_point_id_key_is_pointID_on_the_wire() -> None:
    parsed = VolcanoStatsResponse.model_validate(
        {"statistics": [{"effectSize": "1.0", "pointID": "PF3D7_0100200"}]}
    )
    assert parsed.statistics[0].point_id == "PF3D7_0100200"


def test_count_response_carries_only_a_count() -> None:
    parsed = EdaCountResponse.model_validate(_load("count_unfiltered.json"))
    assert parsed.count == 4279


def test_a_categorical_distribution_has_no_subset_min_or_mean() -> None:
    parsed = EdaDistributionResponse.model_validate(
        _load("distribution_categorical.json")
    )
    assert parsed.statistics.subset_min is None
    assert parsed.statistics.subset_mean is None
    assert parsed.statistics.subset_size == 4279
    assert parsed.statistics.num_var_values == 8409
    labels = {bin_.bin_label for bin_ in parsed.histogram}
    assert "P. berghei" in labels


def test_bin_bounds_are_strings_even_for_a_numeric_variable() -> None:
    parsed = EdaDistributionResponse.model_validate(
        {
            "histogram": [
                {
                    "value": 13,
                    "binStart": "0.0",
                    "binEnd": "5.0",
                    "binLabel": "[0.0,5.0)",
                }
            ],
            "statistics": {
                "subsetSize": 48721,
                "subsetMin": 3.0,
                "subsetMax": 18.9,
                "subsetMean": 12.032154770825814,
                "numVarValues": 36570,
                "numDistinctValues": 174,
                "numDistinctEntityRecords": 36570,
                "numMissingCases": 12151,
            },
        }
    )
    assert parsed.histogram[0].bin_start == "0.0"
    assert parsed.statistics.subset_mean is not None


def test_the_tabular_json_body_is_a_bare_array_of_arrays() -> None:
    rows = TABULAR_JSON.validate_python(_load("tabular_json.json"))
    assert rows[0][0].endswith("_stable_id")
    assert len(rows) > 1


def test_apps_declare_their_visualizations_and_their_projects() -> None:
    parsed = EdaAppsResponse.model_validate(_load("apps.json"))
    by_name = {app.name: app for app in parsed.apps}
    de = by_name["differentialexpression"]
    assert de.compute_name == "differentialexpression"
    assert [v.name for v in de.visualizations] == ["volcanoplot"]
    assert "PlasmoDB" in de.projects
    assert by_name["distributions"].compute_name is None
```

- [ ] **Run it.** Expect `ImportError: cannot import name 'EdaComputeJob'`.

- [ ] **Implementation.** Append to `models.py`:

```python
EdaJobStatus = Literal[
    "queued",
    "in-progress",
    "complete",
    "failed",
    "expired",
    "no-such-job",
]


class EdaComputeJob(EdaModel):
    """The job id is an MD5 of the request, so a caller never stores one."""

    job_id: str = Field(validation_alias=AliasChoices("jobID", "jobId", "job_id"))
    status: EdaJobStatus
    queue_position: int | None = None


class VolcanoStatsRow(EdaModel):
    """One point. Every number is a string, and a row may omit both p-values."""

    point_id: str = Field(
        validation_alias=AliasChoices("pointID", "pointId", "point_id"),
    )
    effect_size: str
    p_value: str | None = None
    adjusted_p_value: str | None = None


class VolcanoStatsResponse(EdaModel):
    effect_size_label: str = ""
    p_value_floor: str | None = None
    adjusted_p_value_floor: str | None = None
    statistics: list[VolcanoStatsRow] = Field(default_factory=list)


class EdaCountResponse(EdaModel):
    count: int


class EdaHistogramBin(EdaModel):
    value: float
    bin_start: str
    bin_end: str
    bin_label: str


class EdaDistributionStatistics(EdaModel):
    subset_size: int = 0
    subset_min: float | None = None
    subset_max: float | None = None
    subset_mean: float | None = None
    num_var_values: int = 0
    num_distinct_values: int = 0
    num_distinct_entity_records: int = 0
    num_missing_cases: int = 0


class EdaDistributionResponse(EdaModel):
    histogram: list[EdaHistogramBin] = Field(default_factory=list)
    statistics: EdaDistributionStatistics = Field(
        default_factory=EdaDistributionStatistics,
    )


class EdaVisualizationOverview(EdaModel):
    name: str
    display_name: str = ""
    description: str = ""
    projects: list[str] = Field(default_factory=list)
    max_panels: int = 1


class EdaAppInfo(EdaModel):
    """An app with no ``computeName`` is a pass-through and takes no computeConfig."""

    name: str
    display_name: str = ""
    description: str = ""
    projects: list[str] = Field(default_factory=list)
    compute_name: str | None = None
    visualizations: list[EdaVisualizationOverview] = Field(default_factory=list)


class EdaAppsResponse(EdaModel):
    apps: list[EdaAppInfo] = Field(default_factory=list)


TABULAR_JSON: TypeAdapter[list[list[str]]] = TypeAdapter(list[list[str]])
"""The JSON tabular body is a bare array of arrays, header row first."""
```

  **Why the statistics are `str` and not `Decimal`.** Two reasons, in order.
  First, the precedent is decided: `WDKEnrichmentRowBase` in
  `integrations/veupathdb/wdk_models.py` types every enrichment statistic as
  `str` with the docstring "Every value arrives as a string, including the
  numeric ones". Second, the wire carries values like `"1.95781599815607e-05"`
  and a row that omits `pValue` entirely; the threshold comparison is a
  consumer-side `float()` inside one helper
  (`services/eda/compute.py::retained_rows`, batch 2), which is exactly where
  the WDK bridge plugin puts it - it catches a per-row parse failure and drops
  the row. Parsing to `Decimal` at the boundary would move that decision into a
  layer that cannot drop a row, and would round-trip differently from the
  bytes upstream sent. Keep the wire's own representation at the wire.

- [ ] **Gates**, with
      `src/pathfinder/tests/unit/integrations/eda/test_compute_models.py`.

---

### Task A7 - the fixture sweep

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/integrations/eda/test_fixtures_validate.py`:

```python
"""Every recorded response validates against the model that reads it."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from pathfinder.integrations.eda.models import (
    TABULAR_JSON,
    EdaAppsResponse,
    EdaComputeJob,
    EdaCountResponse,
    EdaDistributionResponse,
    EdaPermissionsResponse,
    EdaStudiesResponse,
    EdaStudyDetailResponse,
    VolcanoStatsResponse,
)

FIXTURES = Path(__file__).parent / "fixtures"

READERS: dict[str, Callable[[object], object]] = {
    "studies_list.json": EdaStudiesResponse.model_validate,
    "study_detail_de.json": EdaStudyDetailResponse.model_validate,
    "study_detail_phenotype.json": EdaStudyDetailResponse.model_validate,
    "permissions.json": EdaPermissionsResponse.model_validate,
    "count_unfiltered.json": EdaCountResponse.model_validate,
    "count_filtered.json": EdaCountResponse.model_validate,
    "distribution_categorical.json": EdaDistributionResponse.model_validate,
    "tabular_json.json": TABULAR_JSON.validate_python,
    "apps.json": EdaAppsResponse.model_validate,
    "compute_job_lookup.json": EdaComputeJob.model_validate,
    "volcano_statistics.json": VolcanoStatsResponse.model_validate,
}


def test_every_fixture_file_has_a_reader() -> None:
    on_disk = {p.name for p in FIXTURES.glob("*.json")}
    assert on_disk == set(READERS)


@pytest.mark.parametrize("name", sorted(READERS))
def test_fixture_validates(name: str) -> None:
    raw = json.loads((FIXTURES / name).read_text())
    reader = READERS[name]
    reader(raw)
```

- [ ] **Run it.** With tasks A1 to A6 done it should pass on the first run; if a
      fixture fails, the model is wrong, not the fixture.

- [ ] **Gates**, with the whole directory:

  ```bash
  cd apps/api && uv run ruff check src/ \
    && uv run mypy --strict src/pathfinder/ \
    && uv run pyright src/pathfinder/ \
    && uv run pytest src/pathfinder/tests/unit/integrations/eda/ -v
  ```

- [ ] **Section end.** Run the full unit suite and the import contracts:

  ```bash
  cd apps/api && uv run pytest src/pathfinder/tests/unit/ -v && uv run lint-imports
  ```

---

## Implementer B: `integrations/eda/client.py`, `analyses.py`, and the base URL

### Files

| Action | Path |
|---|---|
| Create | `apps/api/src/pathfinder/integrations/eda/errors.py` |
| Create | `apps/api/src/pathfinder/integrations/eda/client.py` |
| Create | `apps/api/src/pathfinder/integrations/eda/analyses.py` |
| Create | `apps/api/src/pathfinder/integrations/eda/factory.py` |
| Modify | `apps/api/src/pathfinder/integrations/veupathdb/site_router.py` (add one property) |
| Create | `apps/api/src/pathfinder/tests/unit/integrations/eda/test_eda_base_url.py` |
| Create | `apps/api/src/pathfinder/tests/unit/integrations/eda/test_error_mapping.py` |
| Create | `apps/api/src/pathfinder/tests/integration/eda/__init__.py` |
| Create | `apps/api/src/pathfinder/tests/integration/eda/test_client_hermetic.py` |
| Create | `apps/api/src/pathfinder/tests/integration/eda/test_client_live.py` |

### Interfaces

**Consumes** (implementer A, task A2 to A6): every name in the Produces list of
implementer A.

**Produces:**

```python
# integrations/veupathdb/site_router.py
SiteInfo.eda_base_url -> str          # property, f"{self.site_origin}/eda"

# integrations/eda/errors.py
class EdaError(AppError)               # base, status carried through
class EdaBadRequestError(EdaError)     # 400 - a name or a type did not check out
class EdaInvalidInputError(EdaError)   # 422 - the JSON did not deserialize
class EdaForbiddenError(EdaError)      # 403 - permission, or a dataset id where a study id belongs
class EdaNotFoundError(EdaError)       # 404
class EdaServerError(EdaError)         # 500 - so far only an unparseable date
class EdaComputeNotReadyError(EdaError)  # 400 "Compute results are not available..."
# A wire 401 has NO dedicated class: it carries through as the base EdaError
# with status 401. The missing-token case never reaches the wire - the client
# raises WDKLoginRequiredError before sending anything. The acceptance suite
# pins both readings.

# integrations/eda/client.py
class EdaClient:
    def __init__(self, *, base_url: str, timeout: float = 60.0) -> None
    async def close(self) -> None
    async def list_studies(self) -> list[EdaStudyOverview]
    async def get_study(self, study_id: str) -> EdaStudyDetail
    async def get_permissions(self) -> dict[str, EdaPermissionEntry]
    async def count(self, *, study_id: str, entity_id: str,
                    filters: Sequence[EdaFilter]) -> int
    async def tabular(self, *, study_id: str, entity_id: str,
                      filters: Sequence[EdaFilter],
                      output_variable_ids: Sequence[str],
                      num_rows: int | None = None,
                      offset: int = 0) -> list[list[str]]
    async def distribution(self, *, study_id: str, entity_id: str, variable_id: str,
                           filters: Sequence[EdaFilter],
                           bin_spec: EdaBinSpec | None = None,
                           ) -> EdaDistributionResponse
    async def list_apps(self) -> list[EdaAppInfo]
    async def submit_compute(self, *, compute_name: str, study_id: str,
                             config: EdaDifferentialExpressionConfig,
                             filters: Sequence[EdaFilter],
                             autostart: bool = True) -> EdaComputeJob
    async def get_job(self, job_id: str) -> EdaComputeJob
    async def compute_statistics(self, *, compute_name: str, study_id: str,
                                 config: EdaDifferentialExpressionConfig,
                                 filters: Sequence[EdaFilter],
                                 ) -> VolcanoStatsResponse
    async def visualization_data(self, *, app: str, viz: str, study_id: str,
                                 compute_config: EdaDifferentialExpressionConfig,
                                 filters: Sequence[EdaFilter],
                                 ) -> VolcanoStatsResponse

# integrations/eda/models.py addition (task B3)
class EdaBinSpec(EdaModel)

# integrations/eda/analyses.py
class EdaAnalysesClient:
    def __init__(self, *, client: EdaClient, project_id: str) -> None
    async def resolve_user_id(self, wdk_client: VEuPathDBClient) -> str
    async def create(self, *, user_id: str, analysis: EdaNewAnalysis
                     ) -> EdaCreateAnalysisResponse
    async def get(self, *, user_id: str, analysis_id: str) -> EdaAnalysisDetail
    async def patch_descriptor(self, *, user_id: str, analysis_id: str,
                               descriptor: EdaAnalysisDescriptor) -> None
    async def rename(self, *, user_id: str, analysis_id: str,
                     display_name: str) -> None
    async def delete(self, *, user_id: str, analysis_id: str) -> None

# integrations/eda/factory.py
def get_eda_client(site_id: str) -> EdaClient
def get_eda_analyses_client(site_id: str) -> EdaAnalysesClient
async def close_all_eda_clients() -> None
```

---

### Task B1 - `SiteInfo.eda_base_url`

**The decision, stated so no implementer re-opens it.** The EDA base URL is
derived from the site host, not from a new environment variable. The reason is
measured: `https://{site}/eda` is verified live on plasmodb.org and
clinepidb.org ([../rest-surface.md](../rest-surface.md)), the sites are already
enumerated in `integrations/veupathdb/sites.yaml`, and `SiteInfo` already owns
the derivation that answers this exact question -
`site_origin` returns scheme plus host with no path, and exists precisely
because "site search lives at the origin, not under the WDK service prefix".
A new setting would be a second answer to "where is this site" and would break
the moment a site is added to the YAML.

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/integrations/eda/test_eda_base_url.py`:

```python
from __future__ import annotations

from pathfinder.integrations.veupathdb.factory import get_site, list_sites


def test_the_eda_base_url_is_the_site_origin_plus_eda() -> None:
    site = get_site("plasmodb")
    assert site.base_url == "https://plasmodb.org/plasmo/service"
    assert site.eda_base_url == "https://plasmodb.org/eda"


def test_every_configured_site_derives_an_eda_base_url() -> None:
    for site in list_sites():
        assert site.eda_base_url.endswith("/eda")
        assert "/service" not in site.eda_base_url
```

- [ ] **Run it.** Expect
      `AttributeError: 'SiteInfo' object has no attribute 'eda_base_url'`.

- [ ] **Implementation.** In
      `apps/api/src/pathfinder/integrations/veupathdb/site_router.py`, beside
      `site_origin`:

```python
    @property
    def eda_base_url(self) -> str:
        """Returns the EDA service URL, which lives at the site origin."""
        return f"{self.site_origin}/eda"
```

- [ ] **Gates**, with
      `src/pathfinder/tests/unit/integrations/eda/test_eda_base_url.py` and
      `src/pathfinder/tests/unit/integrations/veupathdb/`.

---

### Task B2 - the error classes and the status mapping

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/integrations/eda/test_error_mapping.py`:

```python
from __future__ import annotations

import pytest

from pathfinder.integrations.eda.errors import (
    EdaBadRequestError,
    EdaComputeNotReadyError,
    EdaForbiddenError,
    EdaInvalidInputError,
    EdaNotFoundError,
    EdaServerError,
    eda_failure,
)


def test_400_becomes_a_bad_request_carrying_the_service_message() -> None:
    error = eda_failure(
        "POST",
        "/studies/S/entities/E/count",
        400,
        '{"status":"bad-request","message":"Variable \'VAR_deadbeef\' is not found"}',
    )
    assert isinstance(error, EdaBadRequestError)
    assert error.status == 400
    assert error.detail is not None
    assert "VAR_deadbeef" in error.detail


def test_the_compute_not_ready_400_is_its_own_class() -> None:
    error = eda_failure(
        "POST",
        "/apps/differentialexpression/visualizations/volcanoplot",
        400,
        '{"status":"bad-request",'
        '"message":"Compute results are not available for the requested job."}',
    )
    assert isinstance(error, EdaComputeNotReadyError)


def test_422_names_the_offending_key() -> None:
    error = eda_failure(
        "POST",
        "/computes/differentialexpression",
        422,
        '{"status":"invalid-input","errors":{"general":[],"byKey":'
        '{"config":["Cannot deserialize value of type ... DESeq2"]}}}',
    )
    assert isinstance(error, EdaInvalidInputError)
    assert error.errors is not None


def test_403_is_forbidden_and_names_the_study_id_trap() -> None:
    error = eda_failure(
        "POST", "/computes/differentialexpression", 403, '{"status":"forbidden"}'
    )
    assert isinstance(error, EdaForbiddenError)
    assert error.detail is not None
    assert "STUDY_" in error.detail


def test_404_and_500_map_to_their_own_classes() -> None:
    assert isinstance(eda_failure("GET", "/jobs/x", 404, ""), EdaNotFoundError)
    assert isinstance(
        eda_failure(
            "POST",
            "/studies/S/entities/E/count",
            500,
            '{"status":"server-error","message":"Can\'t parse date/time string: 2017-05-05"}',
        ),
        EdaServerError,
    )


def test_an_unmapped_status_still_raises_an_eda_error() -> None:
    error = eda_failure("GET", "/studies", 418, "")
    assert error.status == 418


def test_every_eda_error_is_an_app_error() -> None:
    from pathfinder.platform.errors import AppError

    for status in (400, 403, 404, 422, 500):
        assert isinstance(eda_failure("GET", "/x", status, ""), AppError)
```

- [ ] **Run it.** Expect `ModuleNotFoundError`.

- [ ] **Implementation.** Create
      `apps/api/src/pathfinder/integrations/eda/errors.py`:

```python
"""Typed refusals from the EDA service, one class per status class."""

from __future__ import annotations

from assistant_core.platform.types import JSONArray
from pydantic import BaseModel, ConfigDict, Field

from pathfinder.platform.errors import AppError, ErrorCode

_COMPUTE_NOT_READY = "Compute results are not available"

_STUDY_ID_HINT = (
    "A dataset id where a study id belongs is refused as forbidden. "
    "Compute and visualization bodies take the STUDY_ id."
)


class EdaError(AppError):
    """Base for every EDA refusal."""

    def __init__(
        self,
        detail: str,
        status: int,
        errors: JSONArray | None = None,
    ) -> None:
        super().__init__(
            code=ErrorCode.EXTERNAL_SERVICE_ERROR,
            title="EDA service error",
            status=status,
            detail=detail,
            errors=errors,
        )


class EdaBadRequestError(EdaError):
    """A name or a type did not check out. The message is specific enough to repair."""


class EdaComputeNotReadyError(EdaError):
    """A compute-backed visualization whose job has not completed."""


class EdaInvalidInputError(EdaError):
    """The JSON did not deserialize. No variable was resolved."""


class EdaForbiddenError(EdaError):
    """Permission, or an id that is not a study id."""


class EdaNotFoundError(EdaError):
    """No such resource. A malformed job id lands here too."""


class EdaServerError(EdaError):
    """An unparseable date bound is an author error, not an outage."""


class _EdaKeyedErrors(BaseModel):
    """The 422 body's per-key messages, the only machine-readable rejection."""

    model_config = ConfigDict(extra="ignore")

    general: list[str] = Field(default_factory=list)
    by_key: dict[str, list[str]] = Field(
        default_factory=dict,
        validation_alias="byKey",
    )


class _EdaProblem(BaseModel):
    """The two refusal bodies the service returns."""

    model_config = ConfigDict(extra="ignore")

    status: str = ""
    message: str = ""
    errors: _EdaKeyedErrors | None = None


def eda_failure(method: str, path: str, status: int, body: str) -> EdaError:
    """Build the typed refusal for one non-2xx response."""
    problem = _parse(body)
    detail = f"{method} {path}: {problem.message or body[:500]}"
    keyed = _keyed(problem)
    if status == 400 and _COMPUTE_NOT_READY in problem.message:
        return EdaComputeNotReadyError(detail, status)
    if status == 400:
        return EdaBadRequestError(detail, status)
    if status == 403:
        return EdaForbiddenError(f"{detail}. {_STUDY_ID_HINT}", status)
    if status == 404:
        return EdaNotFoundError(detail, status)
    if status == 422:
        return EdaInvalidInputError(detail, status, keyed)
    if status >= 500:
        return EdaServerError(detail, status)
    return EdaError(detail, status)


def _parse(body: str) -> _EdaProblem:
    try:
        return _EdaProblem.model_validate_json(body)
    except ValueError:
        return _EdaProblem()


def _keyed(problem: _EdaProblem) -> JSONArray | None:
    if problem.errors is None:
        return None
    rows: JSONArray = [
        {"key": key, "messages": messages}
        for key, messages in sorted(problem.errors.by_key.items())
    ]
    if problem.errors.general:
        rows.append({"key": "general", "messages": problem.errors.general})
    return rows
```

- [ ] **Gates**, with
      `src/pathfinder/tests/unit/integrations/eda/test_error_mapping.py`.

---

### Task B3 - the client transport and the read endpoints

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/integration/eda/test_client_hermetic.py`.
      The transport is exercised with `httpx.MockTransport`, so the test is
      hermetic and still drives real request building - the `Accept` header, the
      query parameter, the body.

```python
"""The EDA client against the recorded wire, with no network."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from pathfinder.integrations.eda.client import EdaClient
from pathfinder.integrations.eda.errors import (
    EdaBadRequestError,
    EdaForbiddenError,
    EdaInvalidInputError,
)
from pathfinder.integrations.eda.models import (
    EdaComparator,
    EdaDifferentialExpressionConfig,
    EdaLabeledRange,
    EdaStringSetFilter,
    EdaVariableSpec,
)
from pathfinder.platform.context import veupathdb_auth_token_ctx

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


def _client(handler: httpx.MockTransport) -> EdaClient:
    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(handler)
    return client


def _species_filter() -> EdaStringSetFilter:
    return EdaStringSetFilter(
        entity_id="GENE_PHENOTYPE_DATA_ENTITY",
        variable_id="VAR_035294d0",
        string_set=["P. berghei"],
    )


def _de_config() -> EdaDifferentialExpressionConfig:
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


async def test_the_request_carries_the_authorization_cookie() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_fixture("studies_list.json"))

    token = veupathdb_auth_token_ctx.set("token-abc")
    try:
        client = _client(httpx.MockTransport(handler))
        await client.list_studies()
    finally:
        veupathdb_auth_token_ctx.reset(token)
        await client.close()

    assert "Authorization=token-abc" in seen[0].headers["cookie"]
    assert seen[0].url.path == "/eda/studies"


async def test_list_studies_parses_the_recorded_catalog() -> None:
    client = _client(
        httpx.MockTransport(
            lambda _r: httpx.Response(200, json=_fixture("studies_list.json"))
        )
    )
    studies = await client.list_studies()
    await client.close()
    assert studies
    assert any(s.source_type == "user_submitted" for s in studies)


async def test_get_permissions_returns_the_resolution_map() -> None:
    client = _client(
        httpx.MockTransport(
            lambda _r: httpx.Response(200, json=_fixture("permissions.json"))
        )
    )
    per_dataset = await client.get_permissions()
    await client.close()
    assert per_dataset["DS_53f554ec6a"].study_id == "STUDY_53f554ec6a"


async def test_count_posts_the_filter_array_and_returns_an_int() -> None:
    seen: list[object] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"count": 4011})

    client = _client(httpx.MockTransport(handler))
    count = await client.count(
        study_id="STUDY_53f554ec6a",
        entity_id="GENE_PHENOTYPE_DATA_ENTITY",
        filters=[_species_filter()],
    )
    await client.close()
    assert count == 4011
    assert seen[0] == {
        "filters": [
            {
                "entityId": "GENE_PHENOTYPE_DATA_ENTITY",
                "variableId": "VAR_035294d0",
                "type": "stringSet",
                "stringSet": ["P. berghei"],
            }
        ]
    }


async def test_tabular_sends_the_accept_header_verbatim() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_fixture("tabular_json.json"))

    client = _client(httpx.MockTransport(handler))
    rows = await client.tabular(
        study_id="STUDY_53f554ec6a",
        entity_id="GENE_PHENOTYPE_DATA_ENTITY",
        filters=[],
        output_variable_ids=["VEUPATHDB_GENE_ID"],
        num_rows=5,
    )
    await client.close()
    assert seen[0].headers["accept"] == "application/json"
    assert rows[0][0].endswith("_stable_id")


async def test_tabular_sends_both_paging_keys_or_neither() -> None:
    seen: list[object] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=[["a"]])

    client = _client(httpx.MockTransport(handler))
    await client.tabular(
        study_id="S", entity_id="E", filters=[], output_variable_ids=[]
    )
    await client.tabular(
        study_id="S",
        entity_id="E",
        filters=[],
        output_variable_ids=[],
        num_rows=20,
        offset=40,
    )
    await client.close()
    assert "reportConfig" not in seen[0]
    assert seen[1]["reportConfig"] == {"paging": {"numRows": 20, "offset": 40}}


async def test_submit_compute_sends_autostart_and_the_study_id() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_fixture("compute_job_lookup.json"))

    client = _client(httpx.MockTransport(handler))
    job = await client.submit_compute(
        compute_name="differentialexpression",
        study_id="STUDY_e973eadd57",
        config=_de_config(),
        filters=[],
        autostart=False,
    )
    await client.close()
    assert seen[0].url.params["autostart"] == "false"
    body = json.loads(seen[0].content)
    assert body["studyId"] == "STUDY_e973eadd57"
    assert body["filters"] == []
    assert body["derivedVariables"] == []
    assert len(job.job_id) == 32


async def test_visualization_data_posts_compute_config_and_an_empty_config() -> None:
    seen: list[object] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=_fixture("volcano_statistics.json"))

    client = _client(httpx.MockTransport(handler))
    stats = await client.visualization_data(
        app="differentialexpression",
        viz="volcanoplot",
        study_id="STUDY_e973eadd57",
        compute_config=_de_config(),
        filters=[],
    )
    await client.close()
    assert seen[0]["config"] == {}
    assert "computeConfig" in seen[0]
    assert stats.statistics


async def test_a_400_becomes_a_bad_request_error() -> None:
    client = _client(
        httpx.MockTransport(
            lambda _r: httpx.Response(
                400,
                json={
                    "status": "bad-request",
                    "message": "Variable 'VAR_deadbeef' is not found",
                },
            )
        )
    )
    with pytest.raises(EdaBadRequestError):
        await client.count(study_id="S", entity_id="E", filters=[])
    await client.close()


async def test_a_403_on_a_compute_becomes_forbidden() -> None:
    client = _client(
        httpx.MockTransport(lambda _r: httpx.Response(403, json={"status": "forbidden"}))
    )
    with pytest.raises(EdaForbiddenError):
        await client.submit_compute(
            compute_name="differentialexpression",
            study_id="DS_e973eadd57",
            config=_de_config(),
            filters=[],
        )
    await client.close()


async def test_a_422_becomes_invalid_input() -> None:
    client = _client(
        httpx.MockTransport(
            lambda _r: httpx.Response(
                422,
                json={
                    "status": "invalid-input",
                    "errors": {"general": [], "byKey": {"config": ["bad enum"]}},
                },
            )
        )
    )
    with pytest.raises(EdaInvalidInputError):
        await client.submit_compute(
            compute_name="differentialexpression",
            study_id="STUDY_x",
            config=_de_config(),
            filters=[],
        )
    await client.close()
```

- [ ] **Run it.** Expect `ModuleNotFoundError: pathfinder.integrations.eda.client`.

- [ ] **Implementation.** Create
      `apps/api/src/pathfinder/integrations/eda/client.py`:

```python
"""Async HTTP client for one site's EDA service."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Literal

import httpx
from assistant_core.platform.logging import get_logger
from pydantic import JsonValue, TypeAdapter

from pathfinder.integrations.eda.errors import eda_failure
from pathfinder.integrations.eda.models import (
    TABULAR_JSON,
    EdaAppInfo,
    EdaAppsResponse,
    EdaBinSpec,
    EdaComputeJob,
    EdaCountResponse,
    EdaDifferentialExpressionConfig,
    EdaDistributionResponse,
    EdaFilter,
    EdaPermissionEntry,
    EdaPermissionsResponse,
    EdaStudyDetail,
    EdaStudyDetailResponse,
    EdaStudiesResponse,
    EdaStudyOverview,
    VolcanoStatsResponse,
)
from pathfinder.platform.context import veupathdb_auth_token_ctx
from pathfinder.platform.errors import WDKLoginRequiredError

logger = get_logger(__name__)

FILTERS: TypeAdapter[list[EdaFilter]] = TypeAdapter(list[EdaFilter])

# Content negotiation is one exact string comparison; any other value is TSV.
_JSON_ONLY = "application/json"


class EdaClient:
    """One site's EDA service. The request's own registered token authenticates it."""

    def __init__(self, *, base_url: str, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._transport: httpx.BaseTransport | None = None
        self._lock = asyncio.Lock()

    def install_transport(self, transport: httpx.BaseTransport) -> None:
        # Part of the pinned interface: every hermetic test in this plan,
        # including the frozen acceptance suite, injects its wire through it.
        """Pin the transport a test drives. Production leaves it unset."""
        self._transport = transport

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    async def _http(self) -> httpx.AsyncClient:
        if self._client is not None and not self._client.is_closed:
            return self._client
        async with self._lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(
                    base_url=self.base_url,
                    timeout=httpx.Timeout(self.timeout),
                    transport=self._transport,
                    headers={"Content-Type": _JSON_ONLY},
                )
            return self._client

    def _token(self) -> str:
        token = veupathdb_auth_token_ctx.get()
        if not token:
            raise WDKLoginRequiredError
        return token

    async def _request(
        self,
        method: Literal["GET", "POST", "PATCH", "DELETE"],
        path: str,
        *,
        json: JsonValue | None = None,
        params: dict[str, str] | None = None,
    ) -> JsonValue:
        client = await self._http()
        request = client.build_request(
            method,
            path,
            json=json,
            params=params,
            headers={"Accept": _JSON_ONLY, "Cookie": f"Authorization={self._token()}"},
        )
        response = await client.send(request)
        if response.status_code >= 400:
            raise eda_failure(method, path, response.status_code, response.text)
        if not response.content or not response.text.strip():
            return None
        return response.json()

    async def list_studies(self) -> list[EdaStudyOverview]:
        raw = await self._request("GET", "/studies")
        return EdaStudiesResponse.model_validate(raw).studies

    async def get_study(self, study_id: str) -> EdaStudyDetail:
        raw = await self._request("GET", f"/studies/{study_id}")
        return EdaStudyDetailResponse.model_validate(raw).study

    async def get_permissions(self) -> dict[str, EdaPermissionEntry]:
        raw = await self._request("GET", "/permissions")
        return EdaPermissionsResponse.model_validate(raw).per_dataset

    async def count(
        self,
        *,
        study_id: str,
        entity_id: str,
        filters: Sequence[EdaFilter],
    ) -> int:
        raw = await self._request(
            "POST",
            f"/studies/{study_id}/entities/{entity_id}/count",
            json={"filters": _filters(filters)},
        )
        return EdaCountResponse.model_validate(raw).count

    async def tabular(
        self,
        *,
        study_id: str,
        entity_id: str,
        filters: Sequence[EdaFilter],
        output_variable_ids: Sequence[str],
        num_rows: int | None = None,
        offset: int = 0,
    ) -> list[list[str]]:
        body: dict[str, JsonValue] = {
            "filters": _filters(filters),
            "outputVariableIds": list(output_variable_ids),
        }
        # An offset with no numRows is a server error, so both keys travel or neither.
        if num_rows is not None:
            body["reportConfig"] = {"paging": {"numRows": num_rows, "offset": offset}}
        raw = await self._request(
            "POST",
            f"/studies/{study_id}/entities/{entity_id}/tabular",
            json=body,
        )
        return TABULAR_JSON.validate_python(raw)

    async def distribution(
        self,
        *,
        study_id: str,
        entity_id: str,
        variable_id: str,
        filters: Sequence[EdaFilter],
        bin_spec: EdaBinSpec | None = None,
    ) -> EdaDistributionResponse:
        body: dict[str, JsonValue] = {
            "filters": _filters(filters),
            "valueSpec": "count",
        }
        # A binSpec is required for a continuous variable and refused otherwise.
        if bin_spec is not None:
            body["binSpec"] = bin_spec.model_dump(by_alias=True, exclude_none=True)
        raw = await self._request(
            "POST",
            f"/studies/{study_id}/entities/{entity_id}"
            f"/variables/{variable_id}/distribution",
            json=body,
        )
        return EdaDistributionResponse.model_validate(raw)

    async def list_apps(self) -> list[EdaAppInfo]:
        raw = await self._request("GET", "/apps")
        return EdaAppsResponse.model_validate(raw).apps

    async def submit_compute(
        self,
        *,
        compute_name: str,
        study_id: str,
        config: EdaDifferentialExpressionConfig,
        filters: Sequence[EdaFilter],
        autostart: bool = True,
    ) -> EdaComputeJob:
        raw = await self._request(
            "POST",
            f"/computes/{compute_name}",
            json=_compute_body(study_id, config, filters),
            params={"autostart": "true" if autostart else "false"},
        )
        return EdaComputeJob.model_validate(raw)

    async def get_job(self, job_id: str) -> EdaComputeJob:
        raw = await self._request("GET", f"/jobs/{job_id}")
        return EdaComputeJob.model_validate(raw)

    async def compute_statistics(
        self,
        *,
        compute_name: str,
        study_id: str,
        config: EdaDifferentialExpressionConfig,
        filters: Sequence[EdaFilter],
    ) -> VolcanoStatsResponse:
        raw = await self._request(
            "POST",
            f"/computes/{compute_name}/statistics",
            json=_compute_body(study_id, config, filters),
        )
        return VolcanoStatsResponse.model_validate(raw)

    async def visualization_data(
        self,
        *,
        app: str,
        viz: str,
        study_id: str,
        compute_config: EdaDifferentialExpressionConfig,
        filters: Sequence[EdaFilter],
    ) -> VolcanoStatsResponse:
        raw = await self._request(
            "POST",
            f"/apps/{app}/visualizations/{viz}",
            json={
                "studyId": study_id,
                "filters": _filters(filters),
                "computeConfig": compute_config.model_dump(
                    by_alias=True, mode="json", exclude_none=True
                ),
                "config": {},
            },
        )
        return VolcanoStatsResponse.model_validate(raw)


def _filters(filters: Sequence[EdaFilter]) -> JsonValue:
    return FILTERS.dump_python(list(filters), by_alias=True, mode="json")


def _compute_body(
    study_id: str,
    config: EdaDifferentialExpressionConfig,
    filters: Sequence[EdaFilter],
) -> dict[str, JsonValue]:
    """The submit body addresses the job, so a reader sends the same one."""
    return {
        "studyId": study_id,
        "filters": _filters(filters),
        "derivedVariables": [],
        "config": config.model_dump(by_alias=True, mode="json", exclude_none=True),
    }
```

  Add `EdaBinSpec` to `models.py` (this task owns it, implementer A does not):

```python
class EdaBinSpec(EdaModel):
    """Required for a continuous variable, refused for any other."""

    display_range_min: JsonValue = None
    display_range_max: JsonValue = None
    bin_width: float
    bin_units: EdaBinUnits | None = None
```

  Coordinate: implementer A owns `models.py`. Send `EdaBinSpec` and the
  `JsonValue` import to implementer A as a two-line addition, or land it in a
  fourth commit after A closes. Do not fork the module.

- [ ] **Gates**, with
      `src/pathfinder/tests/integration/eda/test_client_hermetic.py`.

**Traps named:**

- `Accept` must be the literal `application/json`. httpx appends nothing when
  the header is set explicitly, and `application/json, */*` yields TSV.
- The compute body sent to `/computes/{name}/statistics` must be byte-equal to
  the submit body, because that body is how the job is addressed. `_compute_body`
  is the one place it is built.
- `studyId` in a compute or visualization body is the STUDY id. A dataset id
  there is a 403, not a 404.
- No retry on a compute submission: `autostart=true` starts work, and a second
  attempt is a second start against a shared cache. This client does not retry
  at all; a read failure right after completion is the caller's retry
  (batch 2, `services/eda/compute.py`).

---

### Task B4 - `analyses.py` and the conversation binding helpers

- [ ] **Failing test.** Append to
      `apps/api/src/pathfinder/tests/integration/eda/test_client_hermetic.py`:

```python
async def test_create_analysis_posts_the_new_analysis_under_the_project() -> None:
    from pathfinder.integrations.eda.analyses import EdaAnalysesClient
    from pathfinder.integrations.eda.models import EdaNewAnalysis

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"analysisId": "t4fszEJ"})

    client = _client(httpx.MockTransport(handler))
    analyses = EdaAnalysesClient(client=client, project_id="PlasmoDB")
    created = await analyses.create(
        user_id="1216062453",
        analysis=EdaNewAnalysis(study_id="DS_53f554ec6a", display_name="probe"),
    )
    await client.close()
    assert created.analysis_id == "t4fszEJ"
    assert seen[0].url.path == "/eda/users/1216062453/analyses/PlasmoDB"
    body = json.loads(seen[0].content)
    assert body["studyId"] == "DS_53f554ec6a"
    assert body["descriptor"]["subset"]["descriptor"] == []


async def test_patch_descriptor_sends_only_the_descriptor() -> None:
    from pathfinder.integrations.eda.analyses import EdaAnalysesClient
    from pathfinder.integrations.eda.models import (
        EdaAnalysisDescriptor,
        EdaSubsetDescriptor,
    )

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    client = _client(httpx.MockTransport(handler))
    analyses = EdaAnalysesClient(client=client, project_id="PlasmoDB")
    await analyses.patch_descriptor(
        user_id="1",
        analysis_id="t4fszEJ",
        descriptor=EdaAnalysisDescriptor(
            subset=EdaSubsetDescriptor(descriptor=[_species_filter()]),
        ),
    )
    await client.close()
    assert seen[0].method == "PATCH"
    assert seen[0].url.path == "/eda/users/1/analyses/PlasmoDB/t4fszEJ"
    assert set(json.loads(seen[0].content)) == {"descriptor"}


async def test_delete_analysis_addresses_the_single_analysis() -> None:
    from pathfinder.integrations.eda.analyses import EdaAnalysesClient

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(202)

    client = _client(httpx.MockTransport(handler))
    analyses = EdaAnalysesClient(client=client, project_id="PlasmoDB")
    await analyses.delete(user_id="1", analysis_id="t4fszEJ")
    await client.close()
    assert seen[0].method == "DELETE"
```

- [ ] **Run it.** Expect `ModuleNotFoundError`.

- [ ] **Implementation.** Create
      `apps/api/src/pathfinder/integrations/eda/analyses.py`:

```python
"""CRUD over the persisted analysis document, the SSOT for one analysis."""

from __future__ import annotations

from pathfinder.integrations.eda.client import EdaClient
from pathfinder.integrations.eda.models import (
    EdaAnalysisDescriptor,
    EdaAnalysisDetail,
    EdaAnalysisSummary,
    EdaCreateAnalysisResponse,
    EdaNewAnalysis,
)
from pathfinder.integrations.veupathdb.client import VEuPathDBClient
from pathfinder.integrations.veupathdb.strategy_api.helpers import (
    resolve_wdk_user_id,
)
from pathfinder.platform.errors import WDKLoginRequiredError


class EdaAnalysesClient:
    """One project's analysis store for one user."""

    def __init__(self, *, client: EdaClient, project_id: str) -> None:
        self._client = client
        self._project_id = project_id

    async def resolve_user_id(self, wdk_client: VEuPathDBClient) -> str:
        """The numeric WDK user id the analysis routes are keyed by."""
        user_id = await resolve_wdk_user_id(wdk_client)
        if user_id is None:
            raise WDKLoginRequiredError
        return user_id

    def _root(self, user_id: str) -> str:
        return f"/users/{user_id}/analyses/{self._project_id}"

    @property
    def project_id(self) -> str:
        return self._project_id

    async def list_all(self, *, user_id: str) -> list[EdaAnalysisSummary]:
        raw = await self._client.request_json("GET", self._root(user_id))
        return ANALYSIS_SUMMARIES.validate_python(raw)

    async def create(
        self,
        *,
        user_id: str,
        analysis: EdaNewAnalysis,
    ) -> EdaCreateAnalysisResponse:
        raw = await self._client.request_json(
            "POST",
            self._root(user_id),
            json=analysis.model_dump(by_alias=True, mode="json", exclude_none=True),
        )
        return EdaCreateAnalysisResponse.model_validate(raw)

    async def get(self, *, user_id: str, analysis_id: str) -> EdaAnalysisDetail:
        raw = await self._client.request_json(
            "GET", f"{self._root(user_id)}/{analysis_id}"
        )
        return EdaAnalysisDetail.model_validate(raw)

    async def patch_descriptor(
        self,
        *,
        user_id: str,
        analysis_id: str,
        descriptor: EdaAnalysisDescriptor,
    ) -> None:
        await self._client.request_json(
            "PATCH",
            f"{self._root(user_id)}/{analysis_id}",
            json={
                "descriptor": descriptor.model_dump(
                    by_alias=True, mode="json", exclude_none=True
                )
            },
        )

    async def rename(
        self,
        *,
        user_id: str,
        analysis_id: str,
        display_name: str,
    ) -> None:
        await self._client.request_json(
            "PATCH",
            f"{self._root(user_id)}/{analysis_id}",
            json={"displayName": display_name},
        )

    async def delete(self, *, user_id: str, analysis_id: str) -> None:
        await self._client.request_json(
            "DELETE", f"{self._root(user_id)}/{analysis_id}"
        )
```

  and at module top, beside the imports:

```python
ANALYSIS_SUMMARIES: TypeAdapter[list[EdaAnalysisSummary]] = TypeAdapter(
    list[EdaAnalysisSummary],
)
```

  Rename `EdaClient._request` to a public `request_json` with the same
  signature so `analyses.py` uses it without reaching a private name, and
  update `client.py`'s own call sites in the same edit.

- [ ] **Gates**, with
      `src/pathfinder/tests/integration/eda/test_client_hermetic.py`.

---

### Task B5 - the factory and the live lane

- [ ] **Failing test (factory).** Append to
      `apps/api/src/pathfinder/tests/unit/integrations/eda/test_eda_base_url.py`:

```python
def test_the_factory_builds_one_client_per_site() -> None:
    from pathfinder.integrations.eda.factory import get_eda_client

    first = get_eda_client("plasmodb")
    again = get_eda_client("plasmodb")
    other = get_eda_client("toxodb")
    assert first is again
    assert first is not other
    assert first.base_url == "https://plasmodb.org/eda"


def test_the_analyses_client_carries_the_site_project_id() -> None:
    from pathfinder.integrations.eda.factory import get_eda_analyses_client

    assert get_eda_analyses_client("plasmodb").project_id == "PlasmoDB"
    assert get_eda_analyses_client("toxodb").project_id == "ToxoDB"
```

- [ ] **Implementation.** Create
      `apps/api/src/pathfinder/integrations/eda/factory.py`, modelled on
      `integrations/veupathdb/factory.py` plus the lazy per-site cache of
      `SiteRouter.get_client`:

```python
"""Integration entrypoints for the per-site EDA clients."""

from __future__ import annotations

import threading

from pathfinder.integrations.eda.analyses import EdaAnalysesClient
from pathfinder.integrations.eda.client import EdaClient
from pathfinder.integrations.veupathdb.factory import get_site

_clients: dict[str, EdaClient] = {}
_lock = threading.Lock()


def get_eda_client(site_id: str) -> EdaClient:
    """The EDA client for a site, created on first use."""
    if site_id in _clients:
        return _clients[site_id]
    with _lock:
        if site_id not in _clients:
            site = get_site(site_id)
            _clients[site_id] = EdaClient(base_url=site.eda_base_url)
        return _clients[site_id]


def get_eda_analyses_client(site_id: str) -> EdaAnalysesClient:
    """The analysis store for a site, keyed by that site's project id."""
    site = get_site(site_id)
    return EdaAnalysesClient(
        client=get_eda_client(site_id),
        project_id=site.project_id,
    )


async def close_all_eda_clients() -> None:
    """Close every cached EDA client."""
    for client in _clients.values():
        await client.close()
    _clients.clear()
```

- [ ] **Wire the teardown.** `main.py` already calls `close_all_clients()` on
      shutdown. Add `close_all_eda_clients()` beside it in the same lifespan
      block, and add a fixture in
      `apps/api/src/pathfinder/tests/conftest.py` beside
      `_close_wdk_clients_after_test` that closes the EDA clients after each
      test. A process-wide cache a test inherits is a flaky test.

- [ ] **Failing test (live lane).** Create
      `apps/api/src/pathfinder/tests/integration/eda/test_client_live.py`. It
      reuses the existing credential idiom exactly: the `require_wdk_creds`
      fixture from `tests/conftest.py` (which skips with
      `NO_CREDENTIALS_REASON` when the environment names no account) and the
      registered `live_wdk` marker. EDA takes the same registered WDK token, so
      no second credential and no second marker is introduced.

```python
"""Live EDA: the recorded fixtures still describe the deployment.

Gated on WDK_TEST_TOKEN, or WDK_TEST_EMAIL/WDK_TEST_PASSWORD (skipped unset).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pathfinder.integrations.eda.factory import get_eda_client
from pathfinder.integrations.eda.models import (
    EdaStringSetFilter,
    EdaStudiesResponse,
)
from pathfinder.platform.context import veupathdb_auth_token_ctx

pytestmark = [pytest.mark.live_wdk, pytest.mark.asyncio]

FIXTURES = (
    Path(__file__).resolve().parents[2]
    / "unit"
    / "integrations"
    / "eda"
    / "fixtures"
)

_PHENOTYPE_STUDY = "STUDY_53f554ec6a"
_PHENOTYPE_ENTITY = "GENE_PHENOTYPE_DATA_ENTITY"


async def test_the_live_study_catalog_still_parses(require_wdk_creds: str) -> None:
    token = veupathdb_auth_token_ctx.set(require_wdk_creds)
    try:
        studies = await get_eda_client("plasmodb").list_studies()
    finally:
        veupathdb_auth_token_ctx.reset(token)
    assert len(studies) > 500
    assert any(s.source_type == "user_submitted" for s in studies)


async def test_the_recorded_fields_are_still_a_subset_of_the_live_ones(
    require_wdk_creds: str,
) -> None:
    """A field the fixture carries and the wire dropped is drift worth failing on."""
    recorded = EdaStudiesResponse.model_validate(
        json.loads((FIXTURES / "studies_list.json").read_text())
    )
    token = veupathdb_auth_token_ctx.set(require_wdk_creds)
    try:
        live = await get_eda_client("plasmodb").list_studies()
    finally:
        veupathdb_auth_token_ctx.reset(token)
    live_ids = {s.id for s in live}
    assert {s.id for s in recorded.studies} <= live_ids


async def test_a_live_filtered_count_matches_the_recorded_one(
    require_wdk_creds: str,
) -> None:
    token = veupathdb_auth_token_ctx.set(require_wdk_creds)
    try:
        client = get_eda_client("plasmodb")
        unfiltered = await client.count(
            study_id=_PHENOTYPE_STUDY, entity_id=_PHENOTYPE_ENTITY, filters=[]
        )
        filtered = await client.count(
            study_id=_PHENOTYPE_STUDY,
            entity_id=_PHENOTYPE_ENTITY,
            filters=[
                EdaStringSetFilter(
                    entity_id=_PHENOTYPE_ENTITY,
                    variable_id="VAR_035294d0",
                    string_set=["P. berghei"],
                )
            ],
        )
    finally:
        veupathdb_auth_token_ctx.reset(token)
    assert unfiltered == 4279
    assert filtered == 4011


async def test_an_out_of_vocabulary_value_returns_zero_not_an_error(
    require_wdk_creds: str,
) -> None:
    """The 200-with-count-0 class the authoring validator is the only guard for."""
    token = veupathdb_auth_token_ctx.set(require_wdk_creds)
    try:
        count = await get_eda_client("plasmodb").count(
            study_id=_PHENOTYPE_STUDY,
            entity_id=_PHENOTYPE_ENTITY,
            filters=[
                EdaStringSetFilter(
                    entity_id=_PHENOTYPE_ENTITY,
                    variable_id="VAR_a8ad31c0",
                    string_set=["maybe"],
                )
            ],
        )
    finally:
        veupathdb_auth_token_ctx.reset(token)
    assert count == 0
```

- [ ] **Run the live lane once** with the credentials set, then confirm it skips
      cleanly without them:

  ```bash
  cd apps/api && uv run pytest src/pathfinder/tests/integration/eda/test_client_live.py -v
  cd apps/api && WDK_TEST_TOKEN= WDK_TEST_EMAIL= WDK_TEST_PASSWORD= \
    uv run pytest src/pathfinder/tests/integration/eda/test_client_live.py -v
  ```

- [ ] **Section end.**

  ```bash
  cd apps/api && uv run ruff check src/ \
    && uv run mypy --strict src/pathfinder/ \
    && uv run pyright src/pathfinder/ \
    && uv run pytest src/pathfinder/tests/unit/ src/pathfinder/tests/integration/eda/ -v \
    && uv run lint-imports
  ```

---

## Implementer C: `domain/eda.py` - the pure predicates

### Files

| Action | Path |
|---|---|
| Create | `apps/api/src/pathfinder/domain/eda.py` |
| Create | `apps/api/src/pathfinder/tests/unit/domain/eda/__init__.py` |
| Create | `apps/api/src/pathfinder/tests/unit/domain/eda/test_validate_filters.py` |
| Create | `apps/api/src/pathfinder/tests/unit/domain/eda/test_find_gene_entity.py` |
| Create | `apps/api/src/pathfinder/tests/unit/domain/eda/test_validate_compute_config.py` |

### Interfaces

**Consumes:** nothing. Read the note below before writing a line.

**Produces:**

```python
VEUPATHDB_GENE_ID: str                     # "VEUPATHDB_GENE_ID"
GENE_EXPRESSION_VALUE_IDS: frozenset[str]  # the five reserved value ids
DIFFERENTIAL_EXPRESSION_METHODS: frozenset[str]  # {"DESeq", "limma"}

class VariableFacts(Protocol)
class EntityFacts(Protocol)
class StudyFacts(Protocol)
class FilterFacts(Protocol)
class SubFilterFacts(Protocol)
class VariableSpecFacts(Protocol)
class ComparatorFacts(Protocol)
class ComputeConfigFacts(Protocol)

def walk_entities(root: EntityFacts) -> Iterator[EntityFacts]
def entity_by_id(root: EntityFacts, entity_id: str) -> EntityFacts | None
def variable_by_id(entity: EntityFacts, variable_id: str) -> VariableFacts | None
def ancestor_entity_ids(root: EntityFacts, entity_id: str) -> frozenset[str]
DeclaredRanges = Mapping[tuple[str, str], tuple[float, float]]
def validate_filters(study: StudyFacts, filters: Sequence[FilterFacts],
                     declared_ranges: DeclaredRanges | None = None) -> list[str]
def find_gene_entity(study: StudyFacts) -> GeneEntityResult
def validate_compute_config(study: StudyFacts, config: ComputeConfigFacts) -> list[str]

@dataclass(frozen=True, slots=True)
class GeneEntityResult:
    entity_id: str | None
    error: str | None
```

### The layering note - read this first

`apps/api/pyproject.toml` contract "Domain layer is pure" forbids
`pathfinder.domain` from importing `pathfinder.integrations`. The gate is
`uv run lint-imports` and it fails the build. CLAUDE.md forbids
`TYPE_CHECKING` imports as a way round it.

So `domain/eda.py` does **not** import `integrations/eda/models.py`. It declares
structural `Protocol` types and the integration models satisfy them by shape.
The precedent is in this repository:
`domain/strategy/types.py::SyncStateProtocol` is exactly this - a `Protocol` of
read-only properties that `domain/strategy/session.py` consumes while the
concrete class lives outside `domain/`. `domain/parameters/values.py`
`ParamSpecLimits` is a second instance.

This refines - it does not contradict -
[../pathfinder-architecture-fit.md](../pathfinder-architecture-fit.md) section
1.2, which says the predicates "take the integration models as arguments and
import nothing". They do take them; the annotation is a Protocol, which is what
"import nothing" costs under the contract.

**Consequence for the tests:** the unit tests build tiny frozen dataclasses
satisfying the Protocols. They must NOT import `integrations.eda.models` either,
or they would prove nothing about purity. Verifier 2 checks that the models
satisfy the Protocols from the other side (see the Verifier 2 section).

---

### Task C1 - the Protocols and the tree walk

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/domain/eda/test_find_gene_entity.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from pathfinder.domain.eda import (
    VEUPATHDB_GENE_ID,
    ancestor_entity_ids,
    entity_by_id,
    find_gene_entity,
    walk_entities,
)


@dataclass(frozen=True)
class Var:
    id: str
    type: str = "string"
    display_name: str = ""
    display_type: str = "default"
    parent_id: str | None = None
    vocabulary: list[str] | None = None
    is_multi_valued: bool = False
    data_shape: str | None = None


@dataclass(frozen=True)
class Ent:
    id: str
    display_name: str = ""
    variables: list[Var] = field(default_factory=list)
    children: list["Ent"] = field(default_factory=list)


@dataclass(frozen=True)
class Study:
    id: str
    root_entity: Ent


def _de_study() -> Study:
    counts = Ent(
        id="ENT_fd574cd6",
        display_name="pfal3D7 htseq counts",
        variables=[
            Var(id=VEUPATHDB_GENE_ID),
            Var(id="SEQUENCE_READ_COUNT_SENSE", type="number"),
        ],
    )
    samples = Ent(
        id="ENT_8151325d",
        display_name="Samples",
        variables=[Var(id="VAR_081ab087", vocabulary=["febrile", "normal"])],
        children=[counts],
    )
    return Study(id="STUDY_e973eadd57", root_entity=samples)


def test_walk_visits_the_root_and_every_descendant() -> None:
    ids = [entity.id for entity in walk_entities(_de_study().root_entity)]
    assert ids == ["ENT_8151325d", "ENT_fd574cd6"]


def test_entity_by_id_finds_a_descendant() -> None:
    found = entity_by_id(_de_study().root_entity, "ENT_fd574cd6")
    assert found is not None
    assert found.display_name == "pfal3D7 htseq counts"


def test_entity_by_id_returns_none_for_an_unknown_id() -> None:
    assert entity_by_id(_de_study().root_entity, "ENT_nope") is None


def test_ancestors_of_a_leaf_are_every_entity_above_it() -> None:
    assert ancestor_entity_ids(_de_study().root_entity, "ENT_fd574cd6") == frozenset(
        {"ENT_8151325d"}
    )


def test_ancestors_of_the_root_are_empty() -> None:
    assert ancestor_entity_ids(_de_study().root_entity, "ENT_8151325d") == frozenset()


def test_exactly_one_gene_id_variable_resolves_the_gene_entity() -> None:
    result = find_gene_entity(_de_study())
    assert result.entity_id == "ENT_fd574cd6"
    assert result.error is None


def test_no_gene_id_variable_is_an_error_naming_the_reserved_id() -> None:
    study = Study(id="S", root_entity=Ent(id="E", variables=[Var(id="V")]))
    result = find_gene_entity(study)
    assert result.entity_id is None
    assert result.error is not None
    assert VEUPATHDB_GENE_ID in result.error


def test_two_gene_id_variables_are_an_error_naming_both_entities() -> None:
    study = Study(
        id="S",
        root_entity=Ent(
            id="A",
            variables=[Var(id=VEUPATHDB_GENE_ID)],
            children=[Ent(id="B", variables=[Var(id=VEUPATHDB_GENE_ID)])],
        ),
    )
    result = find_gene_entity(study)
    assert result.entity_id is None
    assert result.error is not None
    assert "A" in result.error
    assert "B" in result.error
```

- [ ] **Run it.** Expect `ModuleNotFoundError: pathfinder.domain.eda`.

- [ ] **Implementation.** Create
      `apps/api/src/pathfinder/domain/eda.py`:

```python
"""Pure predicates over a fetched EDA study tree and a filter array.

The shapes are structural, so this module imports no other layer.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Protocol

VEUPATHDB_GENE_ID = "VEUPATHDB_GENE_ID"

GENE_EXPRESSION_VALUE_IDS = frozenset(
    {
        "SEQUENCE_READ_COUNT",
        "SEQUENCE_READ_COUNT_SENSE",
        "SEQUENCE_READ_COUNT_ANTISENSE",
        "NORMALIZED_EXPRESSION",
        "NORMALIZED_INTENSITY",
    }
)

DIFFERENTIAL_EXPRESSION_METHODS = frozenset({"DESeq", "limma"})

_MULTIFILTER_DISPLAY = "multifilter"


class VariableFacts(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def type(self) -> str: ...
    @property
    def display_name(self) -> str: ...
    @property
    def display_type(self) -> str: ...
    @property
    def parent_id(self) -> str | None: ...


class ValueVariableFacts(VariableFacts, Protocol):
    @property
    def vocabulary(self) -> list[str] | None: ...
    @property
    def is_multi_valued(self) -> bool: ...
    @property
    def data_shape(self) -> str | None: ...


class EntityFacts(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def display_name(self) -> str: ...
    @property
    def variables(self) -> Sequence[VariableFacts]: ...
    @property
    def children(self) -> Sequence[EntityFacts]: ...


class StudyFacts(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def root_entity(self) -> EntityFacts: ...


@dataclass(frozen=True, slots=True)
class GeneEntityResult:
    """The entity carrying the reserved gene id, or why there is not one."""

    entity_id: str | None
    error: str | None


def walk_entities(root: EntityFacts) -> Iterator[EntityFacts]:
    """Yield the root and then every descendant, depth first."""
    yield root
    for child in root.children:
        yield from walk_entities(child)


def entity_by_id(root: EntityFacts, entity_id: str) -> EntityFacts | None:
    for entity in walk_entities(root):
        if entity.id == entity_id:
            return entity
    return None


def variable_by_id(entity: EntityFacts, variable_id: str) -> VariableFacts | None:
    for variable in entity.variables:
        if variable.id == variable_id:
            return variable
    return None


def ancestor_entity_ids(root: EntityFacts, entity_id: str) -> frozenset[str]:
    """Every entity strictly above ``entity_id``.

    Empty both when the id names the root and when the tree does not carry it.
    Every caller in this module resolves existence with ``entity_by_id`` first,
    so the shared answer decides nothing.
    """
    return _ancestors(root, entity_id, ())


def _ancestors(
    entity: EntityFacts,
    entity_id: str,
    above: tuple[str, ...],
) -> frozenset[str]:
    if entity.id == entity_id:
        return frozenset(above)
    for child in entity.children:
        found = _ancestors(child, entity_id, (*above, entity.id))
        if found:
            return found
    return frozenset()


def find_gene_entity(study: StudyFacts) -> GeneEntityResult:
    """The study must carry exactly one ``VEUPATHDB_GENE_ID`` to export genes."""
    holders = [
        entity.id
        for entity in walk_entities(study.root_entity)
        if variable_by_id(entity, VEUPATHDB_GENE_ID) is not None
    ]
    if not holders:
        return GeneEntityResult(
            entity_id=None,
            error=(
                f"Study {study.id} carries no {VEUPATHDB_GENE_ID} variable, so it "
                f"cannot export a gene list to a strategy step."
            ),
        )
    if len(holders) > 1:
        return GeneEntityResult(
            entity_id=None,
            error=(
                f"Study {study.id} carries {VEUPATHDB_GENE_ID} on more than one "
                f"entity ({', '.join(sorted(holders))}), and the gene bridge "
                f"requires exactly one."
            ),
        )
    return GeneEntityResult(entity_id=holders[0], error=None)
```

  `_ancestors` returns on the first non-empty result, and a non-empty result is
  only possible on the branch that holds `entity_id`, because the accumulator
  always carries at least the parent's id. Do not add a second membership test:
  it would be a guard that is always true when the first one fires.

- [ ] **Gates**, with
      `src/pathfinder/tests/unit/domain/eda/test_find_gene_entity.py` and
      `uv run lint-imports`.

---

### Task C2 - `validate_filters`

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/domain/eda/test_validate_filters.py`.
      Reuse the `Var` / `Ent` / `Study` dataclasses of task C1 by lifting them
      into `apps/api/src/pathfinder/tests/unit/domain/eda/_facts.py` (a test
      support module, no production import) and importing from there in both
      test files.

```python
from __future__ import annotations

from dataclasses import dataclass, field

from pathfinder.domain.eda import validate_filters

from ._facts import Ent, Study, Var


@dataclass(frozen=True)
class Sub:
    variable_id: str
    string_set: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Filt:
    entity_id: str
    variable_id: str
    type: str
    string_set: list[str] = field(default_factory=list)
    number_set: list[float] = field(default_factory=list)
    date_set: list[str] = field(default_factory=list)
    min: float | str | None = None
    max: float | str | None = None
    left: float | None = None
    right: float | None = None
    operation: str = "union"
    sub_filters: list[Sub] = field(default_factory=list)


def _study() -> Study:
    return Study(
        id="STUDY_53f554ec6a",
        root_entity=Ent(
            id="GENE_PHENOTYPE_DATA_ENTITY",
            variables=[
                Var(
                    id="VAR_a8ad31c0",
                    type="string",
                    display_name="Success of Genetic Modification",
                    vocabulary=["no", "yes"],
                ),
                Var(
                    id="EUPATH_0043064",
                    type="integer",
                    display_name="count",
                    data_shape="continuous",
                ),
                Var(
                    id="EUPATH_0043256",
                    type="date",
                    display_name="Collection date",
                    vocabulary=["2017-05-05", "2017-05-11"],
                ),
                Var(id="OBI_0001621", type="longitude", display_name="longitude"),
                Var(
                    id="CAT_1",
                    type="category",
                    display_name="Diagnosis",
                    display_type="multifilter",
                ),
                Var(
                    id="CHILD_1",
                    type="string",
                    display_name="Malaria",
                    parent_id="CAT_1",
                    vocabulary=["Yes"],
                ),
            ],
        ),
    )


def _ok(*filters: Filt) -> list[str]:
    return validate_filters(_study(), list(filters))


def test_a_valid_string_set_produces_no_errors() -> None:
    assert _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="VAR_a8ad31c0",
            type="stringSet",
            string_set=["yes"],
        )
    ) == []


def test_an_unknown_entity_is_reported_with_its_id() -> None:
    errors = _ok(Filt(entity_id="ENT_nope", variable_id="V", type="stringSet",
                      string_set=["x"]))
    assert len(errors) == 1
    assert "ENT_nope" in errors[0]


def test_an_unknown_variable_is_reported_with_its_id() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="VAR_deadbeef",
            type="stringSet",
            string_set=["x"],
        )
    )
    assert len(errors) == 1
    assert "VAR_deadbeef" in errors[0]


def test_a_string_set_on_a_number_variable_names_the_expected_type() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="EUPATH_0043064",
            type="stringSet",
            string_set=["1"],
        )
    )
    assert len(errors) == 1
    assert "integer" in errors[0]
    assert "stringSet" in errors[0]


def test_a_number_range_on_a_longitude_variable_is_refused() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="OBI_0001621",
            type="numberRange",
            min=0.0,
            max=1.0,
        )
    )
    assert len(errors) == 1


def test_a_longitude_range_on_a_number_variable_is_refused() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="EUPATH_0043064",
            type="longitudeRange",
            left=0.0,
            right=1.0,
        )
    )
    assert len(errors) == 1


def test_a_string_set_on_a_category_variable_is_refused() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="CAT_1",
            type="stringSet",
            string_set=["Yes"],
        )
    )
    assert len(errors) == 1


def test_an_out_of_vocabulary_value_is_the_error_the_service_will_not_give() -> None:
    """Live this returns 200 with count 0, so this predicate is the only guard."""
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="VAR_a8ad31c0",
            type="stringSet",
            string_set=["maybe"],
        )
    )
    assert len(errors) == 1
    assert "maybe" in errors[0]
    assert "no" in errors[0]
    assert "yes" in errors[0]


def test_an_empty_string_set_is_refused() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="VAR_a8ad31c0",
            type="stringSet",
            string_set=[],
        )
    )
    assert len(errors) == 1


def test_a_bare_date_bound_is_refused_before_the_500() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="EUPATH_0043256",
            type="dateRange",
            min="2017-05-05",
            max="2017-05-08",
        )
    )
    assert len(errors) == 2
    assert all("T00:00:00" in e for e in errors)


def test_a_dated_bound_with_a_time_passes() -> None:
    assert _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="EUPATH_0043256",
            type="dateRange",
            min="2017-05-05T00:00:00",
            max="2017-05-08T00:00:00",
        )
    ) == []


def test_an_inverted_number_range_is_refused() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="EUPATH_0043064",
            type="numberRange",
            min=100.0,
            max=0.0,
        )
    )
    assert len(errors) == 1
    assert "min" in errors[0]


def test_a_degenerate_longitude_window_is_refused() -> None:
    """left == right silently selects every row, so it never means what it looks like."""
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="OBI_0001621",
            type="longitudeRange",
            left=15.5,
            right=15.5,
        )
    )
    assert len(errors) == 1


def test_a_multifilter_on_a_non_multifilter_variable_is_refused() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="VAR_a8ad31c0",
            type="multiFilter",
            operation="union",
            sub_filters=[Sub(variable_id="CHILD_1", string_set=["Yes"])],
        )
    )
    assert len(errors) == 1
    assert "multifilter" in errors[0]


def test_a_multifilter_sub_filter_must_be_a_child_of_the_category() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="CAT_1",
            type="multiFilter",
            operation="union",
            sub_filters=[Sub(variable_id="VAR_a8ad31c0", string_set=["yes"])],
        )
    )
    assert len(errors) == 1
    assert "VAR_a8ad31c0" in errors[0]


def test_a_well_formed_multifilter_passes() -> None:
    assert _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="CAT_1",
            type="multiFilter",
            operation="union",
            sub_filters=[Sub(variable_id="CHILD_1", string_set=["Yes"])],
        )
    ) == []


def test_two_disjoint_sets_on_one_single_valued_variable_are_refused() -> None:
    """The most likely way to silently produce nothing: 200 with count 0."""
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="VAR_a8ad31c0",
            type="stringSet",
            string_set=["yes"],
        ),
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="VAR_a8ad31c0",
            type="stringSet",
            string_set=["no"],
        ),
    )
    assert len(errors) == 1
    assert "one filter" in errors[0]


def test_every_error_is_reported_not_just_the_first() -> None:
    errors = _ok(
        Filt(entity_id="ENT_nope", variable_id="V", type="stringSet",
             string_set=["x"]),
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="VAR_a8ad31c0",
            type="stringSet",
            string_set=["maybe"],
        ),
    )
    assert len(errors) == 2
```

- [ ] **Run it.** Expect `ImportError: cannot import name 'validate_filters'`.

- [ ] **Implementation.** Append to `domain/eda.py`:

```python
_TYPES_FOR_FILTER: dict[str, frozenset[str]] = {
    "stringSet": frozenset({"string"}),
    "numberSet": frozenset({"number", "integer"}),
    "dateSet": frozenset({"date"}),
    "numberRange": frozenset({"number", "integer"}),
    "dateRange": frozenset({"date"}),
    "longitudeRange": frozenset({"longitude"}),
    "multiFilter": frozenset({"category"}),
}

_DATE_TIME_MARKER = "T"


class SubFilterFacts(Protocol):
    @property
    def variable_id(self) -> str: ...
    @property
    def string_set(self) -> Sequence[str]: ...


class FilterFacts(Protocol):
    @property
    def entity_id(self) -> str: ...
    @property
    def variable_id(self) -> str: ...
    @property
    def type(self) -> str: ...


def validate_filters(
    study: StudyFacts,
    filters: Sequence[FilterFacts],
    declared_ranges: DeclaredRanges | None = None,
) -> list[str]:
    """Every reason this filter array will not mean what it says.

    An empty list means the service will answer about the subset the author
    described. The service accepts several of these and answers count 0.
    """
    errors: list[str] = []
    for entry in filters:
        errors.extend(_one_filter(study, entry, declared_ranges or {}))
    errors.extend(_repeated_single_valued(study, filters))
    return errors
```

  The per-filter body. Every branch reads a named attribute on the concrete
  filter, and the union member decides which attributes exist, so the check is
  a lookup on `entry.type` and never an `isinstance` chain. Use
  `_payload(entry, name)` - a one-line typed accessor built on `Protocol`
  narrowing - or split `_one_filter` into one small function per `type` keyed
  by a `dict[str, Callable[...]]`. Choose the dict of small functions: it keeps
  each check three lines and states the seven types once.

  The checks each function performs, stated so nothing is guessed:

  | `type` | checks |
  |---|---|
  | every type | entity exists; variable exists on THAT entity; variable's `type` is in `_TYPES_FOR_FILTER[type]` |
  | `stringSet` | set is non-empty; every member is in the variable's `vocabulary` when it declares one |
  | `numberSet` | set is non-empty; when the variable is `integer`, every member is integral |
  | `dateSet` | set is non-empty; every member contains `T` |
  | `numberRange` | `min <= max`; both bounds inside `declared_ranges[(entityId, variableId)]` when the caller supplies one |
  | `dateRange` | both bounds contain `T`; `min <= max` as strings |
  | `longitudeRange` | `left != right` |
  | `multiFilter` | target variable is `category` with `displayType == "multifilter"`; `subFilters` non-empty; every sub-filter's `variableId` is a variable on the same entity whose `parentId` is the category id; every sub-filter's `stringSet` is non-empty and inside that child's vocabulary |

  And the cross-filter check:

  | check | rule |
  |---|---|
  | repeated single-valued variable | two or more `stringSet` filters on the same `(entityId, variableId)` where the variable's `isMultiValued` is false and the sets are disjoint. Message: express OR with one filter holding several members, never with two array entries. |

  **Where the declared numeric range comes from, and why it is an argument.**
  `distributionDefaults` has three different shapes across the variable union
  (absent on `string`, float-bounded on `number`/`integer`, string-bounded on
  `date`), so no single `Protocol` member describes it. Reading it inside
  `domain/eda.py` would mean narrowing a `Protocol` by a string compare, which
  pyright cannot do, and the only escapes are `getattr` or a cast - both
  banned. So the signature is:

```python
DeclaredRanges = Mapping[tuple[str, str], tuple[float, float]]


def validate_filters(
    study: StudyFacts,
    filters: Sequence[FilterFacts],
    declared_ranges: DeclaredRanges | None = None,
) -> list[str]:
```

  The caller builds the map where the concrete type already exists. Batch 2's
  `services/eda/authoring.py` walks the study's variables and matches the
  discriminated union with `match`, which is the union's own idiom and not an
  `isinstance` chain:

```python
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
```

  With no map, the range check is skipped and `min <= max` still runs. The
  bounds are a hint rather than a wall - live, `displayRangeMax: 20` did not
  stop a `[20.0,25.0)` bin coming back - so the message must say "outside the
  declared range", never "invalid".

- [ ] **Gates**, with
      `src/pathfinder/tests/unit/domain/eda/` and `uv run lint-imports`.

---

### Task C3 - `validate_compute_config`

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/domain/eda/test_validate_compute_config.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from pathfinder.domain.eda import VEUPATHDB_GENE_ID, validate_compute_config

from ._facts import Ent, Study, Var


@dataclass(frozen=True)
class Spec:
    entity_id: str
    variable_id: str


@dataclass(frozen=True)
class Group:
    label: str


@dataclass(frozen=True)
class Comparator:
    variable: Spec
    group_a: list[Group] = field(default_factory=list)
    group_b: list[Group] = field(default_factory=list)


@dataclass(frozen=True)
class Config:
    identifier_variable: Spec
    value_variable: Spec
    comparator: Comparator
    differential_expression_method: str = "DESeq"


def _study() -> Study:
    counts = Ent(
        id="ENT_fd574cd6",
        variables=[
            Var(id=VEUPATHDB_GENE_ID),
            Var(id="SEQUENCE_READ_COUNT_SENSE", type="number"),
        ],
    )
    return Study(
        id="STUDY_e973eadd57",
        root_entity=Ent(
            id="ENT_8151325d",
            variables=[
                Var(
                    id="VAR_081ab087",
                    display_name="temperature",
                    vocabulary=["febrile", "normal"],
                )
            ],
            children=[counts],
        ),
    )


def _config(**overrides: object) -> Config:
    base = Config(
        identifier_variable=Spec("ENT_fd574cd6", VEUPATHDB_GENE_ID),
        value_variable=Spec("ENT_fd574cd6", "SEQUENCE_READ_COUNT_SENSE"),
        comparator=Comparator(
            variable=Spec("ENT_8151325d", "VAR_081ab087"),
            group_a=[Group("normal")],
            group_b=[Group("febrile")],
        ),
    )
    return Config(**{**base.__dict__, **overrides})


def test_the_measured_working_configuration_is_accepted() -> None:
    assert validate_compute_config(_study(), _config()) == []


def test_the_two_input_variables_must_share_an_entity() -> None:
    """A different entity is accepted at submit and the job then fails."""
    errors = validate_compute_config(
        _study(),
        _config(value_variable=Spec("ENT_8151325d", "VAR_081ab087")),
    )
    assert len(errors) == 1
    assert "same entity" in errors[0]


def test_the_comparator_variable_must_sit_on_an_ancestor_entity() -> None:
    errors = validate_compute_config(
        _study(),
        _config(
            comparator=Comparator(
                variable=Spec("ENT_fd574cd6", "SEQUENCE_READ_COUNT_SENSE"),
                group_a=[Group("a")],
                group_b=[Group("b")],
            )
        ),
    )
    assert any("ancestor" in e for e in errors)


def test_a_group_label_outside_the_vocabulary_is_refused() -> None:
    """Accepted at submit; the job then produces a wrong or empty answer."""
    errors = validate_compute_config(
        _study(),
        _config(
            comparator=Comparator(
                variable=Spec("ENT_8151325d", "VAR_081ab087"),
                group_a=[Group("NOT_A_VALUE")],
                group_b=[Group("febrile")],
            )
        ),
    )
    assert len(errors) == 1
    assert "NOT_A_VALUE" in errors[0]
    assert "febrile" in errors[0]


def test_an_empty_group_is_refused() -> None:
    errors = validate_compute_config(
        _study(),
        _config(
            comparator=Comparator(
                variable=Spec("ENT_8151325d", "VAR_081ab087"),
                group_a=[],
                group_b=[Group("febrile")],
            )
        ),
    )
    assert any("groupA" in e for e in errors)


def test_the_two_groups_may_not_share_a_label() -> None:
    errors = validate_compute_config(
        _study(),
        _config(
            comparator=Comparator(
                variable=Spec("ENT_8151325d", "VAR_081ab087"),
                group_a=[Group("normal")],
                group_b=[Group("normal")],
            )
        ),
    )
    assert any("both groups" in e for e in errors)


def test_deseq2_is_refused_with_the_two_wire_values_named() -> None:
    errors = validate_compute_config(
        _study(), _config(differential_expression_method="DESeq2")
    )
    assert len(errors) == 1
    assert "DESeq" in errors[0]
    assert "limma" in errors[0]


def test_an_identifier_variable_that_is_not_the_reserved_gene_id_is_refused() -> None:
    errors = validate_compute_config(
        _study(),
        _config(identifier_variable=Spec("ENT_fd574cd6", "SEQUENCE_READ_COUNT_SENSE")),
    )
    assert any(VEUPATHDB_GENE_ID in e for e in errors)


def test_a_value_variable_outside_the_reserved_ids_is_refused() -> None:
    study = Study(
        id="S",
        root_entity=Ent(
            id="P",
            variables=[Var(id="C", vocabulary=["a", "b"])],
            children=[
                Ent(
                    id="E",
                    variables=[Var(id=VEUPATHDB_GENE_ID), Var(id="MADE_UP", type="number")],
                )
            ],
        ),
    )
    errors = validate_compute_config(
        study,
        Config(
            identifier_variable=Spec("E", VEUPATHDB_GENE_ID),
            value_variable=Spec("E", "MADE_UP"),
            comparator=Comparator(
                variable=Spec("P", "C"),
                group_a=[Group("a")],
                group_b=[Group("b")],
            ),
        ),
    )
    assert any("SEQUENCE_READ_COUNT" in e for e in errors)
```

- [ ] **Run it.** Expect `ImportError: cannot import name 'validate_compute_config'`.

- [ ] **Implementation.** Append to `domain/eda.py` the Protocols
      (`VariableSpecFacts`, `LabeledRangeFacts`, `ComparatorFacts`,
      `ComputeConfigFacts`) and:

```python
def validate_compute_config(
    study: StudyFacts,
    config: ComputeConfigFacts,
) -> list[str]:
    """Every reason this differentialexpression config will fail or mislead.

    Submission validates schema shape and study permission only, so a bad
    entity pairing or an out-of-vocabulary label reaches a failed job.
    """
```

  The checks, each one a named live measurement:

  | check | why |
  |---|---|
  | both input specs name an existing entity and an existing variable on it | a 200 at submit, a `failed` job later |
  | `identifierVariable.entityId == valueVariable.entityId` | the plugin throws `IllegalArgumentException` otherwise |
  | `identifierVariable.variableId == VEUPATHDB_GENE_ID` | the notebook's `allowedVariableIds` is exactly that one id |
  | `valueVariable.variableId in GENE_EXPRESSION_VALUE_IDS` | the notebook's `allowedVariableIds` is exactly those five |
  | comparator variable's entity is in `ancestor_entity_ids(root, identifier entity)` | the plugin reads it from an ancestor and dedups to one row per sample |
  | `groupA` and `groupB` are both non-empty | accepted at submit, meaningless afterwards |
  | no label appears in both groups | a sample cannot be its own control |
  | every label is in the comparator variable's `vocabulary` when it declares one | live, `{"label":"NOT_A_VALUE"}` is accepted at submit |
  | `differentialExpressionMethod in DIFFERENTIAL_EXPRESSION_METHODS` | `DESeq2` is a 422 with the enum quoted |

  Every message must name the offending value and the valid set, in the shape
  the `set_eda_filters` validator hands to `ModelRetry` in batch 3. A message
  the model cannot act on is a wasted retry.

- [ ] **Section end.**

  ```bash
  cd apps/api && uv run ruff check src/ \
    && uv run mypy --strict src/pathfinder/ \
    && uv run pyright src/pathfinder/ \
    && uv run pytest src/pathfinder/tests/unit/domain/eda/ -v \
    && uv run pytest src/pathfinder/tests/unit/ -v \
    && uv run lint-imports
  ```

---

## Verifier 1 - covers implementers A and B

### Re-run, from a clean checkout of their work

```bash
cd apps/api
uv run ruff check src/
uv run mypy --strict src/pathfinder/
uv run pyright src/pathfinder/
uv run lint-imports
uv run pytest src/pathfinder/tests/unit/integrations/eda/ -v
uv run pytest src/pathfinder/tests/integration/eda/test_client_hermetic.py -v
uv run pytest src/pathfinder/tests/unit/ -v
# credentials set for this one; then unset them and confirm a clean skip
uv run pytest src/pathfinder/tests/integration/eda/test_client_live.py -v
```

### Traps to hunt, by name

1. **Reject any model that requires `shortDisplayName` or `description`.** Both
   are declared required upstream and absent live (14 and 2 of 759 studies; 24
   of 880 permission entries). Grep `models.py` for those two fields and check
   both are `| None = None`.
2. **Reject `sha1hash` spelled as one key for both endpoints.** `/studies` sends
   `sha1hash`, `/permissions` sends `sha1Hash`. Both must parse, and
   `EdaStudyOverview.model_dump(by_alias=True)` must emit `sha1hash`.
3. **Reject a modelled `isCategory` or `scale`.** Both are declared and never on
   the wire. `grep -n "is_category\|scale" models.py` must find nothing.
4. **Reject a variable union that is not discriminated.** `Discriminator("type")`
   must be present and `category` must have no value fields. A plain `Union` lets
   Pydantic guess and silently mis-parses.
5. **Reject a `stringPrefixSet` member.** Wire-absent; a model that accepts it
   invites a 422 nobody will diagnose.
6. **Reject any volcano statistic typed as `float` or `Decimal`.** Every number
   is a string on the wire, and one row of 5511 omits `pValue`.
7. **Reject `pointId` without the `pointID` alias.** The RAML is wrong about the
   case; the wire and the WDK plugin both use `pointID`.
8. **Reject a tabular reader that expects `{"tabular": ...}`.** The JSON body is
   a bare `string[][]`.
9. **Reject an `Accept` header that is not exactly `application/json`.** Grep
   `client.py` for `Accept` and read the literal.
10. **Reject `paging.offset` sent without `paging.numRows`.** That is a 500.
11. **Reject a compute body built at more than one call site.** The submit body
    addresses the job, so `_compute_body` must be the only builder. Grep for
    `"studyId"` in `client.py` and count.
12. **Reject a retry on `POST /computes`.** `autostart=true` starts work.
13. **Reject a new environment variable for the EDA base URL.** Grep
    `platform/config.py` for `eda`; there must be no new setting.
14. **Reject any `isinstance` chain, `getattr` with a default, `hasattr`,
    `dict.get` ladder, `# type: ignore`, `noqa`, or `import as`** in the four
    new modules.
15. **Reject a fixture that is not read by `test_fixtures_validate.py`.** The
    set-equality assertion must be present and passing.
16. **Reject a live test that passes with no credentials.** Unset them and
    confirm `SKIPPED` with the reason naming the variables.

### Report format

One block per task (A1 to A7, B1 to B5):

```
Task A2 - PASS
  evidence: uv run pytest .../test_study_models.py -v -> 7 passed
  read: integrations/eda/models.py lines 1-140
  traps checked: 1 (short_display_name is `str | None = None`, line 63),
                 2 (AliasChoices("sha1Hash","sha1_hash"), line 92),
                 3 (grep is_category|scale -> no matches)
```

A FAIL names the file, the line and the rule broken. A summary alone is not a
report.

---

## Verifier 2 - covers implementer C, plus the cross-check

### Re-run

```bash
cd apps/api
uv run ruff check src/
uv run mypy --strict src/pathfinder/
uv run pyright src/pathfinder/
uv run lint-imports
uv run pytest src/pathfinder/tests/unit/domain/eda/ -v
uv run pytest src/pathfinder/tests/unit/ -v
```

### Traps to hunt, by name

1. **Reject any import of `pathfinder.integrations` in `domain/eda.py`**, and any
   `TYPE_CHECKING` block. `uv run lint-imports` must pass, and
   `grep -n "integrations\|TYPE_CHECKING" src/pathfinder/domain/eda.py` must
   find nothing.
2. **Reject an `isinstance` chain over filter types.** The dispatch is a
   `dict[str, Callable]` keyed by the wire `type` string.
3. **Reject a `validate_filters` that returns on the first error.** The test
   `test_every_error_is_reported_not_just_the_first` must pass, and the
   implementation must accumulate.
4. **Reject a missing out-of-vocabulary check.** That check is the only guard
   against the dangerous class: 200 with count 0.
5. **Reject a missing `T00:00:00` check on a date bound.** A bare
   `YYYY-MM-DD` is a 500, and the study metadata prints bare dates, so the model
   will copy one.
6. **Reject a missing degenerate-longitude check.** `left == right` selects
   every row.
7. **Reject a missing disjoint-sets-on-one-single-valued-variable check.**
8. **Reject `find_gene_entity` that returns the first holder when there are
   two.** The bridge requires exactly one, and two is a hard failure upstream.
9. **Reject a `validate_compute_config` that omits the same-entity check or the
   ancestor check.** Both are accepted at submit and produce a `failed` job.
10. **Reject `DESeq2` being accepted anywhere.**
11. **Reject an error message that does not name the offending value and the
    valid set.** These strings become `ModelRetry` text in batch 3; a message
    the model cannot act on burns a retry.
12. **Reject dead code.** The plan text deliberately contains a wrong first
    draft of `ancestor_entity_ids`; if any of it survived (a first loop, a call
    to `entity_and_child`), that is a FAIL.

### The cross-check - the one thing only this verifier does

Implementer C's tests must not import the integration models, so nothing yet
proves the models satisfy the Protocols. Write that proof:

- [ ] Create
      `apps/api/src/pathfinder/tests/unit/integrations/eda/test_models_satisfy_domain_protocols.py`:

```python
"""The wire models are the shapes the pure predicates are declared over."""

from __future__ import annotations

import json
from pathlib import Path

from pathfinder.domain.eda import (
    EntityFacts,
    StudyFacts,
    find_gene_entity,
    validate_filters,
)
from pathfinder.integrations.eda.models import (
    EdaStringSetFilter,
    EdaStudyDetailResponse,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _study() -> EdaStudyDetailResponse:
    return EdaStudyDetailResponse.model_validate(
        json.loads((FIXTURES / "study_detail_de.json").read_text())
    )


def test_the_study_detail_is_a_study_facts() -> None:
    study: StudyFacts = _study().study
    entity: EntityFacts = study.root_entity
    assert entity.id


def test_find_gene_entity_runs_over_the_recorded_tree() -> None:
    result = find_gene_entity(_study().study)
    assert result.entity_id == "ENT_fd574cd6"


def test_validate_filters_runs_over_the_recorded_tree_and_the_wire_filter() -> None:
    study = _study().study
    errors = validate_filters(
        study,
        [
            EdaStringSetFilter(
                entity_id="ENT_8151325d",
                variable_id="VAR_081ab087",
                string_set=["normal"],
            )
        ],
    )
    assert errors == []


def test_an_out_of_vocabulary_value_on_the_recorded_tree_is_caught() -> None:
    study = _study().study
    errors = validate_filters(
        study,
        [
            EdaStringSetFilter(
                entity_id="ENT_8151325d",
                variable_id="VAR_081ab087",
                string_set=["tepid"],
            )
        ],
    )
    assert len(errors) == 1
    assert "tepid" in errors[0]
```

  This test lives under `tests/unit/integrations/`, not under
  `tests/unit/domain/`, so it never makes the domain suite depend on the
  integration layer. Run `uv run pyright` on it (mypy excludes the test
  tree by config, so pyright is the enforcing checker): the two explicit
  annotations (`study: StudyFacts`, `entity: EntityFacts`) are the actual
  assertion. A structural mismatch is a type error, not a runtime failure.

- [ ] If it does not type-check, the FAIL belongs to whichever side diverged.
      Name it: a Protocol member the model spells differently, or a model field
      the Protocol demands and the wire does not carry.

### Report format

Same as verifier 1, one block per task C1 to C3, plus one block for the
cross-check.

---

## Exit criteria

The session lead closes batch 1 when all of these are true.

1. `cd apps/api && uv run ruff check src/ && uv run mypy --strict src/pathfinder/ && uv run pyright src/pathfinder/ && uv run lint-imports && uv run pytest src/pathfinder/tests/ -v` is green, run by the lead.
2. Eleven fixture files plus `README.txt` exist under
   `apps/api/src/pathfinder/tests/unit/integrations/eda/fixtures/`, and
   `test_fixtures_validate.py` asserts the set of files equals the set of
   readers.
3. The live lane runs green with credentials and skips with a named reason
   without them.
4. `grep -rn "integrations" apps/api/src/pathfinder/domain/eda.py` finds nothing.
5. `grep -rn "type: ignore\|noqa\|isinstance\|getattr(\|hasattr(" apps/api/src/pathfinder/integrations/eda/ apps/api/src/pathfinder/domain/eda.py`
   finds nothing outside a Pydantic validator that a verifier explicitly
   approved in writing.
6. `test_models_satisfy_domain_protocols.py` exists and type-checks under
   `uv run pyright` - pyright, not mypy: `apps/api/pyproject.toml` excludes
   `src/pathfinder/tests/` from mypy, so pyright is the checker that enforces
   the Protocol proof over the test tree.
7. No new setting in `platform/config.py`; `SiteInfo.eda_base_url` is the one
   answer to where EDA lives.
8. Both verifier reports are PASS on every task, with evidence lines, and the
   lead has spot-read `models.py`, `client.py` and `domain/eda.py` against this
   document.
9. Zero debt: no dead code, no unused argument, no temporary logging, no new
   TODO. The recap leads with that sentence or the batch stays open.
10. The acceptance module for this batch passes unmodified:
    `uv run pytest -m eda_acceptance src/pathfinder/tests/acceptance/eda/test_batch1_integration.py -v --override-ini addopts=''`.
    Note: the `domain/eda.py` predicates ship in this batch but are
    acceptance-gated at batch 2's close (they live in
    `test_batch2_services.py` beside the services that call them).
