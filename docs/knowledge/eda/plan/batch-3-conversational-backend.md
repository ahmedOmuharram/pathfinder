---
type: Plan
title: "EDA batch 3: conversational backend"
description: The agent toolset that lets a researcher explore an EDA study in conversation, the three data-eda stream parts, the step bridge into the existing strategy service, the conversation_analyses attachment, and the durable compute with its worker impl - three implementers, two verifiers, one scripted end-to-end conversation.
tags: [eda, pathfinder, plan, batch, agent-tools, stream-parts, durable-tools, persistence, prompts]
generated: { by: claude-code/opus-5, at: 2026-08-28T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-28T00:00:00Z }
status: draft
---

# EDA batch 3: conversational backend

**Goal.** A researcher can say "look at the heat-shock RNA-Seq study, keep the
febrile samples, run differential expression, and put the significant genes in
my strategy", and every step of that happens in chat with real counts, a real
durable compute, and a real WDK step.

**Prerequisites.** Batches 1 and 2 closed by the session lead.

**Read first:** [overview.md](overview.md) - especially "The co-edited SSOT" and
"The pinned shared contract" - then
[batch-1-integration-foundation.md](batch-1-integration-foundation.md) and
[batch-2-services.md](batch-2-services.md) for the interfaces this batch
consumes, and
[../pathfinder-architecture-fit.md](../pathfinder-architecture-fit.md) sections
1.4, 1.5, 1.6, 2 and 4.3. The wire truths come from
[../eda-wdk-bridge.md](../eda-wdk-bridge.md),
[../computes-and-jobs.md](../computes-and-jobs.md),
[../notebook-presets.md](../notebook-presets.md),
[../genomics-and-wdk-relations.md](../genomics-and-wdk-relations.md),
[../filters.md](../filters.md) and
[../subsetting-and-tabular.md](../subsetting-and-tabular.md).

## Inherited constraints

- **TDD is non-negotiable.** Failing test first, always.
- **Pydantic maximalism.** Typed models at every boundary. No `isinstance`
  chains, no `getattr` with a default, no `hasattr`, no `dict.get` ladders over
  untyped JSON. A `match` over a discriminated union is allowed.
- **No type suppressions, no `noqa`, no `import as`, no backwards compatibility.**
- **Comments: 1 to 3 lines, ASD-STE100, near zero.** Tool docstrings are the
  exception: they are the model's instructions and they are load-bearing prose.
  Write them for a model that has never seen EDA.
- **ASCII punctuation only**, in prose, in code and in every prompt string.
- **Python 3.14.** `except ValueError, TypeError:` is valid.
- **Import-linter contracts:**
  - `pathfinder.ai.tools` may not import `pathfinder.integrations` or
    `pathfinder.persistence`. Every EDA tool goes through `pathfinder.services`.
  - `pathfinder.persistence` may not import `services`, `transport`, `ai` or
    `integrations`.
  - **Nothing EDA-shaped enters `packages/assistant-core`.** No module under
    `assistant_core/` may name a study, an entity, a variable, a filter type, a
    compute or `VEUPATHDB_GENE_ID`. `packages/assistant-core/pyproject.toml`
    names no `pathfinder` dependency and
    `packages/assistant-core/tests/unit/test_package_boundary.py` pins the
    import surface.
- **The serialization rule from batch 2 still holds.**
  `services/eda/authoring.py::serialize_spec` is the only place an analysis
  becomes a string. A `model_dump_json` of an analysis in `ai/` or `jobs/` is a
  FAIL, and batch 2's grep test will catch it.
- **Only the LLM is mocked** (`PATHFINDER_CHAT_PROVIDER=mock`). Postgres, the
  worker and the EDA fixtures are real.
- **After a backend change, rebuild and verify the container updated:**
  `docker compose --env-file .env.dev up -d --build api worker web`, then grep
  inside the container for a string you just added, then `--force-recreate` if
  the old container is still running. Chat turns run in the WORKER, so a change
  to a tool or a prompt needs the worker restarted.
- **When a Pydantic schema changes,** the OpenAPI and the TypeScript types are
  regenerated. This batch registers three stream parts, so batch 4 runs
  `yarn generate:types`. Do not run it here; note the pending regeneration in
  the recap so batch 4 picks it up.
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
  && uv run pytest src/pathfinder/tests/integration/ -v \
  && uv run lint-imports
cd packages/assistant-core && uv run pytest && uv run mypy --strict src/
```

The `assistant-core` suite is in the ladder for this batch because the boundary
test in that package is the only gate that catches an EDA name leaking into the
runtime.

## One friction with the pinned contract, resolved here

`overview.md` puts `run_eda_compute` in
`ai/tools/standalone/` beside the other six EDA tools, and all seven are tools
the Lead calls. But `ai/tools/durable.py::durable_tool` is typed to
`RunContext[AgentDeps]` and reads `deps.conversation_id` and `deps.user_id`,
while the Lead's tools take `RunContext[LeadDeps]` and `LeadDeps` is a
dataclass with `state` and `runtime` instead.

**The resolution, and it is a generalization rather than a workaround.**
`durable_tool` needs an identity, not the whole of `AgentDeps`. Task C1 below
narrows its requirement to a `Protocol` with two members and gives `LeadDeps`
those two members as properties over the state it already holds. Nothing is
renamed and no second decorator appears. The alternative - putting
`run_eda_compute` on a sub-agent toolset - was rejected because it would put the
EDA loop behind a phase dispatch the researcher never asked for, and the Lead
would lose the compute result it must narrate.

---

## Implementer A: the agent toolset and the stream parts

### Files

| Action | Path |
|---|---|
| Create | `packages/shared-py/src/shared_py/stream_parts/eda.py` |
| Create | `apps/api/src/pathfinder/ai/eda_stream_parts.py` |
| Modify | `apps/api/src/pathfinder/assistants/pathfinder_spec.py` (compose the two registration hooks) |
| Create | `apps/api/src/pathfinder/ai/tools/standalone/_eda_models.py` |
| Create | `apps/api/src/pathfinder/ai/tools/standalone/_eda_stream_parts.py` |
| Create | `apps/api/src/pathfinder/ai/tools/standalone/eda_catalog.py` |
| Create | `apps/api/src/pathfinder/ai/tools/standalone/eda_analysis.py` |
| Create | `apps/api/src/pathfinder/ai/tools/toolsets/eda.py` |
| Modify | `apps/api/src/pathfinder/ai/lead/lead_agent.py` (add the toolset) |
| Modify | `apps/api/src/pathfinder/ai/lead/_lead_instructions.py` (add the EDA section) |
| Create | `apps/api/src/pathfinder/tests/unit/stream_parts/test_eda_parts.py` |
| Create | `apps/api/src/pathfinder/tests/unit/ai/tools/eda/__init__.py` |
| Create | `apps/api/src/pathfinder/tests/unit/ai/tools/eda/test_eda_toolset.py` |
| Create | `apps/api/src/pathfinder/tests/unit/ai/tools/eda/test_set_eda_filters_sheet.py` |
| Create | `apps/api/src/pathfinder/tests/unit/ai/lead/test_eda_instructions.py` |
| Create | `apps/api/src/pathfinder/tests/integration/eda/test_eda_tools.py` |

### Interfaces

**Consumes** (batches 1 and 2):

```python
from pathfinder.services.eda.catalog import (
    StudyCard, UnknownEdaDatasetError,
    search_studies, get_study_detail_for_dataset, resolve_dataset,
)
from pathfinder.services.eda.authoring import (
    SubsetPreview, SubsetRejected,
    apply_filters, open_analysis, preview_subset, validate_subset,
)
from pathfinder.integrations.eda.models import (  # types only, via services
    EdaAnalysisDetail, EdaDistributionResponse, EdaFilter, EdaStudyDetail,
)
```

**The import-linter problem, and its answer.** `pathfinder.ai.tools` may not
import `pathfinder.integrations`, and the tools need the filter models as
argument types. Do NOT re-declare them. `pathfinder.services.eda` re-exports the
shapes a tool signature needs, in one place:

```python
# services/eda/__init__.py  (implementer A of this batch owns this addition)
from pathfinder.integrations.eda.models import (
    EdaAnalysisDetail,
    EdaDistributionResponse,
    EdaEntity,
    EdaFilter,
    EdaStudyDetail,
    EdaVariable,
)

__all__ = [
    "EdaAnalysisDetail",
    "EdaDistributionResponse",
    "EdaEntity",
    "EdaFilter",
    "EdaStudyDetail",
    "EdaVariable",
]
```

This is a re-export, which CLAUDE.md forbids as a backwards-compatibility
device. It is not one here: it is the service layer publishing the types its own
signatures use, exactly as `services/catalog/__init__.py` publishes
`SearchMatch` and `SearchInspection` today. Verifier 1 checks that the list holds
only types that appear in a `services/eda` public signature, and nothing else.

**Produces:**

```python
# shared_py/stream_parts/eda.py
class EdaAnalysisState(CamelModel)
class EdaSubsetPreviewPart(CamelModel)
class EdaEntityCount(CamelModel)
class EdaDistributionSeries(CamelModel)
class EdaVizPart(CamelModel)
class EdaVolcanoPoint(CamelModel)

# ai/eda_stream_parts.py
def register_eda_stream_parts(registry: StreamPartRegistry) -> None

# ai/tools/standalone/_eda_stream_parts.py
def eda_analysis_state_chunk(...) -> DataChunk
def eda_subset_preview_chunk(...) -> DataChunk
def eda_viz_chunk(...) -> DataChunk

# ai/tools/standalone/eda_catalog.py
async def search_eda_studies(ctx, query: str, limit: int = 5) -> ...
async def describe_eda_study(ctx, dataset_id: str, entity_id: str | None = None) -> ...

# ai/tools/standalone/eda_analysis.py
async def open_eda_analysis(ctx, dataset_id: str, purpose: str) -> ...
async def set_eda_filters(ctx, *, dataset_id: str,
                          filters: list[EdaFilter] | None = None) -> ...
async def preview_eda_subset(ctx, *, entity_id: str,
                             distribution_variable_id: str | None = None) -> ...

# ai/tools/toolsets/eda.py
def build_toolset() -> AbstractToolset[LeadDeps]
```

---

### Task A1 - the three stream-part payload models

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/stream_parts/test_eda_parts.py`:

```python
"""The three data-eda parts, their payloads, and their registration."""

from __future__ import annotations

from assistant_core.conversation.stream_parts.core_parts import (
    register_core_stream_parts,
)
from assistant_core.conversation.stream_parts.registry import StreamPartRegistry
from shared_py.stream_parts.eda import (
    EdaAnalysisState,
    EdaDistributionSeries,
    EdaEntityCount,
    EdaSubsetPreviewPart,
    EdaVizPart,
    EdaVolcanoPoint,
)

from pathfinder.ai.eda_stream_parts import register_eda_stream_parts
from pathfinder.ai.strategy_stream_parts import register_strategy_stream_parts

_KINDS = {
    "data-eda.analysis-state",
    "data-eda.subset-preview",
    "data-eda.viz",
}


def test_the_three_kinds_register() -> None:
    registry = StreamPartRegistry()
    register_eda_stream_parts(registry)
    assert registry.kinds() == _KINDS


def test_the_dotted_kinds_map_to_python_identifiers() -> None:
    registry = StreamPartRegistry()
    register_eda_stream_parts(registry)
    names = {entry.schema_name for entry in registry.entries()}
    assert names == {"eda_analysis_state", "eda_subset_preview", "eda_viz"}


def test_the_eda_kinds_do_not_collide_with_the_runtime_or_the_strategy_parts() -> None:
    registry = StreamPartRegistry()
    register_core_stream_parts(registry)
    register_strategy_stream_parts(registry)
    register_eda_stream_parts(registry)
    assert _KINDS <= registry.kinds()


def test_the_schema_index_exposes_every_eda_payload() -> None:
    registry = StreamPartRegistry()
    register_eda_stream_parts(registry)
    fields = set(registry.schema_index_model().model_fields)
    assert {"eda_analysis_state", "eda_subset_preview", "eda_viz"} <= fields


def test_the_analysis_state_carries_the_reference_and_a_summary() -> None:
    part = EdaAnalysisState(
        site_id="plasmodb",
        dataset_id="DS_53f554ec6a",
        study_id="STUDY_53f554ec6a",
        analysis_id="t4fszEJ",
        study_display_name="Rodent malaria phenotypes",
        display_name="berghei subset",
        num_filters=1,
        num_computations=0,
        filter_summaries=["Species is one of P. berghei"],
        can_export_rows=True,
    )
    dumped = part.model_dump(by_alias=True)
    assert dumped["datasetId"] == "DS_53f554ec6a"
    assert dumped["analysisId"] == "t4fszEJ"
    assert dumped["numFilters"] == 1


def test_the_subset_preview_carries_entity_counts_and_one_distribution() -> None:
    part = EdaSubsetPreviewPart(
        dataset_id="DS_53f554ec6a",
        analysis_id="t4fszEJ",
        entity_counts=[
            EdaEntityCount(
                entity_id="GENE_PHENOTYPE_DATA_ENTITY",
                entity_display_name="Gene phenotype",
                count=4011,
                unfiltered_count=4279,
            )
        ],
        distribution=EdaDistributionSeries(
            variable_id="VAR_035294d0",
            variable_display_name="Species",
            labels=["P. berghei", "P. falciparum", "P. yoelii"],
            values=[4011.0, 4130.0, 268.0],
            subset_size=4279,
            num_var_values=8409,
            num_missing_cases=0,
            is_multi_valued=True,
        ),
    )
    dumped = part.model_dump(by_alias=True)
    assert dumped["entityCounts"][0]["unfilteredCount"] == 4279
    assert dumped["distribution"]["isMultiValued"] is True


def test_a_multi_valued_distribution_says_so_because_the_values_do_not_partition(
) -> None:
    """4011 + 4130 + 268 = 8409 over 4279 rows."""
    series = EdaDistributionSeries(
        variable_id="V",
        variable_display_name="Species",
        labels=["a", "b"],
        values=[4011.0, 4130.0],
        subset_size=4279,
        num_var_values=8409,
        num_missing_cases=0,
        is_multi_valued=True,
    )
    assert sum(series.values) > series.subset_size
    assert series.is_multi_valued is True


def test_the_viz_part_carries_the_chart_kind_and_its_series() -> None:
    part = EdaVizPart(
        dataset_id="DS_e973eadd57",
        analysis_id="t4fszEJ",
        chart="volcano",
        effect_size_label="log2(Fold Change)",
        effect_size_threshold=1.0,
        significance_threshold=0.05,
        effect_direction="upAndDown",
        total_points=5511,
        retained_points=1543,
        points=[
            EdaVolcanoPoint(
                point_id="PF3D7_0100200",
                effect_size=3.94437533216012,
                p_value=1.95781599815607e-05,
                retained=True,
            )
        ],
    )
    dumped = part.model_dump(by_alias=True)
    assert dumped["chart"] == "volcano"
    assert dumped["retainedPoints"] == 1543
    assert dumped["points"][0]["pointId"] == "PF3D7_0100200"


def test_a_viz_point_may_have_no_p_value() -> None:
    point = EdaVolcanoPoint(
        point_id="PF3D7_MIT04200", effect_size=-1.49447459261845, retained=False
    )
    assert point.p_value is None


def test_the_labels_and_values_of_a_series_are_the_same_length() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        EdaDistributionSeries(
            variable_id="V",
            variable_display_name="V",
            labels=["a", "b"],
            values=[1.0],
            subset_size=1,
            num_var_values=1,
            num_missing_cases=0,
            is_multi_valued=False,
        )
```

- [ ] **Run it.** Expect
      `ModuleNotFoundError: No module named 'shared_py.stream_parts.eda'`.

- [ ] **Implementation.** Create
      `packages/shared-py/src/shared_py/stream_parts/eda.py`:

```python
"""Typed payloads for the data-eda parts the chat and the tab both render."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from shared_py.pydantic_base import CamelModel


class EdaAnalysisState(CamelModel):
    """The open analysis, as both surfaces re-render it after every mutation.

    The part is a full snapshot, like the strategy graph part: the tab
    hydrates its store from it with no follow-up fetch. ``revision`` is a
    per-binding mutation counter kept on the ``conversation_analyses`` row
    and incremented by every authoring mutation; ``None`` means unknown and
    the store's reconcile rule then takes the last write. ``filters`` entries
    are the wire filter objects, kept as JSON here because ``shared_py``
    cannot import the integrations union; the frontend parses each entry with
    the generated ``edaFilter`` zod schema at hydration and drops what fails.
    """

    site_id: str
    dataset_id: str
    study_id: str
    analysis_id: str
    revision: int | None = None
    study_display_name: str = ""
    display_name: str = ""
    num_filters: int = Field(default=0, ge=0)
    num_computations: int = Field(default=0, ge=0)
    filters: list[JSONObject] = Field(default_factory=list)
    filter_summaries: list[str] = Field(default_factory=list)
    entity_counts: list[EdaEntityCount] = Field(default_factory=list)
    can_export_rows: bool = False


class EdaEntityCount(CamelModel):
    """One entity's subset size against its unfiltered size."""

    entity_id: str
    entity_display_name: str = ""
    count: int = Field(ge=0)
    unfiltered_count: int = Field(ge=0)


class EdaDistributionSeries(CamelModel):
    """One variable's histogram under the current subset.

    ``num_var_values`` can exceed ``subset_size`` on a multi-valued variable,
    so a percentage needs its denominator named.
    """

    variable_id: str
    variable_display_name: str = ""
    labels: list[str] = Field(default_factory=list)
    values: list[float] = Field(default_factory=list)
    subset_size: int = Field(default=0, ge=0)
    num_var_values: int = Field(default=0, ge=0)
    num_missing_cases: int = Field(default=0, ge=0)
    is_multi_valued: bool = False

    @model_validator(mode="after")
    def _one_value_per_label(self) -> EdaDistributionSeries:
        if len(self.labels) != len(self.values):
            msg = "labels and values must be the same length"
            raise ValueError(msg)
        return self


class EdaSubsetPreviewPart(CamelModel):
    """What the current filters select, with one variable's shape."""

    dataset_id: str
    analysis_id: str
    entity_counts: list[EdaEntityCount] = Field(default_factory=list)
    distribution: EdaDistributionSeries | None = None


class EdaVolcanoPoint(CamelModel):
    """One gene on the volcano. A point may carry no p-value."""

    point_id: str
    effect_size: float
    p_value: float | None = None
    adjusted_p_value: float | None = None
    retained: bool = False


class EdaVizPart(CamelModel):
    """Server-computed plot data, sized for one chart."""

    dataset_id: str
    analysis_id: str
    chart: Literal["volcano", "histogram", "boxplot", "bar", "scatter"]
    effect_size_label: str = ""
    effect_size_threshold: float | None = None
    significance_threshold: float | None = None
    effect_direction: Literal["upOnly", "downOnly", "upAndDown"] | None = None
    total_points: int = Field(default=0, ge=0)
    retained_points: int = Field(default=0, ge=0)
    points: list[EdaVolcanoPoint] = Field(default_factory=list)
```

- [ ] Create `apps/api/src/pathfinder/ai/eda_stream_parts.py`:

```python
"""Stream parts of the EDA surface: the analysis, the subset, the plot."""

from assistant_core.conversation.stream_parts.registry import StreamPartRegistry
from shared_py.stream_parts.eda import (
    EdaAnalysisState,
    EdaSubsetPreviewPart,
    EdaVizPart,
)


def register_eda_stream_parts(registry: StreamPartRegistry) -> None:
    registry.register("data-eda.analysis-state", EdaAnalysisState)
    registry.register("data-eda.subset-preview", EdaSubsetPreviewPart)
    registry.register("data-eda.viz", EdaVizPart)
```

- [ ] **Compose the two hooks.** `assistants/pathfinder_spec.py` currently
      passes `register_stream_parts=register_strategy_stream_parts`. The spec
      field takes one callable, so add a private composer in that module:

```python
def _register_product_stream_parts(registry: StreamPartRegistry) -> None:
    """Every part this product emits: the strategy surface and the EDA surface."""
    register_strategy_stream_parts(registry)
    register_eda_stream_parts(registry)
```

  and pass `register_stream_parts=_register_product_stream_parts`. Update
  `apps/api/src/pathfinder/tests/unit/assistants/test_pathfinder_spec.py` in the
  same task: its `test_it_registers_the_strategy_stream_parts` must now also
  assert the three EDA kinds are present, and the assertion must be on the set
  of kinds, not on the hook's identity.

- [ ] **Gates**, with
      `src/pathfinder/tests/unit/stream_parts/ src/pathfinder/tests/unit/assistants/`
      and also:

  ```bash
  cd packages/shared-py && uv run ruff check src/ && uv run mypy --strict src/
  ```

**Trap named:** the payload models live in `shared_py`, not in `assistant_core`
and not in `pathfinder`. That is where every other data-part payload lives
(`shared_py/stream_parts/{gene_set,graph,strategy,enrichment}.py`) and it is what
feeds the generated TypeScript in batch 4. A payload model in `pathfinder/`
would not reach the generated types.

---

### Task A2 - the chunk builders

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/integration/eda/test_eda_tools.py` and
      start it with the chunk builders, because the tools' tests below assert on
      the chunks they emit:

```python
"""The EDA tools, the chunks they emit, and the retries they raise."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from pathfinder.ai.tools.standalone._eda_stream_parts import (
    eda_analysis_state_chunk,
    eda_subset_preview_chunk,
)
from pathfinder.integrations.eda.models import (
    EdaAnalysisDetail,
    EdaDistributionResponse,
    EdaStringSetFilter,
)
from pathfinder.services.eda.authoring import SubsetPreview

FIXTURES = (
    Path(__file__).resolve().parents[2]
    / "unit"
    / "integrations"
    / "eda"
    / "fixtures"
)

_DATASET = "DS_53f554ec6a"
_STUDY = "STUDY_53f554ec6a"
_ENTITY = "GENE_PHENOTYPE_DATA_ENTITY"


def _fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text())


def _detail() -> EdaAnalysisDetail:
    return EdaAnalysisDetail.model_validate(
        {
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
        }
    )


def test_the_analysis_state_chunk_names_the_part_kind() -> None:
    chunk = eda_analysis_state_chunk(
        site_id="plasmodb",
        dataset_id=_DATASET,
        study_id=_STUDY,
        study_display_name="Rodent malaria phenotypes",
        analysis=_detail(),
        filter_summaries=["Species is one of P. berghei"],
        can_export_rows=True,
    )
    assert chunk.type == "data-eda.analysis-state"
    assert chunk.data["analysisId"] == "t4fszEJ"
    assert chunk.data["numFilters"] == 1
    assert chunk.data["filterSummaries"] == ["Species is one of P. berghei"]


def test_the_subset_preview_chunk_converts_a_histogram_to_a_series() -> None:
    preview = SubsetPreview(
        entity_id=_ENTITY,
        entity_display_name="Gene phenotype",
        count=4011,
        unfiltered_count=4279,
        distribution=EdaDistributionResponse.model_validate(
            _fixture("distribution_categorical.json")
        ),
    )
    chunk = eda_subset_preview_chunk(
        dataset_id=_DATASET,
        analysis_id="t4fszEJ",
        preview=preview,
        variable_id="VAR_035294d0",
        variable_display_name="Species",
        is_multi_valued=True,
    )
    assert chunk.type == "data-eda.subset-preview"
    counts = chunk.data["entityCounts"]
    assert counts[0]["count"] == 4011
    assert counts[0]["unfilteredCount"] == 4279
    series = chunk.data["distribution"]
    assert len(series["labels"]) == len(series["values"])
    assert series["isMultiValued"] is True
    assert series["numVarValues"] == 8409


def test_the_subset_preview_chunk_omits_the_series_when_there_is_none() -> None:
    preview = SubsetPreview(
        entity_id=_ENTITY,
        entity_display_name="Gene phenotype",
        count=4011,
        unfiltered_count=4279,
        distribution=None,
    )
    chunk = eda_subset_preview_chunk(
        dataset_id=_DATASET,
        analysis_id="t4fszEJ",
        preview=preview,
        variable_id=None,
        variable_display_name="",
        is_multi_valued=False,
    )
    assert chunk.data["distribution"] is None
```

- [ ] **Run it.** Expect `ModuleNotFoundError`.

- [ ] **Implementation.** Create
      `apps/api/src/pathfinder/ai/tools/standalone/_eda_stream_parts.py`,
      modelled on the existing `_stream_parts.py`:

```python
"""The chunks the EDA tools attach to their return metadata."""

from __future__ import annotations

from pydantic_ai.ui.vercel_ai.response_types import DataChunk
from shared_py.stream_parts.eda import (
    EdaAnalysisState,
    EdaDistributionSeries,
    EdaEntityCount,
    EdaSubsetPreviewPart,
    EdaVizPart,
    EdaVolcanoPoint,
)

from pathfinder.services.eda import (
    EdaAnalysisDetail,
    EdaDistributionResponse,
)
from pathfinder.services.eda.authoring import SubsetPreview
from pathfinder.services.eda.compute import RetainedSummary

_MAX_VIZ_POINTS = 4000


def eda_analysis_state_chunk(
    *,
    site_id: str,
    dataset_id: str,
    study_id: str,
    study_display_name: str,
    analysis: EdaAnalysisDetail,
    filter_summaries: list[str],
    can_export_rows: bool,
) -> DataChunk:
    """The analysis as both surfaces re-render it."""
    payload = EdaAnalysisState(
        site_id=site_id,
        dataset_id=dataset_id,
        study_id=study_id,
        analysis_id=analysis.analysis_id,
        study_display_name=study_display_name,
        display_name=analysis.display_name,
        num_filters=analysis.num_filters,
        num_computations=analysis.num_computations,
        filter_summaries=filter_summaries,
        can_export_rows=can_export_rows,
    )
    return DataChunk(
        type="data-eda.analysis-state",
        data=payload.model_dump(by_alias=True, mode="json"),
    )


def eda_subset_preview_chunk(
    *,
    dataset_id: str,
    analysis_id: str,
    preview: SubsetPreview,
    variable_id: str | None,
    variable_display_name: str,
    is_multi_valued: bool,
) -> DataChunk:
    """The subset's size and one variable's shape under it."""
    payload = EdaSubsetPreviewPart(
        dataset_id=dataset_id,
        analysis_id=analysis_id,
        entity_counts=[
            EdaEntityCount(
                entity_id=preview.entity_id,
                display_name=preview.entity_display_name,
                count=preview.count,
                unfiltered_count=preview.unfiltered_count,
            )
        ],
        distribution=_series(
            preview.distribution,
            variable_id=variable_id,
            variable_display_name=variable_display_name,
            is_multi_valued=is_multi_valued,
        ),
    )
    return DataChunk(
        type="data-eda.subset-preview",
        data=payload.model_dump(by_alias=True, mode="json"),
    )


def _series(
    distribution: EdaDistributionResponse | None,
    *,
    variable_id: str | None,
    variable_display_name: str,
    is_multi_valued: bool,
) -> EdaDistributionSeries | None:
    if distribution is None or variable_id is None:
        return None
    statistics = distribution.statistics
    return EdaDistributionSeries(
        variable_id=variable_id,
        variable_display_name=variable_display_name,
        labels=[bin_.bin_label for bin_ in distribution.histogram],
        values=[bin_.value for bin_ in distribution.histogram],
        subset_size=statistics.subset_size,
        num_var_values=statistics.num_var_values,
        num_missing_cases=statistics.num_missing_cases,
        is_multi_valued=is_multi_valued,
    )


def eda_viz_chunk(
    *,
    dataset_id: str,
    analysis_id: str,
    effect_size_label: str,
    effect_size_threshold: float,
    significance_threshold: float,
    effect_direction: str,
    summary: RetainedSummary,
    points: list[EdaVolcanoPoint],
) -> DataChunk:
    """The volcano, capped so one message does not carry every gene."""
    payload = EdaVizPart(
        dataset_id=dataset_id,
        analysis_id=analysis_id,
        chart="volcano",
        effect_size_label=effect_size_label,
        effect_size_threshold=effect_size_threshold,
        significance_threshold=significance_threshold,
        effect_direction=effect_direction,
        total_points=summary.total_rows,
        retained_points=summary.retained,
        points=points[:_MAX_VIZ_POINTS],
    )
    return DataChunk(
        type="data-eda.viz",
        data=payload.model_dump(by_alias=True, mode="json"),
    )
```

  `effect_direction` is a `str` in the signature and a `Literal` on the model,
  so a wrong value is a `ValidationError` at the boundary rather than a silently
  wrong chart. Do not widen the model's `Literal`.

  `_MAX_VIZ_POINTS` is 4000, above the 1543 retained in the measured run and
  below the 5511 total, so the cap is real and the retained set always survives
  it. Sort `points` so every retained point comes first before slicing, or the
  cap can drop retained genes. Add the test for that ordering.

- [ ] **Gates**, with
      `src/pathfinder/tests/integration/eda/test_eda_tools.py`.

---

### Task A3 - `search_eda_studies` and `describe_eda_study`

- [ ] **Failing test.** Append to
      `apps/api/src/pathfinder/tests/integration/eda/test_eda_tools.py`:

```python
async def test_search_eda_studies_returns_cards_the_model_can_act_on(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    from pathfinder.ai.tools.standalone import eda_catalog
    from pathfinder.services.eda.catalog import StudyCard

    async def cards(_site: str, _query: str, limit: int = 5) -> list[StudyCard]:
        return [
            StudyCard(
                dataset_id=_DATASET,
                study_id=_STUDY,
                display_name="Rodent malaria phenotypes",
                short_display_name="Rod Mal Phenotype",
                description="Phenotypes of genetically modified rodent malaria",
                source_type="curated",
                relevance=0.71,
                can_subset=True,
                can_export_rows=True,
            )
        ][:limit]

    monkeypatch.setattr(eda_catalog, "search_studies", cards)
    result = await eda_catalog.search_eda_studies(lead_ctx, query="rodent malaria")
    assert result.studies
    first = result.studies[0]
    assert first.dataset_id == _DATASET
    assert first.study_id == _STUDY
    assert first.can_export_rows is True
    assert "Phenotypes" in first.description


async def test_search_eda_studies_says_so_when_nothing_matches(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    from pathfinder.ai.tools.standalone import eda_catalog

    async def none(_site: str, _query: str, limit: int = 5) -> list[object]:
        return []

    monkeypatch.setattr(eda_catalog, "search_studies", none)
    result = await eda_catalog.search_eda_studies(lead_ctx, query="nothing here")
    assert result.studies == []
    assert "no EDA study" in result.guidance


async def test_describe_eda_study_reports_the_entity_tree_and_the_gene_entity(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    from pathfinder.ai.tools.standalone import eda_catalog

    monkeypatch.setattr(eda_catalog, "get_study_detail_for_dataset", _phenotype_study)
    result = await eda_catalog.describe_eda_study(lead_ctx, dataset_id=_DATASET)
    assert result.study_id == _STUDY
    assert result.gene_entity_id == _ENTITY
    entities = {e.entity_id: e for e in result.entities}
    assert _ENTITY in entities
    assert entities[_ENTITY].record_count is None
    assert entities[_ENTITY].variable_count > 0


async def test_describe_eda_study_summarises_a_vocabulary_without_dumping_it(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    """A tool payload must fit a context window; 4000 terms must not travel."""
    from pathfinder.ai.tools.standalone import eda_catalog

    monkeypatch.setattr(eda_catalog, "get_study_detail_for_dataset", _phenotype_study)
    result = await eda_catalog.describe_eda_study(
        lead_ctx, dataset_id=_DATASET, entity_id=_ENTITY
    )
    species = next(
        v for v in result.variables if v.variable_id == "VAR_035294d0"
    )
    assert species.vocabulary_total == 3
    assert species.vocabulary == ["P. berghei", "P. falciparum", "P. yoelii"]
    assert species.is_multi_valued is True
    assert species.filter_type == "stringSet"


async def test_describe_eda_study_truncates_a_long_vocabulary_and_says_so(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    from pathfinder.ai.tools.standalone import eda_catalog

    monkeypatch.setattr(
        eda_catalog, "get_study_detail_for_dataset", _wide_vocabulary_study
    )
    result = await eda_catalog.describe_eda_study(
        lead_ctx, dataset_id=_DATASET, entity_id="E"
    )
    wide = result.variables[0]
    assert wide.vocabulary_total == 500
    assert len(wide.vocabulary) == 40
    assert wide.vocabulary_note is not None
    assert "500" in wide.vocabulary_note


async def test_describe_eda_study_names_a_multifilter_category_and_its_children(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    from pathfinder.ai.tools.standalone import eda_catalog

    monkeypatch.setattr(
        eda_catalog, "get_study_detail_for_dataset", _multifilter_study
    )
    result = await eda_catalog.describe_eda_study(
        lead_ctx, dataset_id=_DATASET, entity_id="EUPATH_0000096"
    )
    category = next(v for v in result.variables if v.filter_type == "multiFilter")
    assert category.sub_filter_variable_ids
    assert category.vocabulary == []


async def test_describe_eda_study_refuses_a_study_with_no_gene_id_variable(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    from pathfinder.ai.tools.standalone import eda_catalog

    monkeypatch.setattr(eda_catalog, "get_study_detail_for_dataset", _no_gene_study)
    result = await eda_catalog.describe_eda_study(lead_ctx, dataset_id=_DATASET)
    assert result.gene_entity_id is None
    assert result.gene_entity_problem is not None
    assert "VEUPATHDB_GENE_ID" in result.gene_entity_problem


async def test_an_unknown_dataset_id_raises_a_model_retry_naming_the_tool(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    from pydantic_ai.exceptions import ModelRetry

    from pathfinder.ai.tools.standalone import eda_catalog
    from pathfinder.services.eda.catalog import UnknownEdaDatasetError

    async def raises(_site: str, _dataset_id: str) -> object:
        raise UnknownEdaDatasetError("DS_nope", ["DS_a", "DS_b"])

    monkeypatch.setattr(eda_catalog, "get_study_detail_for_dataset", raises)
    with pytest.raises(ModelRetry) as excinfo:
        await eda_catalog.describe_eda_study(lead_ctx, dataset_id="DS_nope")
    assert "DS_nope" in str(excinfo.value)
    assert "search_eda_studies" in str(excinfo.value)
```

  The `lead_ctx` fixture and the four study builders (`_phenotype_study`,
  `_wide_vocabulary_study`, `_multifilter_study`, `_no_gene_study`) go in a
  module-level block at the top of the file. `lead_ctx` is a
  `RunContext[LeadDeps]`; build it the way the existing tool tests do - read
  `apps/api/src/pathfinder/tests/unit/ai/tools/` for a `RunContext` construction
  already in the suite and copy it, so the deps carry a `site_id`, a
  `conversation_id`, a `user_id` and the `state`.

- [ ] **Implementation.** Create
      `apps/api/src/pathfinder/ai/tools/standalone/_eda_models.py` with the tool
      return shapes:

```python
"""Return shapes of the EDA tools. Every field is something the model acts on."""

from __future__ import annotations

from typing import Literal

from assistant_core.platform.pydantic_base import CamelModel
from pydantic import Field


class EdaStudyCardOut(CamelModel):
    dataset_id: str
    study_id: str
    display_name: str
    short_display_name: str = ""
    description: str = ""
    source_type: str = ""
    relevance: float = 0.0
    can_subset: bool = False
    can_export_rows: bool = False


class EdaStudySearchResult(CamelModel):
    studies: list[EdaStudyCardOut] = Field(default_factory=list)
    guidance: str = ""


EdaFilterType = Literal[
    "stringSet",
    "numberSet",
    "dateSet",
    "numberRange",
    "dateRange",
    "longitudeRange",
    "multiFilter",
]


class EdaVariableOut(CamelModel):
    """One filterable variable, with the exact filter type it takes."""

    entity_id: str
    variable_id: str
    display_name: str
    variable_type: str
    filter_type: EdaFilterType | None = None
    data_shape: str | None = None
    is_multi_valued: bool = False
    vocabulary: list[str] = Field(default_factory=list)
    vocabulary_total: int = 0
    vocabulary_note: str | None = None
    range_min: float | None = None
    range_max: float | None = None
    date_min: str | None = None
    date_max: str | None = None
    sub_filter_variable_ids: list[str] = Field(default_factory=list)


class EdaEntityOut(CamelModel):
    entity_id: str
    display_name: str
    display_name_plural: str = ""
    parent_entity_id: str | None = None
    variable_count: int = 0
    record_count: int | None = None
    has_gene_id: bool = False


class EdaStudyDescription(CamelModel):
    dataset_id: str
    study_id: str
    display_name: str = ""
    entities: list[EdaEntityOut] = Field(default_factory=list)
    variables: list[EdaVariableOut] = Field(default_factory=list)
    gene_entity_id: str | None = None
    gene_entity_problem: str | None = None
    guidance: str = ""
```

- [ ] Create `apps/api/src/pathfinder/ai/tools/standalone/eda_catalog.py`. Both
      tools take `RunContext[LeadDeps]`.

```python
"""Agent tools that find an EDA study and read its shape."""

from __future__ import annotations

from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.ai.tools.standalone._eda_models import (
    EdaStudyCardOut,
    EdaStudyDescription,
    EdaStudySearchResult,
)
from pathfinder.services.eda.catalog import (
    UnknownEdaDatasetError,
    get_study_detail_for_dataset,
    search_studies,
)

_VOCABULARY_SHOWN = 40


async def search_eda_studies(
    ctx: RunContext[LeadDeps],
    query: str,
    limit: int = 5,
) -> EdaStudySearchResult:
    """Find an EDA study by what it measures.

    EDA studies are the sample-level datasets behind VEuPathDB's expression,
    phenotype and antibody-array searches. Use this when the user names a
    dataset, an experiment, a condition or a comparison - "the heat shock
    RNA-Seq data", "rodent malaria phenotypes", "febrile against normal" -
    rather than a gene attribute.

    Each result carries a ``datasetId`` (a ``DS_`` or ``EDAUD_`` id) and a
    ``studyId``. Every later EDA tool takes the ``datasetId``; never build one
    from the other. ``canSubset`` false means this account cannot count that
    study, and ``canExportRows`` false means it cannot export its rows into a
    step, so say so instead of trying.

    Args:
        ctx: Agent run context.
        query: What the study should measure, in the user's own words.
        limit: Maximum studies to return.
    """
    cards = await search_studies(ctx.deps.runtime.site_id, query, limit=limit)
    if not cards:
        return EdaStudySearchResult(
            guidance=(
                f"No EDA study on this site matches {query!r}. EDA covers "
                f"sample-level expression, phenotype and antibody-array "
                f"datasets only. If the question is about gene attributes, use "
                f"search_for_searches instead."
            ),
        )
    return EdaStudySearchResult(
        studies=[
            EdaStudyCardOut(
                dataset_id=c.dataset_id,
                study_id=c.study_id,
                display_name=c.display_name,
                short_display_name=c.short_display_name,
                description=c.description,
                source_type=c.source_type,
                relevance=c.relevance,
                can_subset=c.can_subset,
                can_export_rows=c.can_export_rows,
            )
            for c in cards
        ],
        guidance=(
            "Call describe_eda_study on the datasetId you want before "
            "opening an analysis."
        ),
    )
```

  `describe_eda_study` walks the tree with `pathfinder.domain.eda.walk_entities`
  and `find_gene_entity`, and builds one `EdaVariableOut` per filterable
  variable on the requested entity - or per entity summary only when no
  `entity_id` is given, so a 5000-variable study does not arrive whole.

  The rules the builder must encode, each one a live measurement:

  | rule | why |
  |---|---|
  | with no `entity_id`, return entity summaries and NO variables | `HMPWgs-1`'s `OBI_0002623` carries 4931 variables |
  | `filter_type` comes from the variable's `type`, per the seven-type table | `longitude` is not `number`; `category` has no values |
  | a `category` whose `displayType` is not `multifilter` gets `filter_type = None` | it cannot be filtered on and cannot be an output variable |
  | a `multifilter` category lists its children in `sub_filter_variable_ids` and carries an empty `vocabulary` | the sub-filters name the children, not the parent |
  | a vocabulary longer than 40 terms is truncated and `vocabulary_note` states the total | a tool payload must fit a context window |
  | `is_multi_valued` is always reported | summing per-value counts on a multi-valued variable is off by nearly a factor of two |
  | a `date` variable's bounds are reported with `T00:00:00` already appended | the metadata prints bare dates and a bare bound is a 500 |
  | `record_count` is `None` | the tree carries no counts; `preview_eda_subset` is what produces one |
  | `hide_from` containing `everywhere` still lists the variable | `hideFrom` is UI advice, not access control, and the variable is still filterable |

  And the guidance string, written for the model:

```python
    guidance = (
        "Filter this study with set_eda_filters. Copy an entityId and a "
        "variableId from the lists above; a variableId is only valid on the "
        "entity that declares it. Pick the filter type from the variable's "
        "own type, not from what the value looks like. Check every string "
        "value against the variable's vocabulary yourself: an invented value "
        "returns a count of zero with no error."
    )
```

  The `UnknownEdaDatasetError` handler raises `ModelRetry` with the error's own
  `guidance` plus "Call search_eda_studies to find a real datasetId.". A
  `ModelRetry` is the right shape here because the model can fix the call.

- [ ] **Gates**, with
      `src/pathfinder/tests/integration/eda/test_eda_tools.py`.

---

### Task A4 - `open_eda_analysis`

- [ ] **Failing test.** Append to `test_eda_tools.py`:

```python
async def test_open_eda_analysis_creates_the_analysis_and_binds_the_conversation(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    from pathfinder.ai.tools.standalone import eda_analysis

    bound: list[tuple[str, str, str]] = []

    async def open_it(_site: str, *, dataset_id: str, display_name: str) -> str:
        assert display_name
        return "t4fszEJ"

    async def bind(**kwargs: object) -> None:
        bound.append(
            (
                str(kwargs["dataset_id"]),
                str(kwargs["analysis_id"]),
                str(kwargs["site_id"]),
            )
        )

    monkeypatch.setattr(eda_analysis, "open_analysis", open_it)
    monkeypatch.setattr(eda_analysis, "bind_conversation_analysis", bind)
    monkeypatch.setattr(eda_analysis, "read_analysis", _read_detail)
    monkeypatch.setattr(
        eda_analysis, "get_study_detail_for_dataset", _phenotype_study
    )

    returned = await eda_analysis.open_eda_analysis(
        lead_ctx, dataset_id=_DATASET, purpose="keep the P. berghei rows"
    )
    assert returned.return_value.analysis_id == "t4fszEJ"
    assert bound == [(_DATASET, "t4fszEJ", "plasmodb")]
    kinds = [chunk.type for chunk in returned.metadata]
    assert kinds == ["data-eda.analysis-state"]


async def test_opening_a_second_analysis_replaces_the_binding(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    """One conversation binds at most one open analysis at a time."""
    from pathfinder.ai.tools.standalone import eda_analysis

    calls: list[str] = []

    async def bind(**kwargs: object) -> None:
        calls.append(str(kwargs["analysis_id"]))

    monkeypatch.setattr(eda_analysis, "bind_conversation_analysis", bind)
    monkeypatch.setattr(
        eda_analysis, "open_analysis", lambda *_a, **_k: _resolved("A")
    )
    monkeypatch.setattr(eda_analysis, "read_analysis", _read_detail)
    monkeypatch.setattr(
        eda_analysis, "get_study_detail_for_dataset", _phenotype_study
    )
    await eda_analysis.open_eda_analysis(
        lead_ctx, dataset_id=_DATASET, purpose="first"
    )
    monkeypatch.setattr(
        eda_analysis, "open_analysis", lambda *_a, **_k: _resolved("B")
    )
    await eda_analysis.open_eda_analysis(
        lead_ctx, dataset_id=_DATASET, purpose="second"
    )
    assert calls == ["A", "B"]


async def test_opening_an_analysis_on_a_study_with_no_gene_id_warns_the_model(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    """A study with no gene column can be explored and cannot be exported."""
    from pathfinder.ai.tools.standalone import eda_analysis

    monkeypatch.setattr(eda_analysis, "open_analysis", lambda *_a, **_k: _resolved("A"))
    monkeypatch.setattr(eda_analysis, "read_analysis", _read_detail)
    monkeypatch.setattr(eda_analysis, "bind_conversation_analysis", _noop_bind)
    monkeypatch.setattr(eda_analysis, "get_study_detail_for_dataset", _no_gene_study)

    returned = await eda_analysis.open_eda_analysis(
        lead_ctx, dataset_id=_DATASET, purpose="explore"
    )
    assert "cannot export" in returned.return_value.guidance
```

  `_resolved(value)` is a one-line async helper returning `value`; `_noop_bind`
  is an async no-op; `_read_detail` returns `_detail()`. Put all three at the top
  of the file with the fixtures.

- [ ] **Implementation.** Create
      `apps/api/src/pathfinder/ai/tools/standalone/eda_analysis.py`. Its
      docstring is what the model reads, so write it fully:

```python
async def open_eda_analysis(
    ctx: RunContext[LeadDeps],
    dataset_id: str,
    purpose: str,
) -> ToolReturn[EdaAnalysisOpened]:
    """Open an EDA analysis on a study, so filters and computes have somewhere
    to live.

    This creates a real analysis document in the researcher's VEuPathDB
    workspace and binds it to this conversation. From then on set_eda_filters,
    preview_eda_subset, run_eda_compute and create_eda_step all act on it, and
    the researcher sees the same analysis in the EDA tab and on the VEuPathDB
    site.

    One conversation holds one open analysis at a time. Opening a second one
    replaces the binding, so open the study you actually mean, after
    describe_eda_study confirms it carries the variables the question needs.

    ``purpose`` becomes the analysis's display name in the researcher's
    workspace, so write what the subset is for in their words - "P. berghei
    rows with successful genetic modification", not "analysis 1".

    Args:
        ctx: Agent run context.
        dataset_id: The ``datasetId`` from search_eda_studies. A ``DS_`` or
            ``EDAUD_`` id, never a ``STUDY_`` id.
        purpose: What this analysis is for, in the researcher's words.
    """
```

  The body, in order: resolve the study (so an unknown dataset fails before
  anything is created), `open_analysis`, `bind_conversation_analysis` (from
  implementer B's `services/eda/binding.py`), `read_analysis` to get the
  descriptor upstream stored, then return a `ToolReturn` whose `metadata` is one
  `eda_analysis_state_chunk`. The `guidance` on the return names the next tool
  and, when `find_gene_entity` reports a problem, says the study cannot export
  rows into a step and why.

  `bind_conversation_analysis` and `read_analysis` are module-level names so a
  test can replace them. Do not inline either.

- [ ] **Gates.**

---

### Task A5 - `set_eda_filters`: the sheet pattern

This is the tool the whole conversational experience turns on. It copies
`ai/tools/standalone/frame_spec.py::set_criterion` exactly: a first call with no
`filters` returns the SHEET and records nothing; a second call with `filters`
validates and applies; a rejection is a `ModelRetry` carrying the domain
predicates' own error strings.

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/ai/tools/eda/test_set_eda_filters_sheet.py`:

```python
"""set_eda_filters answers with a sheet, then binds what the model proposed."""

from __future__ import annotations

import pytest
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.tools.standalone import eda_analysis

pytestmark = pytest.mark.asyncio


async def test_a_first_call_with_no_filters_returns_the_sheet(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    monkeypatch.setattr(
        eda_analysis, "get_study_detail_for_dataset", _phenotype_study
    )
    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    result = await eda_analysis.set_eda_filters(lead_ctx, dataset_id=_DATASET)
    assert result.decide
    assert result.filters_template == []
    assert result.applied is False


async def test_the_sheet_names_the_exact_filter_type_per_variable(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    monkeypatch.setattr(
        eda_analysis, "get_study_detail_for_dataset", _phenotype_study
    )
    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    result = await eda_analysis.set_eda_filters(lead_ctx, dataset_id=_DATASET)
    species = next(e for e in result.decide if e.variable_id == "VAR_035294d0")
    assert species.filter_type == "stringSet"
    assert species.example == {
        "entityId": "GENE_PHENOTYPE_DATA_ENTITY",
        "variableId": "VAR_035294d0",
        "type": "stringSet",
        "stringSet": ["P. berghei"],
    }


async def test_a_second_call_applies_the_filters_and_emits_the_state(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    monkeypatch.setattr(
        eda_analysis, "get_study_detail_for_dataset", _phenotype_study
    )
    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    monkeypatch.setattr(eda_analysis, "apply_filters", _apply_ok)
    returned = await eda_analysis.set_eda_filters(
        lead_ctx,
        dataset_id=_DATASET,
        filters=[_species_filter("P. berghei")],
    )
    assert returned.return_value.applied is True
    assert returned.return_value.num_filters == 1
    assert [c.type for c in returned.metadata] == ["data-eda.analysis-state"]


async def test_an_out_of_vocabulary_value_raises_a_model_retry_with_the_options(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    """The service would answer 200 with count 0, so the retry is the only signal."""
    monkeypatch.setattr(
        eda_analysis, "get_study_detail_for_dataset", _phenotype_study
    )
    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    monkeypatch.setattr(eda_analysis, "apply_filters", _apply_rejects)
    with pytest.raises(ModelRetry) as excinfo:
        await eda_analysis.set_eda_filters(
            lead_ctx,
            dataset_id=_DATASET,
            filters=[_species_filter("P. vivax")],
        )
    message = str(excinfo.value)
    assert "P. vivax" in message
    assert "P. berghei" in message
    assert "do not request the sheet again" in message


async def test_calling_with_no_open_analysis_raises_a_model_retry_naming_the_tool(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    monkeypatch.setattr(eda_analysis, "bound_analysis", _unbound)
    with pytest.raises(ModelRetry) as excinfo:
        await eda_analysis.set_eda_filters(
            lead_ctx, dataset_id=_DATASET, filters=[_species_filter("P. berghei")]
        )
    assert "open_eda_analysis" in str(excinfo.value)


async def test_the_second_sheet_for_the_same_study_omits_the_vocabularies(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    """The model already holds them; resending costs the whole prompt cache."""
    monkeypatch.setattr(
        eda_analysis, "get_study_detail_for_dataset", _phenotype_study
    )
    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    first = await eda_analysis.set_eda_filters(lead_ctx, dataset_id=_DATASET)
    second = await eda_analysis.set_eda_filters(lead_ctx, dataset_id=_DATASET)
    assert any(e.vocabulary for e in first.decide)
    assert all(e.vocabulary == [] for e in second.decide)
    assert all(e.vocabulary_note for e in second.decide if e.vocabulary_total)


async def test_an_empty_filter_list_clears_the_subset(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    """An analysis with no filters is legal and means the whole study."""
    monkeypatch.setattr(
        eda_analysis, "get_study_detail_for_dataset", _phenotype_study
    )
    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    monkeypatch.setattr(eda_analysis, "apply_filters", _apply_cleared)
    returned = await eda_analysis.set_eda_filters(
        lead_ctx, dataset_id=_DATASET, filters=[]
    )
    assert returned.return_value.applied is True
    assert returned.return_value.num_filters == 0
```

  Note the distinction the last test pins: `filters=None` asks for the sheet,
  `filters=[]` clears the subset. They are different calls and the signature
  must keep them different - default `None`, and an explicit empty list means
  "no filters".

- [ ] **Implementation.** Append to `eda_analysis.py`. The sheet entry model
      goes in `_eda_models.py`:

```python
class EdaFilterSheetEntry(CamelModel):
    """One variable, with everything needed to write a filter for it."""

    entity_id: str
    entity_display_name: str
    variable_id: str
    display_name: str
    variable_type: str
    filter_type: EdaFilterType
    data_shape: str | None = None
    is_multi_valued: bool = False
    vocabulary: list[str] = Field(default_factory=list)
    vocabulary_total: int = 0
    vocabulary_note: str | None = None
    range_min: float | None = None
    range_max: float | None = None
    date_min: str | None = None
    date_max: str | None = None
    sub_filter_variable_ids: list[str] = Field(default_factory=list)
    example: JSONObject = Field(default_factory=dict)


class EdaFiltersResult(CamelModel):
    """Result of one set_eda_filters call."""

    applied: bool = False
    analysis_id: str = ""
    dataset_id: str = ""
    num_filters: int = 0
    # Every filterable variable, with its type, its vocabulary and one example
    # filter object. Declared before ``filters_template`` so the sheet is read
    # before the shape to copy.
    decide: list[EdaFilterSheetEntry] = Field(default_factory=list)
    # The exact array shape to send back. Empty on the first call.
    filters_template: list[JSONObject] = Field(default_factory=list)
    filter_summaries: list[str] = Field(default_factory=list)
    guidance: str = ""
```

  and the tool, with the docstring the model reads:

```python
async def set_eda_filters(
    ctx: RunContext[LeadDeps],
    *,
    dataset_id: str,
    filters: list[EdaFilter] | None = None,
) -> EdaFiltersResult | ToolReturn[EdaFiltersResult]:
    """Set the whole subset of the open EDA analysis, in two calls.

    Call this ONCE with no ``filters`` to receive ``decide``, the FILTER SHEET:
    every filterable variable of the study with its entity, its exact filter
    type, its vocabulary or its range, and one complete example filter object
    you can copy. Nothing is recorded by that call.

    Then call it AGAIN with ``filters`` set to the whole array you want. The
    array REPLACES the analysis's subset; it is not a patch, so send every
    filter that should apply. An empty array clears the subset and means the
    whole study.

    Writing the array, and every rule here is one the service will not enforce:

    - Copy ``entityId`` and ``variableId`` together from one sheet entry. A
      variableId is only valid on the entity that declares it.
    - Take ``type`` from the entry's ``filterType``, never from what the value
      looks like. A longitude variable is not a number variable, and a category
      variable holds no values at all.
    - For a string variable, every value must appear in the entry's
      ``vocabulary``. An invented value returns a count of zero with no error,
      so it looks like a real empty result.
    - For a date variable, append ``T00:00:00`` to every bound. The sheet
      already shows the bounds in that form. A bare ``2017-05-05`` is a server
      error.
    - The array is AND, always, across variables and across entities. To say
      "berghei OR falciparum", write ONE stringSet holding both. Two entries on
      one single-valued variable select nothing.
    - ``isMultiValued`` true means one record holds several values, so the
      per-value counts do not add up to the record count and two filters on
      that variable mean "has both".
    - A multiFilter targets a category whose ``filterType`` is ``multiFilter``
      and names its ``subFilterVariableIds``; its ``operation`` is ``union``
      for OR or ``intersect`` for AND. It is the only OR in the algebra.
    - Never put a range's ``min`` above its ``max``, and never set a
      longitudeRange's ``left`` equal to its ``right``. Both are accepted and
      both mean something other than what they look like.

    A rejected array comes back as a retry naming the offending value and the
    valid ones. Fix that value and re-send the whole array; do not ask for the
    sheet again.

    Args:
        ctx: Agent run context.
        dataset_id: The dataset of the open analysis.
        filters: The complete filter array, or omit it to read the sheet.
    """
```

  The body:

  1. `bound_analysis(ctx)` returns the conversation's `(dataset_id,
     analysis_id)` or `None`. When `None`, `ModelRetry` naming
     `open_eda_analysis`. When the bound dataset differs from the argument,
     `ModelRetry` saying which analysis is open.
  2. `filters is None`: build the sheet from
     `get_study_detail_for_dataset`, mark it shown on
     `ctx.deps.state` (see below), return `EdaFiltersResult(decide=...,
     filters_template=[], guidance=...)`. No `ToolReturn`, no chunk: nothing was
     recorded.
  3. `filters is not None`: `apply_filters(...)`, catching `SubsetRejected` and
     re-raising as `ModelRetry` with the joined error strings plus the fixed
     sentence "The valid values are listed above; do not request the sheet
     again." Then return a `ToolReturn` whose `return_value` reports
     `applied=True` and whose `metadata` is one `eda_analysis_state_chunk`.

  **Where "was the sheet shown" lives.** `set_criterion` keeps it on
  `AgentToolState.sheeted_criteria`, a `set[tuple[str, str]]` with
  `mark_sheet_shown` / `was_sheet_shown`. `LeadDeps` has no `AgentToolState`; it
  has `state: PipelineState`. Add the same pair to the Lead's own turn state:
  a `set[str]` of dataset ids on `PipelineState`'s domain section, with
  `mark_eda_sheet_shown(dataset_id)` and `was_eda_sheet_shown(dataset_id)`
  methods beside it. Read
  `apps/api/src/pathfinder/ai/graph/state.py` first, put the field where the
  other per-turn sets live, and add its two tests.

  **The example filter object.** Build it from the variable itself, not from a
  template string: a `stringSet` example uses the first vocabulary term, a
  `numberRange` example uses the declared bounds, a `dateRange` example uses the
  declared bounds with `T00:00:00`, a `multiFilter` example uses the first two
  children with `operation: "union"`. An example the model can copy is worth
  more than a paragraph telling it the shape.

- [ ] **Gates**, with
      `src/pathfinder/tests/unit/ai/tools/eda/` and
      `src/pathfinder/tests/unit/ai/graph/`.

---

### Task A6 - `preview_eda_subset`

- [ ] **Failing test.** Append to
      `apps/api/src/pathfinder/tests/integration/eda/test_eda_tools.py`:

```python
async def test_preview_eda_subset_reports_both_counts_and_emits_the_part(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    from pathfinder.ai.tools.standalone import eda_analysis

    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    monkeypatch.setattr(eda_analysis, "preview_subset", _preview_ok)
    monkeypatch.setattr(
        eda_analysis, "get_study_detail_for_dataset", _phenotype_study
    )
    returned = await eda_analysis.preview_eda_subset(
        lead_ctx,
        entity_id=_ENTITY,
        distribution_variable_id="VAR_035294d0",
    )
    assert returned.return_value.count == 4011
    assert returned.return_value.unfiltered_count == 4279
    assert [c.type for c in returned.metadata] == ["data-eda.subset-preview"]


async def test_a_preview_of_zero_says_which_filter_emptied_the_subset(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    """Zero is a real answer and the model must not silently narrate a result."""
    from pathfinder.ai.tools.standalone import eda_analysis

    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    monkeypatch.setattr(eda_analysis, "preview_subset", _preview_zero)
    monkeypatch.setattr(
        eda_analysis, "get_study_detail_for_dataset", _phenotype_study
    )
    returned = await eda_analysis.preview_eda_subset(lead_ctx, entity_id=_ENTITY)
    assert returned.return_value.count == 0
    assert "selects no records" in returned.return_value.guidance


async def test_a_multi_valued_distribution_warns_that_the_values_do_not_partition(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    from pathfinder.ai.tools.standalone import eda_analysis

    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    monkeypatch.setattr(eda_analysis, "preview_subset", _preview_ok)
    monkeypatch.setattr(
        eda_analysis, "get_study_detail_for_dataset", _phenotype_study
    )
    returned = await eda_analysis.preview_eda_subset(
        lead_ctx, entity_id=_ENTITY, distribution_variable_id="VAR_035294d0"
    )
    assert "several values per record" in returned.return_value.guidance


async def test_a_preview_with_no_open_analysis_raises_a_model_retry(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    from pydantic_ai.exceptions import ModelRetry

    from pathfinder.ai.tools.standalone import eda_analysis

    monkeypatch.setattr(eda_analysis, "bound_analysis", _unbound)
    with pytest.raises(ModelRetry) as excinfo:
        await eda_analysis.preview_eda_subset(lead_ctx, entity_id=_ENTITY)
    assert "open_eda_analysis" in str(excinfo.value)
```

- [ ] **Implementation.** The docstring:

```python
async def preview_eda_subset(
    ctx: RunContext[LeadDeps],
    *,
    entity_id: str,
    distribution_variable_id: str | None = None,
) -> ToolReturn[EdaSubsetPreviewResult]:
    """Count what the open analysis's filters select, on one entity.

    Call this after every set_eda_filters, before you tell the researcher a
    number and before you create a step. It returns the filtered count and the
    unfiltered count for that entity, so the effect of the subset is visible.

    ``entityId`` decides WHAT is counted, and it is independent of which
    entities the filters name: a filter on a child entity restricts the parent
    to parents that still have a surviving child, and a filter on a parent
    restricts the child to children under a surviving parent.

    Name ``distributionVariableId`` to also get that variable's histogram under
    the subset. That is what shows the researcher the shape of what is left.

    A count of zero is a real answer, not an error. Say which filter emptied
    the subset and offer one concrete way to widen it.

    Args:
        ctx: Agent run context.
        entity_id: The entity whose records are counted.
        distribution_variable_id: A variable on that entity to histogram.
    """
```

  The guidance the body composes, by case:

  | case | sentence |
  |---|---|
  | `count == 0` | "This subset selects no records on <entity>. Name the filter that emptied it and offer one way to widen it." |
  | `count == unfiltered_count` and filters exist | "The subset is the whole entity, so these filters narrow nothing here. They may still narrow another entity." |
  | the distribution's variable is multi-valued | "This variable holds several values per record, so the histogram's values sum above the record count. State which denominator any percentage uses." |
  | `num_missing_cases > 0` | "<n> records on this entity have no value for that variable." |

- [ ] **Gates.**

---

### Task A7 - the toolset, the Lead wiring, and the instructions

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/ai/tools/eda/test_eda_toolset.py`:

```python
"""The EDA toolset, and the Lead that carries it."""

from __future__ import annotations

from pydantic_ai.toolsets.function import FunctionToolset
from pydantic_ai.toolsets.wrapper import WrapperToolset

from pathfinder.ai.lead.lead_agent import build_lead_agent
from pathfinder.ai.tools.toolsets.eda import build_toolset

_EDA_TOOLS = {
    "search_eda_studies",
    "describe_eda_study",
    "open_eda_analysis",
    "set_eda_filters",
    "preview_eda_subset",
    "run_eda_compute",
    "create_eda_step",
}


def _function_toolset(toolset: object) -> FunctionToolset:
    while isinstance(toolset, WrapperToolset):
        toolset = toolset.wrapped
    assert isinstance(toolset, FunctionToolset)
    return toolset


def test_the_toolset_carries_exactly_the_seven_contract_tools() -> None:
    tools = _function_toolset(build_toolset()).tools
    assert set(tools) == _EDA_TOOLS


def test_the_durable_tool_is_registered_sequential() -> None:
    """A durable tool suspends the graph; a parallel sibling's return is orphaned."""
    tools = _function_toolset(build_toolset()).tools
    assert tools["run_eda_compute"].tool_def.sequential is True


def test_the_lead_agent_carries_the_eda_toolset() -> None:
    agent = build_lead_agent()
    names: set[str] = set()
    for toolset in agent.toolsets:
        names |= set(_function_toolset(toolset).tools)
    assert _EDA_TOOLS <= names


def test_no_eda_tool_name_collides_with_a_lead_tool() -> None:
    agent = build_lead_agent()
    seen: list[str] = []
    for toolset in agent.toolsets:
        seen.extend(_function_toolset(toolset).tools)
    assert len(seen) == len(set(seen))
```

  `Agent.toolsets` may not be the accessor pydantic-ai exposes. Find the real
  one by reading
  `apps/api/.venv/lib/python3.14/site-packages/pydantic_ai/agent/__init__.py`
  before writing the test, and use whatever it is. Do not guess a pydantic-ai
  surface.

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/ai/lead/test_eda_instructions.py`:

```python
"""The instructions that tell the Lead when EDA is the right route."""

from __future__ import annotations

from pathfinder.ai.lead._lead_instructions import LEAD_INSTRUCTIONS


def test_the_instructions_name_every_eda_tool_in_call_order() -> None:
    order = [
        "search_eda_studies",
        "describe_eda_study",
        "open_eda_analysis",
        "set_eda_filters",
        "preview_eda_subset",
        "run_eda_compute",
        "create_eda_step",
    ]
    positions = [LEAD_INSTRUCTIONS.index(name) for name in order]
    assert positions == sorted(positions)


def test_the_instructions_say_when_eda_beats_a_classic_search() -> None:
    assert "sample-level" in LEAD_INSTRUCTIONS
    assert "eda_analysis_spec" in LEAD_INSTRUCTIONS


def test_the_instructions_forbid_quoting_a_count_before_a_preview() -> None:
    assert "preview_eda_subset" in LEAD_INSTRUCTIONS
    assert "before you state a count" in LEAD_INSTRUCTIONS


def test_the_instructions_say_the_compute_runs_before_the_step() -> None:
    index_compute = LEAD_INSTRUCTIONS.index("run_eda_compute")
    index_step = LEAD_INSTRUCTIONS.index("create_eda_step")
    assert index_compute < index_step
    assert "completes" in LEAD_INSTRUCTIONS


def test_the_instructions_are_ascii_only() -> None:
    assert LEAD_INSTRUCTIONS.isascii()
```

- [ ] **Implementation.** Create
      `apps/api/src/pathfinder/ai/tools/toolsets/eda.py`:

```python
"""The EDA toolset: explore a study in conversation and export a step."""

from pydantic_ai import Tool
from pydantic_ai.toolsets.abstract import AbstractToolset
from pydantic_ai.toolsets.function import FunctionToolset

from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.ai.tools.standalone.eda_analysis import (
    open_eda_analysis,
    preview_eda_subset,
    set_eda_filters,
)
from pathfinder.ai.tools.standalone.eda_catalog import (
    describe_eda_study,
    search_eda_studies,
)
from pathfinder.ai.tools.standalone.eda_compute import run_eda_compute
from pathfinder.ai.tools.standalone.eda_step import create_eda_step


def build_toolset() -> AbstractToolset[LeadDeps]:
    """The seven EDA tools the Lead calls.

    ``run_eda_compute`` is registered sequential: a durable tool suspends the
    graph, and a sibling running in parallel would leave an orphaned tool
    return in the persisted history.
    """
    toolset: FunctionToolset[LeadDeps] = FunctionToolset(
        max_retries=3,
        tools=[
            search_eda_studies,
            describe_eda_study,
            open_eda_analysis,
            set_eda_filters,
            preview_eda_subset,
            Tool(run_eda_compute, sequential=True, max_retries=3),
            create_eda_step,
        ],
    )
    return toolset
```

- [ ] **Wire it into the Lead.** In `ai/lead/lead_agent.py`, add
      `toolsets=[build_eda_toolset()]` to the `Agent(...)` call, importing
      `build_toolset` under a name that does not collide with the three phase
      toolsets already imported elsewhere. CLAUDE.md forbids `import as`, so
      import the module and call `eda_toolset.build_toolset()`:

```python
from pathfinder.ai.tools.toolsets import eda as eda_toolset
...
        toolsets=[eda_toolset.build_toolset()],
```

- [ ] **Write the instructions.** Append this section to `LEAD_INSTRUCTIONS`,
      after "## Rules" and before "## User-facing voice". It is prose the model
      reads every turn, so every sentence must change a decision.

```
## EDA: sample-level data

Some VEuPathDB data is not a gene attribute. Expression levels, phenotype
scores, antibody signals and sample metadata live in EDA studies, one row per
sample or per gene per sample. A question about a CONDITION, a COMPARISON, a
TREATMENT or a SAMPLE GROUP - "genes up in febrile samples", "the heat shock
RNA-Seq data", "phenotypes in P. berghei" - is an EDA question, and a classic
search cannot answer it.

The tell in the catalog: a search whose overview says it carries
``eda_analysis_spec`` is EDA-backed. Do NOT try to propose a value for that
parameter and do NOT route it through frame_problem; its value is a whole EDA
analysis document. Use the EDA tools instead.

The loop, in order:

1. ``search_eda_studies`` - find the study by what it measures. Report the
   study you picked and why, and say when the account cannot export its rows.
2. ``describe_eda_study`` - read the entity tree and the variables. Call it
   with an ``entityId`` when you need that entity's variables.
3. ``open_eda_analysis`` - create the analysis this conversation edits. One at
   a time.
4. ``set_eda_filters`` - twice: once for the sheet, once with the array. The
   array replaces the subset, so send every filter that should apply.
5. ``preview_eda_subset`` - always, before you state a count. The filters can
   select nothing and the service reports that as a plain zero, so a number you
   did not measure is a number you invented.
6. ``run_eda_compute`` - for a comparison. It runs on the worker and can take
   minutes; the turn ends and resumes on its own. Narrate what it found: the
   effect-size label, how many genes pass the thresholds, and how many are up
   against down.
7. ``create_eda_step`` - export the subset, or the genes passing the volcano
   thresholds, as an ordinary step in the researcher's strategy. For a
   compute-backed export, run_eda_compute must have COMPLETED first.

Rules that are not negotiable:

- Never quote a count you did not get from ``preview_eda_subset`` or from a
  compute's own summary. An EDA subset that selects nothing answers zero with
  no error.
- Never invent an entity id, a variable id or a vocabulary value. Copy them
  from the sheet. An invented string value gives a plausible-looking empty
  answer.
- A zero subset is a finding: say which filter emptied it and offer one
  concrete way to widen it. Do not silently re-filter.
- Say which entity a count is on. A count of samples and a count of genes are
  different numbers from the same subset.
- When a study carries no gene column, say the subset cannot become a step and
  offer the analysis itself as the answer.
```

- [ ] **Rebuild and verify the container updated**, because prompts and tools
      run in the worker:

  ```bash
  docker compose --env-file .env.dev up -d --build api worker web
  docker compose exec worker grep -c "sample-level data" \
    /app/src/pathfinder/ai/lead/_lead_instructions.py
  ```

  A count of 0 means the old container is still running; add
  `--force-recreate` and check again.

- [ ] **Section end.** Run the section-end ladder, including the
      `assistant-core` half.

---

## Implementer B: `create_eda_step`, `conversation_analyses`, and the binding

### Files

| Action | Path |
|---|---|
| Modify | `apps/api/src/pathfinder/persistence/models.py` (one table, one view model) |
| Create | `apps/api/src/pathfinder/persistence/repositories/conversation_analysis.py` |
| Create | `apps/api/alembic/versions/2026_08_28_0001_add_conversation_analyses.py` |
| Create | `apps/api/src/pathfinder/services/eda/binding.py` |
| Create | `apps/api/src/pathfinder/ai/tools/standalone/eda_step.py` |
| Create | `apps/api/src/pathfinder/tests/unit/persistence/test_conversation_analyses_model.py` |
| Create | `apps/api/src/pathfinder/tests/integration/persistence/test_conversation_analysis_repo.py` |
| Create | `apps/api/src/pathfinder/tests/integration/eda/test_create_eda_step.py` |

### Interfaces

**Consumes:** batch 1 and 2 as listed; from the repository
`assistant_core.persistence.models.Base`,
`assistant_core.persistence.models.Conversation`,
`pathfinder.domain.strategy.ast.StrategyStepNode`,
`pathfinder.domain.strategy.operations.AddLeafOp`,
`pathfinder.domain.strategy.operations.types.AttachNewRoot`,
`pathfinder.domain.strategy.operations.types.AttachIntoSlot`,
`pathfinder.services.strategies.commit.apply_operations_and_commit`,
`pathfinder.services.strategies.context.StrategyMutationContext`,
`pathfinder.ai.tools.standalone._stream_parts.graph_snapshot_chunk`,
`pathfinder.ai.tools.standalone._stream_parts.strategy_link_chunk`.

**Produces:**

```python
# persistence/models.py
class ConversationAnalysis(Base)          # table conversation_analyses
class ConversationAnalysisView(BaseModel)

# persistence/repositories/conversation_analysis.py
class ConversationAnalysesRepository:
    def __init__(self, *, session_factory: SessionFactory) -> None
    async def get(self, *, conversation_id: UUID) -> ConversationAnalysisView | None
    async def bind(self, *, conversation_id: UUID, site_id: str,
                   dataset_id: str, analysis_id: str) -> None
    async def unbind(self, *, conversation_id: UUID) -> None

# services/eda/binding.py
async def bind_conversation_analysis(*, conversation_id: UUID, site_id: str,
                                     dataset_id: str, analysis_id: str) -> None
async def bound_conversation_analysis(*, conversation_id: UUID
                                      ) -> ConversationAnalysisView | None
async def unbind_conversation_analysis(*, conversation_id: UUID) -> None
async def read_analysis(site_id: str, *, analysis_id: str) -> EdaAnalysisDetail

# ai/tools/standalone/eda_step.py
async def create_eda_step(ctx, *, search_name: str | None = None,
                          attach_to_step_id: str | None = None,
                          slot: Literal["primary", "secondary"] | None = None,
                          effect_size_threshold: float | None = None,
                          significance_threshold: float | None = None,
                          effect_direction: str = "upAndDown",
                          ) -> ToolReturn[EdaStepCreated]
def eda_search_name(*, is_compute_backed: bool) -> str
```

---

### Task B1 - the table, the model and the migration

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/persistence/test_conversation_analyses_model.py`:

```python
"""PathFinder stores a reference to the upstream analysis and nothing else."""

from __future__ import annotations

from pathfinder.persistence.models import ConversationAnalysis


def test_the_table_is_named_by_the_contract() -> None:
    assert ConversationAnalysis.__tablename__ == "conversation_analyses"


def test_the_conversation_is_the_primary_key_so_one_analysis_is_bound() -> None:
    keys = [c.name for c in ConversationAnalysis.__table__.primary_key.columns]
    assert keys == ["conversation_id"]


def test_the_row_holds_only_the_reference() -> None:
    """Storing the descriptor would create a copy that drifts on the next edit."""
    columns = {c.name for c in ConversationAnalysis.__table__.columns}
    assert columns == {
        "conversation_id",
        "site_id",
        "dataset_id",
        "analysis_id",
        "created_at",
    }


def test_the_conversation_foreign_key_cascades() -> None:
    fks = list(ConversationAnalysis.__table__.c.conversation_id.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column.table.name == "conversations"
    assert fks[0].ondelete == "CASCADE"
```

- [ ] **Run it.** Expect `ImportError: cannot import name 'ConversationAnalysis'`.

- [ ] **Implementation.** Append to
      `apps/api/src/pathfinder/persistence/models.py`, beside
      `ConversationStrategy`:

```python
class ConversationAnalysis(Base):
    """The EDA analysis one chat thread has open.

    The EDA user service is the SSOT for the document; this row is the
    attachment. Ownership is the parent thread's, so there is no user column.
    """

    __tablename__ = "conversation_analyses"

    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    site_id: Mapped[str] = mapped_column(String(50), nullable=False)
    dataset_id: Mapped[str] = mapped_column(String(100), nullable=False)
    analysis_id: Mapped[str] = mapped_column(String(100), nullable=False)
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ConversationAnalysisView(BaseModel):
    """Read shape of a thread's bound analysis."""

    model_config = ConfigDict(frozen=True, from_attributes=True, extra="forbid")

    site_id: str
    dataset_id: str
    analysis_id: str
    revision: int
```

`revision` is the mutation counter the `EdaAnalysisState.revision` field and
the store's reconcile rule read. The repository increments it atomically
(`UPDATE ... SET revision = revision + 1 RETURNING revision`) inside every
authoring mutation, so two surfaces patching the same analysis always see a
strictly growing number.

- [ ] **The migration.** Create
      `apps/api/alembic/versions/2026_08_28_0001_add_conversation_analyses.py`.
      The naming pattern is `YYYY_MM_DD_NNNN_<snake_case_summary>.py`, the
      `revision` string equals the numeric prefix, and `down_revision` is the
      current head. Find the head first:

  ```bash
  cd apps/api && uv run alembic heads
  ```

  At the time this plan was written the head was `2026_08_23_0001`. Use whatever
  `alembic heads` reports.

```python
"""add_conversation_analyses

Revision ID: 2026_08_28_0001
Revises: 2026_08_23_0001
Create Date: 2026-08-28 00:00:00.000000

A thread gets a row only while it holds an open EDA analysis. The upstream EDA
user service owns the document.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2026_08_28_0001"
down_revision: str | Sequence[str] | None = "2026_08_23_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_analyses",
        sa.Column(
            "conversation_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("site_id", sa.String(50), nullable=False),
        sa.Column("dataset_id", sa.String(100), nullable=False),
        sa.Column("analysis_id", sa.String(100), nullable=False),
        sa.Column(
            "revision", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_conversation_analyses_dataset_id",
        "conversation_analyses",
        ["dataset_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_analyses_dataset_id",
        table_name="conversation_analyses",
    )
    op.drop_table("conversation_analyses")
```

- [ ] **Verify the migration runs both ways** against a real database:

  ```bash
  docker compose --env-file .env.dev up -d db
  cd apps/api && uv run alembic upgrade head && uv run alembic downgrade -1 \
    && uv run alembic upgrade head
  ```

- [ ] **Gates**, with
      `src/pathfinder/tests/unit/persistence/test_conversation_analyses_model.py`.

---

### Task B2 - the repository and the binding service

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/integration/persistence/test_conversation_analysis_repo.py`:

```python
"""One thread binds at most one open analysis."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from assistant_core.persistence.models import Conversation
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pathfinder.persistence.models import ConversationAnalysis, User
from pathfinder.persistence.repositories.conversation_analysis import (
    ConversationAnalysesRepository,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def db_session(
    session_maker: async_sessionmaker[AsyncSession],
    db_cleaner: None,
) -> AsyncGenerator[AsyncSession]:
    del db_cleaner
    async with session_maker() as session:
        yield session


@pytest.fixture
async def conversation(db_session: AsyncSession) -> Conversation:
    user = User(id=uuid4())
    db_session.add(user)
    await db_session.flush()
    thread = Conversation(id=uuid4(), user_id=user.id)
    db_session.add(thread)
    await db_session.commit()
    return thread


async def test_an_unbound_thread_reads_as_none(
    session_maker: async_sessionmaker[AsyncSession], conversation: Conversation
) -> None:
    repo = ConversationAnalysesRepository(session_factory=session_maker)
    assert await repo.get(conversation_id=conversation.id) is None


async def test_binding_then_reading_returns_the_reference(
    session_maker: async_sessionmaker[AsyncSession], conversation: Conversation
) -> None:
    repo = ConversationAnalysesRepository(session_factory=session_maker)
    await repo.bind(
        conversation_id=conversation.id,
        site_id="plasmodb",
        dataset_id="DS_53f554ec6a",
        analysis_id="t4fszEJ",
    )
    view = await repo.get(conversation_id=conversation.id)
    assert view is not None
    assert view.dataset_id == "DS_53f554ec6a"
    assert view.analysis_id == "t4fszEJ"
    assert view.site_id == "plasmodb"


async def test_binding_twice_replaces_the_row_rather_than_adding_one(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    conversation: Conversation,
) -> None:
    repo = ConversationAnalysesRepository(session_factory=session_maker)
    await repo.bind(
        conversation_id=conversation.id,
        site_id="plasmodb",
        dataset_id="DS_a",
        analysis_id="A",
    )
    await repo.bind(
        conversation_id=conversation.id,
        site_id="plasmodb",
        dataset_id="DS_b",
        analysis_id="B",
    )
    rows = (
        await db_session.execute(
            select(ConversationAnalysis).where(
                ConversationAnalysis.conversation_id == conversation.id
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].analysis_id == "B"


async def test_unbinding_removes_the_row(
    session_maker: async_sessionmaker[AsyncSession], conversation: Conversation
) -> None:
    repo = ConversationAnalysesRepository(session_factory=session_maker)
    await repo.bind(
        conversation_id=conversation.id,
        site_id="plasmodb",
        dataset_id="DS_a",
        analysis_id="A",
    )
    await repo.unbind(conversation_id=conversation.id)
    assert await repo.get(conversation_id=conversation.id) is None


async def test_deleting_the_thread_removes_the_binding(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    conversation: Conversation,
) -> None:
    repo = ConversationAnalysesRepository(session_factory=session_maker)
    await repo.bind(
        conversation_id=conversation.id,
        site_id="plasmodb",
        dataset_id="DS_a",
        analysis_id="A",
    )
    await db_session.delete(await db_session.get(Conversation, conversation.id))
    await db_session.commit()
    assert await repo.get(conversation_id=conversation.id) is None
```

- [ ] **Implementation.** Create
      `apps/api/src/pathfinder/persistence/repositories/conversation_analysis.py`,
      modelled on `repositories/background_tasks.py` (its own session per unit
      of work, because the worker has no long-lived session):

```python
"""The EDA analysis a thread has open. One row per thread, or none."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.persistence.models import (
    ConversationAnalysis,
    ConversationAnalysisView,
)

SessionFactory = Callable[[], AsyncSession]


class ConversationAnalysesRepository:
    """Bind, read and clear a thread's open analysis."""

    def __init__(self, *, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def get(
        self,
        *,
        conversation_id: UUID,
    ) -> ConversationAnalysisView | None:
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(ConversationAnalysis).where(
                        ConversationAnalysis.conversation_id == conversation_id
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            return ConversationAnalysisView.model_validate(row)

    async def bind(
        self,
        *,
        conversation_id: UUID,
        site_id: str,
        dataset_id: str,
        analysis_id: str,
    ) -> None:
        """Bind this analysis, replacing whatever the thread had open."""
        async with self._session_factory() as session:
            statement = (
                insert(ConversationAnalysis)
                .values(
                    conversation_id=conversation_id,
                    site_id=site_id,
                    dataset_id=dataset_id,
                    analysis_id=analysis_id,
                )
                .on_conflict_do_update(
                    index_elements=[ConversationAnalysis.conversation_id],
                    set_={
                        "site_id": site_id,
                        "dataset_id": dataset_id,
                        "analysis_id": analysis_id,
                    },
                )
            )
            await session.execute(statement)
            await session.commit()

    async def unbind(self, *, conversation_id: UUID) -> None:
        async with self._session_factory() as session:
            await session.execute(
                delete(ConversationAnalysis).where(
                    ConversationAnalysis.conversation_id == conversation_id
                )
            )
            await session.commit()
```

- [ ] Create `apps/api/src/pathfinder/services/eda/binding.py` as the thin
      service the tools call, so `ai/tools` never touches `persistence`:

```python
"""The conversation-to-analysis binding, and the read that follows it."""

from __future__ import annotations

from uuid import UUID

from assistant_core.platform.db import async_session_factory

from pathfinder.integrations.eda.factory import get_eda_analyses_client
from pathfinder.integrations.eda.models import EdaAnalysisDetail
from pathfinder.persistence.models import ConversationAnalysisView
from pathfinder.persistence.repositories.conversation_analysis import (
    ConversationAnalysesRepository,
)
from pathfinder.services.eda.authoring import resolve_eda_user_id


def _repo() -> ConversationAnalysesRepository:
    return ConversationAnalysesRepository(session_factory=async_session_factory)


async def bind_conversation_analysis(
    *,
    conversation_id: UUID,
    site_id: str,
    dataset_id: str,
    analysis_id: str,
) -> None:
    await _repo().bind(
        conversation_id=conversation_id,
        site_id=site_id,
        dataset_id=dataset_id,
        analysis_id=analysis_id,
    )


async def bound_conversation_analysis(
    *,
    conversation_id: UUID,
) -> ConversationAnalysisView | None:
    return await _repo().get(conversation_id=conversation_id)


async def unbind_conversation_analysis(*, conversation_id: UUID) -> None:
    await _repo().unbind(conversation_id=conversation_id)


async def read_analysis(site_id: str, *, analysis_id: str) -> EdaAnalysisDetail:
    """The upstream document. It is the SSOT, so every render reads it."""
    analyses = get_eda_analyses_client(site_id)
    return await analyses.get(
        user_id=await resolve_eda_user_id(site_id),
        analysis_id=analysis_id,
    )
```

- [ ] **Gates**, with
      `src/pathfinder/tests/integration/persistence/test_conversation_analysis_repo.py`.

---

### Task B3 - `create_eda_step`: the bridge into the existing strategy service

**The search-name mapping, decided here so no implementer guesses it.**

| what is exported | `searchName` | why |
|---|---|---|
| the subset's genes | `GenesByEdaSubset` | the generic API-facing subset search, with `eda_dataset_id` VISIBLE, so the caller sets it. The per-dataset searches instead ride the `GenesByEdaSubsetGeneric` query with a hidden dataset default, and the genomics UI routes its widget on that query name - which is why the bare search renders no widget upstream and is exactly right for an API caller (see [../eda-wdk-bridge.md](../eda-wdk-bridge.md)). |
| the genes passing a volcano's thresholds | `GenesByEdaVizWithCompute` | `GeneEdaVizWithComputePlugin` reads the spec's first computation and its first visualization, requires that visualization to be `volcanoplot` with both thresholds, and delivers `effectSize` and `pValue` as dynamic columns. |

Both are real searches on the live catalog (1 and 1 of the 68). A per-dataset
search such as `GenesByRNASeq{dataset}DESeq` would also work and defaults
`eda_dataset_id` for you, but its name changes with every dataset load, so
`create_eda_step` accepts an explicit `search_name` for the case where the
researcher already ran one, and defaults to the two generic searches otherwise.

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/integration/eda/test_create_eda_step.py`:

```python
"""create_eda_step builds an ordinary WDK step through the existing service."""

from __future__ import annotations

import json

import pytest
from pydantic_ai.exceptions import ModelRetry

pytestmark = pytest.mark.asyncio

_DATASET = "DS_53f554ec6a"
_ENTITY = "GENE_PHENOTYPE_DATA_ENTITY"


async def test_a_subset_export_uses_the_generic_subset_search(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    from pathfinder.ai.tools.standalone import eda_step

    applied: list[object] = []

    async def commit(*, deps: object, ops: list[object]) -> object:
        applied.append(ops)
        return _commit_result()

    monkeypatch.setattr(eda_step, "bound_analysis", _bound)
    monkeypatch.setattr(eda_step, "read_analysis", _read_detail)
    monkeypatch.setattr(eda_step, "apply_operations_and_commit", commit)

    returned = await eda_step.create_eda_step(lead_ctx)
    step = applied[0][0].step
    assert step.search_name == "GenesByEdaSubset"
    assert step.parameters["eda_dataset_id"].value == _DATASET
    spec = json.loads(step.parameters["eda_analysis_spec"].value)
    assert spec["studyId"] == _DATASET
    assert returned.return_value.search_name == "GenesByEdaSubset"


async def test_a_compute_export_uses_the_viz_with_compute_search(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    from pathfinder.ai.tools.standalone import eda_step

    applied: list[object] = []

    async def commit(*, deps: object, ops: list[object]) -> object:
        applied.append(ops)
        return _commit_result()

    monkeypatch.setattr(eda_step, "bound_analysis", _bound)
    monkeypatch.setattr(eda_step, "read_analysis", _read_detail_with_computation)
    monkeypatch.setattr(eda_step, "apply_operations_and_commit", commit)

    returned = await eda_step.create_eda_step(
        lead_ctx,
        effect_size_threshold=1.0,
        significance_threshold=0.05,
    )
    step = applied[0][0].step
    assert step.search_name == "GenesByEdaVizWithCompute"
    spec = json.loads(step.parameters["eda_analysis_spec"].value)
    viz = spec["descriptor"]["computations"][0]["visualizations"][0]["descriptor"]
    assert viz["configuration"]["effectSizeThreshold"] == 1.0
    assert viz["configuration"]["significanceThreshold"] == 0.05
    assert returned.return_value.search_name == "GenesByEdaVizWithCompute"


async def test_the_thresholds_are_written_into_the_analysis_not_into_a_parameter(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    """The thresholds a user drags ARE the search parameters; they ride in the JSON."""
    from pathfinder.ai.tools.standalone import eda_step

    applied: list[object] = []

    async def commit(*, deps: object, ops: list[object]) -> object:
        applied.append(ops)
        return _commit_result()

    monkeypatch.setattr(eda_step, "bound_analysis", _bound)
    monkeypatch.setattr(eda_step, "read_analysis", _read_detail_with_computation)
    monkeypatch.setattr(eda_step, "apply_operations_and_commit", commit)

    await eda_step.create_eda_step(
        lead_ctx, effect_size_threshold=2.0, significance_threshold=0.01
    )
    step = applied[0][0].step
    assert set(step.parameters) == {"eda_dataset_id", "eda_analysis_spec"}


async def test_a_compute_export_without_thresholds_raises_a_model_retry(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    """The plugin throws unless the volcano carries both thresholds."""
    from pathfinder.ai.tools.standalone import eda_step

    monkeypatch.setattr(eda_step, "bound_analysis", _bound)
    monkeypatch.setattr(eda_step, "read_analysis", _read_detail_with_computation)
    with pytest.raises(ModelRetry) as excinfo:
        await eda_step.create_eda_step(lead_ctx, effect_size_threshold=1.0)
    message = str(excinfo.value)
    assert "significanceThreshold" in message


async def test_a_step_with_no_open_analysis_raises_a_model_retry(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    from pathfinder.ai.tools.standalone import eda_step

    monkeypatch.setattr(eda_step, "bound_analysis", _unbound)
    with pytest.raises(ModelRetry) as excinfo:
        await eda_step.create_eda_step(lead_ctx)
    assert "open_eda_analysis" in str(excinfo.value)


async def test_the_step_emits_the_parts_the_workbench_already_listens_to(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    from pathfinder.ai.tools.standalone import eda_step

    async def commit(*, deps: object, ops: list[object]) -> object:
        return _commit_result()

    monkeypatch.setattr(eda_step, "bound_analysis", _bound)
    monkeypatch.setattr(eda_step, "read_analysis", _read_detail)
    monkeypatch.setattr(eda_step, "apply_operations_and_commit", commit)

    returned = await eda_step.create_eda_step(lead_ctx)
    kinds = [c.type for c in returned.metadata]
    assert "data-graph-snapshot" in kinds


async def test_attaching_into_a_slot_builds_the_slot_attach_point(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    from pathfinder.ai.tools.standalone import eda_step

    applied: list[object] = []

    async def commit(*, deps: object, ops: list[object]) -> object:
        applied.append(ops)
        return _commit_result()

    monkeypatch.setattr(eda_step, "bound_analysis", _bound)
    monkeypatch.setattr(eda_step, "read_analysis", _read_detail)
    monkeypatch.setattr(eda_step, "apply_operations_and_commit", commit)

    await eda_step.create_eda_step(
        lead_ctx, attach_to_step_id="s1", slot="secondary"
    )
    attach = applied[0][0].attach
    assert attach.mode == "into-slot"
    assert attach.target_step_id == "s1"
    assert attach.slot == "secondary"


async def test_a_slot_without_a_target_step_raises_a_model_retry(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    from pathfinder.ai.tools.standalone import eda_step

    monkeypatch.setattr(eda_step, "bound_analysis", _bound)
    monkeypatch.setattr(eda_step, "read_analysis", _read_detail)
    with pytest.raises(ModelRetry):
        await eda_step.create_eda_step(lead_ctx, slot="secondary")
```

- [ ] **Implementation.** Create
      `apps/api/src/pathfinder/ai/tools/standalone/eda_step.py`. The docstring:

```python
async def create_eda_step(
    ctx: RunContext[LeadDeps],
    *,
    search_name: str | None = None,
    attach_to_step_id: str | None = None,
    slot: Literal["primary", "secondary"] | None = None,
    effect_size_threshold: float | None = None,
    significance_threshold: float | None = None,
    effect_direction: Literal["upOnly", "downOnly", "upAndDown"] = "upAndDown",
) -> ToolReturn[EdaStepCreated]:
    """Export the open EDA analysis into the researcher's strategy as a step.

    The step is an ordinary WDK step from then on: it combines, transforms,
    nests and saves like any other, and it appears in the strategy graph the
    researcher is looking at.

    Two exports, and the arguments decide which:

    - The SUBSET's genes: call with no thresholds. Every gene in the filtered
      subset becomes a step.
    - The genes passing a VOLCANO's thresholds: pass
      ``effectSizeThreshold`` AND ``significanceThreshold``. The compute must
      already be complete - call run_eda_compute first and read its summary, so
      you know how many genes you are about to export. ``effectDirection``
      selects the up side, the down side, or both.

    A gene passes when the absolute effect size is at or above
    ``effectSizeThreshold`` and the p-value is at or below
    ``significanceThreshold``. Those are the same comparisons the plot uses, so
    the step's count matches the number you told the researcher.

    Leave ``attachToStepId`` unset to add the step as a new root. Set it, with
    ``slot``, to wire the step into an existing combine.

    Args:
        ctx: Agent run context.
        search_name: A specific EDA-backed search to use. Leave unset to use
            the generic subset or compute search.
        attach_to_step_id: The combine step to wire this into.
        slot: Which input of that combine to fill.
        effect_size_threshold: Minimum absolute effect size to keep.
        significance_threshold: Maximum p-value to keep.
        effect_direction: Which side of the volcano to keep.
    """
```

  The body, in order, with nothing skipped:

  1. `bound_analysis(ctx)` or `ModelRetry` naming `open_eda_analysis`.
  2. `read_analysis(site_id, analysis_id=...)` - the upstream document is the
     SSOT, so the export reads it rather than a local copy.
  3. Decide the export kind. Thresholds present means compute-backed. Refuse a
     half-specified pair with `ModelRetry` naming the missing one, because
     `findVolcanoComputation` requires both keys.
  4. Compute-backed: the analysis must carry a computation. When it does not,
     `ModelRetry` naming `run_eda_compute`. Rebuild the computation's
     visualization with the requested thresholds and direction, through
     `EdaVolcanoConfiguration`, and keep everything else the upstream document
     already holds.
  5. `serialize_spec(...)` - the ONE call. Batch 2's grep test enforces that.
  6. `EdaStepRequest(eda_dataset_id=..., eda_analysis_spec=...)` - its
     `@model_validator` is what refuses a mismatch, and `wdk_parameters()` is
     what produces the two strings.
  7. Build the step: `StrategyStepNode(search_name=..., parameters={...})`
     where each value is the `ParamValue` shape leaf parameters take. Read
     `pathfinder/domain/parameters/values.py` and use the single-value member;
     do not pass a bare string where a `ParamValue` belongs.
  8. `AddLeafOp(step=node, attach=AttachNewRoot())` or
     `AttachIntoSlot(target_step_id=..., slot=...)`. Refuse a `slot` with no
     `attach_to_step_id` with `ModelRetry`.
  9. `apply_operations_and_commit(deps=ctx.deps.runtime...to_strategy_context(),
     ops=[op])` - the EXISTING service. Do not write a second commit path.
     `LeadDeps` does not carry `to_strategy_context()`; find how
     `ai/lead/sub_agent_dispatch.py` builds an `AgentDeps` from `LeadDeps` and
     reuse that, or build a `StrategyMutationContext` directly from
     `ctx.deps.runtime` - it needs `site_id`, `strategy_session`,
     `conversation_id` and `db_session_factory`, and `Context` carries the first
     two and the fourth. Read both files before choosing.
  10. Return a `ToolReturn` whose `metadata` is
      `[graph_snapshot_chunk(session, graph)]` plus a `strategy_link_chunk` when
      the commit produced a WDK URL - the same two chunks `build_strategy` emits,
      so the workbench re-renders with no new frontend code.

  `eda_search_name(*, is_compute_backed: bool)` returns
  `"GenesByEdaVizWithCompute"` or `"GenesByEdaSubset"`. It is a named function
  with its own test so the mapping is stated once.

- [ ] **Gates**, with
      `src/pathfinder/tests/integration/eda/test_create_eda_step.py` and the
      strategy suites the commit path touches:
      `src/pathfinder/tests/unit/strategies/ src/pathfinder/tests/integration/strategies/`.

- [ ] **Section end.** Run the section-end ladder plus the alembic round trip.

---

## Implementer C: the durable compute and its worker impl

### Files

| Action | Path |
|---|---|
| Modify | `apps/api/src/pathfinder/ai/tools/durable.py` (narrow the deps requirement) |
| Modify | `apps/api/src/pathfinder/ai/lead/sub_agent_tools.py` (two properties on `LeadDeps`) |
| Create | `apps/api/src/pathfinder/ai/tools/standalone/eda_compute.py` |
| Create | `apps/api/src/pathfinder/jobs/impls/eda_compute_impl.py` |
| Modify | `apps/api/src/pathfinder/jobs/impls/__init__.py` (`register_tool`) |
| Create | `apps/api/src/pathfinder/tests/unit/ai/tools/test_durable_identity.py` |
| Create | `apps/api/src/pathfinder/tests/unit/ai/tools/eda/test_run_eda_compute.py` |
| Create | `apps/api/src/pathfinder/tests/integration/jobs/test_eda_compute_impl.py` |
| Create | `apps/api/src/pathfinder/tests/integration/jobs/test_eda_compute_resume.py` |

### Interfaces

**Consumes:** `pathfinder.services.eda.compute` (all of it),
`pathfinder.services.eda.authoring.apply_computation`,
`pathfinder.services.eda.binding.bound_conversation_analysis`,
`pathfinder.services.eda.catalog.resolve_dataset`,
`pathfinder.jobs.progress.TaskProgressEmitter`,
`pathfinder.jobs.registry.register_tool`,
`pathfinder.ai.graph.runtime.Context`.

**Produces:**

```python
# ai/tools/durable.py
class DurableIdentity(Protocol):
    @property
    def conversation_id(self) -> UUID | None: ...
    @property
    def user_id(self) -> UUID | None: ...
# durable_tool's first positional argument is now RunContext[DurableIdentity]

# ai/lead/sub_agent_tools.py - LeadDeps gains
    @property
    def conversation_id(self) -> UUID | None
    @property
    def user_id(self) -> UUID | None

# ai/tools/standalone/eda_compute.py
@durable_tool(tool_name="run_eda_compute", estimated_duration_seconds=120)
async def run_eda_compute(ctx, *, identifier_variable: EdaVariableSpecIn,
                          value_variable: EdaVariableSpecIn,
                          comparator_variable: EdaVariableSpecIn,
                          group_a_labels: list[str],
                          group_b_labels: list[str],
                          method: Literal["DESeq", "limma"] = "DESeq",
                          ) -> dict[str, Any]

# jobs/impls/eda_compute_impl.py
async def run_eda_compute_impl(*, context: Context, task_id: UUID,
                               progress: TaskProgressEmitter,
                               memory_store: MemoryStore | None,
                               **kwargs) -> dict[str, Any]
```

---

### Task C1 - narrow `durable_tool` to an identity

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/ai/tools/test_durable_identity.py`:

```python
"""durable_tool needs an identity, not the whole of AgentDeps."""

from __future__ import annotations

from uuid import uuid4

import pytest

from pathfinder.ai.lead.sub_agent_tools import LeadDeps

pytestmark = pytest.mark.asyncio


def test_lead_deps_exposes_the_conversation_and_the_user(lead_deps: LeadDeps) -> None:
    assert lead_deps.conversation_id is not None
    assert lead_deps.user_id is not None


def test_lead_deps_conversation_id_comes_from_the_turn_state(
    lead_deps: LeadDeps,
) -> None:
    assert lead_deps.conversation_id == lead_deps.state.conversation_id


def test_lead_deps_user_id_comes_from_the_turn_context(lead_deps: LeadDeps) -> None:
    assert lead_deps.user_id == lead_deps.runtime.user_id


def test_lead_deps_satisfies_the_durable_identity_protocol(
    lead_deps: LeadDeps,
) -> None:
    from pathfinder.ai.tools.durable import DurableIdentity

    identity: DurableIdentity = lead_deps
    assert identity.conversation_id is not None


def test_agent_deps_still_satisfies_the_durable_identity_protocol() -> None:
    from pathfinder.ai.graph.runtime import AgentDeps
    from pathfinder.ai.tools.durable import DurableIdentity

    deps = AgentDeps(
        site_id="plasmodb",
        user_id=uuid4(),
        conversation_id=uuid4(),
        strategy_session=object(),
    )
    identity: DurableIdentity = deps
    assert identity.user_id is not None
```

  The two explicit annotations are the assertion. A structural mismatch is a
  `mypy --strict` failure, which is why this test must be in the mypy path.

  `lead_deps` is a fixture; build it from the real `PipelineState` and `Context`
  the existing Lead tests use. Find one in
  `apps/api/src/pathfinder/tests/unit/ai/lead/` and reuse its construction.

- [ ] **Run it.** Expect
      `AttributeError: 'LeadDeps' object has no attribute 'conversation_id'`.

- [ ] **Implementation.** In `ai/lead/sub_agent_tools.py`, add two properties to
      `LeadDeps`:

```python
    @property
    def conversation_id(self) -> UUID | None:
        """The thread this turn belongs to, as the turn state holds it."""
        return self.state.conversation_id

    @property
    def user_id(self) -> UUID | None:
        """The account this turn acts as."""
        return self.runtime.user_id
```

  In `ai/tools/durable.py`, replace the `AgentDeps` requirement with the
  Protocol:

```python
class DurableIdentity(Protocol):
    """What a durable dispatch needs from an agent's deps."""

    @property
    def conversation_id(self) -> UUID | None: ...
    @property
    def user_id(self) -> UUID | None: ...
```

  and change `_parse_invocation`'s return type and `_require_durable_deps`'s
  argument to `DurableIdentity`. The messages keep their text minus the
  `AgentDeps` name:
  `"durable_tool requires conversation_id on the agent's deps"`.
  Update `apps/api/src/pathfinder/tests/unit/ai/tools/test_durable_decorator.py`
  and `tests/unit/jobs/test_durable_decorator_auth.py` in the same task - they
  assert on those two message strings.

- [ ] **Gates**, with
      `src/pathfinder/tests/unit/ai/tools/ src/pathfinder/tests/unit/jobs/`.

**Trap named:** `AgentDeps` is a Pydantic `BaseModel` with `conversation_id` and
`user_id` as FIELDS, and `LeadDeps` gets them as PROPERTIES. A `Protocol` with
`@property` members is satisfied by both, because a field read is a property
read. A `Protocol` with plain attribute annotations is not satisfied by a
read-only property under pyright. Declare them as properties.

---

### Task C2 - `run_eda_compute` as a durable tool

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/unit/ai/tools/eda/test_run_eda_compute.py`:

```python
"""run_eda_compute defers the work and suspends the graph."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from langgraph.errors import GraphInterrupt

pytestmark = pytest.mark.asyncio


async def test_calling_the_tool_creates_a_task_and_defers_a_job(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    from pathfinder.ai.tools import durable
    from pathfinder.ai.tools.standalone import eda_compute

    task_id = uuid4()
    created: list[str] = []
    deferred: list[dict[str, Any]] = []

    async def create(**kwargs: Any) -> Any:
        created.append(str(kwargs["tool_name"]))
        return task_id

    class _Task:
        async def defer_async(self, **payload: Any) -> None:
            deferred.append(payload)

    monkeypatch.setattr(durable, "create_background_task", create)
    monkeypatch.setattr(
        durable.procrastinate_app, "configure_task", lambda **_k: _Task()
    )

    with pytest.raises(GraphInterrupt):
        await eda_compute.run_eda_compute(
            lead_ctx,
            identifier_variable={
                "entityId": "ENT_fd574cd6",
                "variableId": "VEUPATHDB_GENE_ID",
            },
            value_variable={
                "entityId": "ENT_fd574cd6",
                "variableId": "SEQUENCE_READ_COUNT_SENSE",
            },
            comparator_variable={
                "entityId": "ENT_8151325d",
                "variableId": "VAR_081ab087",
            },
            group_a_labels=["normal"],
            group_b_labels=["febrile"],
        )

    assert created == ["run_eda_compute"]
    assert deferred


async def test_the_deferred_job_carries_the_arguments_the_impl_needs(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    from pathfinder.ai.tools import durable
    from pathfinder.ai.tools.standalone import eda_compute

    captured: list[dict[str, Any]] = []

    async def create(**kwargs: Any) -> Any:
        captured.append(dict(kwargs))
        return uuid4()

    class _Task:
        async def defer_async(self, **_payload: Any) -> None:
            return None

    monkeypatch.setattr(durable, "create_background_task", create)
    monkeypatch.setattr(
        durable.procrastinate_app, "configure_task", lambda **_k: _Task()
    )

    with pytest.raises(GraphInterrupt):
        await eda_compute.run_eda_compute(
            lead_ctx,
            identifier_variable={
                "entityId": "E",
                "variableId": "VEUPATHDB_GENE_ID",
            },
            value_variable={"entityId": "E", "variableId": "SEQUENCE_READ_COUNT"},
            comparator_variable={"entityId": "P", "variableId": "C"},
            group_a_labels=["a"],
            group_b_labels=["b"],
            method="limma",
        )

    kwargs = captured[0]["args"]["kwargs"]
    assert kwargs["method"] == "limma"
    assert kwargs["group_a_labels"] == ["a"]
    assert kwargs["identifier_variable"]["variableId"] == "VEUPATHDB_GENE_ID"


async def test_the_estimated_duration_is_declared(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: object
) -> None:
    from pathfinder.ai.tools import durable
    from pathfinder.ai.tools.standalone import eda_compute

    captured: list[dict[str, Any]] = []

    async def create(**kwargs: Any) -> Any:
        captured.append(dict(kwargs))
        return uuid4()

    class _Task:
        async def defer_async(self, **_payload: Any) -> None:
            return None

    monkeypatch.setattr(durable, "create_background_task", create)
    monkeypatch.setattr(
        durable.procrastinate_app, "configure_task", lambda **_k: _Task()
    )

    with pytest.raises(GraphInterrupt):
        await eda_compute.run_eda_compute(
            lead_ctx,
            identifier_variable={"entityId": "E", "variableId": "VEUPATHDB_GENE_ID"},
            value_variable={"entityId": "E", "variableId": "SEQUENCE_READ_COUNT"},
            comparator_variable={"entityId": "P", "variableId": "C"},
            group_a_labels=["a"],
            group_b_labels=["b"],
        )
    assert captured[0]["estimated_duration_seconds"] == 120


async def test_the_tool_is_registered_in_the_worker_registry() -> None:
    from pathfinder.jobs.impls import register_all_tools
    from pathfinder.jobs.registry import TOOL_REGISTRY

    register_all_tools()
    assert "run_eda_compute" in TOOL_REGISTRY
```

  `GraphInterrupt` is what `langgraph.types.interrupt` raises outside a running
  graph. Confirm the class name and module by reading
  `apps/api/.venv/lib/python3.14/site-packages/langgraph/errors.py`, and check
  how `tests/unit/ai/tools/test_durable_decorator.py` already asserts on the
  interrupt - copy that, do not invent it.

- [ ] **Implementation.** Create
      `apps/api/src/pathfinder/ai/tools/standalone/eda_compute.py`:

```python
"""The durable differential-expression compute."""

from __future__ import annotations

from typing import Any, Literal

from assistant_core.platform.pydantic_base import CamelModel
from pydantic_ai import RunContext

from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.ai.tools.durable import durable_tool

_ESTIMATED_SECONDS = 120


class EdaVariableSpecIn(CamelModel):
    """One (entity, variable) pair, as the model writes it."""

    entity_id: str
    variable_id: str


@durable_tool(
    tool_name="run_eda_compute",
    estimated_duration_seconds=_ESTIMATED_SECONDS,
)
async def run_eda_compute(
    ctx: RunContext[LeadDeps],
    *,
    identifier_variable: EdaVariableSpecIn,
    value_variable: EdaVariableSpecIn,
    comparator_variable: EdaVariableSpecIn,
    group_a_labels: list[str],
    group_b_labels: list[str],
    method: Literal["DESeq", "limma"] = "DESeq",
) -> dict[str, Any]:
    """Run differential expression on the open EDA analysis, on the worker.

    This compares two groups of samples and reports, per gene, an effect size
    and a p-value. It runs in the background: the turn ends cleanly, the
    researcher sees progress, and you are called again with the result when it
    finishes. That can take a minute or several.

    Use it when the question is a comparison - "up in febrile samples",
    "different between the mutant and the wild type", "responds to heat shock".

    Choosing the arguments, and describe_eda_study gives you all of them:

    - ``identifierVariable`` is the gene column, and it is the reserved
      variable ``VEUPATHDB_GENE_ID``.
    - ``valueVariable`` is the measurement column on the SAME entity. It is one
      of the reserved ids ``SEQUENCE_READ_COUNT``,
      ``SEQUENCE_READ_COUNT_SENSE``, ``SEQUENCE_READ_COUNT_ANTISENSE``,
      ``NORMALIZED_EXPRESSION`` or ``NORMALIZED_INTENSITY``.
    - ``comparatorVariable`` is the sample-level variable that separates the
      two groups, and it lives on an ANCESTOR entity of the expression data.
    - ``groupALabels`` is the reference group and ``groupBLabels`` is the
      comparison group. Every label must be a value in the comparator
      variable's vocabulary, and no label may be in both groups.
    - ``method`` is ``DESeq`` for raw counts and ``limma`` for normalized array
      data. ``DESeq2`` is not a value.

    The result carries the job's identity, the number of genes tested, and how
    many pass the default thresholds of effect size 1 and p-value 0.05, split
    into up and down. Tell the researcher those numbers, then use
    create_eda_step to export the ones that pass.

    Args:
        ctx: Agent run context.
        identifier_variable: The gene column.
        value_variable: The measurement column, on the same entity.
        comparator_variable: The sample variable separating the groups.
        group_a_labels: The reference group's vocabulary values.
        group_b_labels: The comparison group's vocabulary values.
        method: DESeq for counts, limma for normalized arrays.
    """
    del (
        ctx,
        identifier_variable,
        value_variable,
        comparator_variable,
        group_a_labels,
        group_b_labels,
        method,
    )
    msg = "run_eda_compute runs on the worker via @durable_tool"
    raise NotImplementedError(msg)
```

  The body is a `NotImplementedError`, exactly as
  `ai/tools/standalone/experiment.py::run_control_tests_on_step` is: the
  decorator never calls it. Do not put logic there.

- [ ] **Gates**, with
      `src/pathfinder/tests/unit/ai/tools/eda/test_run_eda_compute.py`.

---

### Task C3 - `jobs/impls/eda_compute_impl.py`

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/integration/jobs/test_eda_compute_impl.py`:

```python
"""The worker impl drives the six-state job and reports progress."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest

from pathfinder.integrations.eda.client import EdaClient
from pathfinder.jobs.impls.eda_compute_impl import run_eda_compute_impl

FIXTURES = (
    Path(__file__).resolve().parents[2]
    / "unit"
    / "integrations"
    / "eda"
    / "fixtures"
)

pytestmark = pytest.mark.asyncio

_ARGS: dict[str, Any] = {
    "identifier_variable": {
        "entityId": "ENT_fd574cd6",
        "variableId": "VEUPATHDB_GENE_ID",
    },
    "value_variable": {
        "entityId": "ENT_fd574cd6",
        "variableId": "SEQUENCE_READ_COUNT_SENSE",
    },
    "comparator_variable": {
        "entityId": "ENT_8151325d",
        "variableId": "VAR_081ab087",
    },
    "group_a_labels": ["normal"],
    "group_b_labels": ["febrile"],
    "method": "DESeq",
}


class _Progress:
    def __init__(self) -> None:
        self.updates: list[tuple[float, str]] = []

    async def update(
        self,
        *,
        percent: float,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        del data
        self.updates.append((percent, message))


def _statuses(*values: str) -> httpx.MockTransport:
    remaining = list(values)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/permissions"):
            return httpx.Response(
                200, json=json.loads((FIXTURES / "permissions.json").read_text())
            )
        if path.endswith("/statistics"):
            return httpx.Response(
                200,
                json=json.loads(
                    (FIXTURES / "volcano_statistics.json").read_text()
                ),
            )
        status = remaining.pop(0) if remaining else "complete"
        return httpx.Response(200, json={"jobID": "a" * 32, "status": status})

    return httpx.MockTransport(handler)


async def test_the_impl_polls_to_completion_and_returns_a_summary(
    monkeypatch: pytest.MonkeyPatch, worker_context: object
) -> None:
    from pathfinder.jobs.impls import eda_compute_impl

    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(_statuses("queued", "in-progress", "complete"))
    monkeypatch.setattr(eda_compute_impl, "get_eda_client", lambda _s: client)
    monkeypatch.setattr(eda_compute_impl, "_POLL_SECONDS", 0.0)
    monkeypatch.setattr(eda_compute_impl, "bound_analysis_for_worker", _bound)

    progress = _Progress()
    result = await run_eda_compute_impl(
        context=worker_context,
        task_id=uuid4(),
        progress=progress,
        memory_store=None,
        **_ARGS,
    )
    await client.close()

    assert result["status"] == "complete"
    assert result["jobId"] == "a" * 32
    assert result["genesTested"] > 0
    assert result["retained"] == result["retainedUp"] + result["retainedDown"]
    assert result["effectSizeThreshold"] == 1.0
    assert result["significanceThreshold"] == 0.05


async def test_progress_reports_queued_then_running_then_complete(
    monkeypatch: pytest.MonkeyPatch, worker_context: object
) -> None:
    from pathfinder.jobs.impls import eda_compute_impl

    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(_statuses("queued", "in-progress", "complete"))
    monkeypatch.setattr(eda_compute_impl, "get_eda_client", lambda _s: client)
    monkeypatch.setattr(eda_compute_impl, "_POLL_SECONDS", 0.0)
    monkeypatch.setattr(eda_compute_impl, "bound_analysis_for_worker", _bound)

    progress = _Progress()
    await run_eda_compute_impl(
        context=worker_context,
        task_id=uuid4(),
        progress=progress,
        memory_store=None,
        **_ARGS,
    )
    await client.close()

    percents = [p for p, _m in progress.updates]
    assert percents == sorted(percents)
    assert percents[0] == 0.0
    assert percents[-1] == 1.0
    messages = " ".join(m for _p, m in progress.updates)
    assert "queue" in messages.lower()
    assert "complete" in messages.lower()


async def test_a_failed_job_raises_with_the_status_named(
    monkeypatch: pytest.MonkeyPatch, worker_context: object
) -> None:
    from pathfinder.jobs.impls import eda_compute_impl

    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(_statuses("queued", "failed"))
    monkeypatch.setattr(eda_compute_impl, "get_eda_client", lambda _s: client)
    monkeypatch.setattr(eda_compute_impl, "_POLL_SECONDS", 0.0)
    monkeypatch.setattr(eda_compute_impl, "bound_analysis_for_worker", _bound)

    with pytest.raises(RuntimeError) as excinfo:
        await run_eda_compute_impl(
            context=worker_context,
            task_id=uuid4(),
            progress=_Progress(),
            memory_store=None,
            **_ARGS,
        )
    await client.close()
    assert "failed" in str(excinfo.value)


async def test_a_config_the_predicates_reject_never_reaches_the_wire(
    monkeypatch: pytest.MonkeyPatch, worker_context: object
) -> None:
    """An out-of-vocabulary group label is accepted at submit and fails later."""
    from pathfinder.jobs.impls import eda_compute_impl

    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/permissions"):
            return httpx.Response(
                200, json=json.loads((FIXTURES / "permissions.json").read_text())
            )
        if request.url.path.startswith("/eda/studies/"):
            return httpx.Response(
                200,
                json=json.loads((FIXTURES / "study_detail_de.json").read_text()),
            )
        return httpx.Response(200, json={"jobID": "a" * 32, "status": "complete"})

    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(httpx.MockTransport(handler))
    monkeypatch.setattr(eda_compute_impl, "get_eda_client", lambda _s: client)
    monkeypatch.setattr(eda_compute_impl, "bound_analysis_for_worker", _bound_de)

    bad = dict(_ARGS)
    bad["group_a_labels"] = ["NOT_A_VALUE"]
    with pytest.raises(ValueError) as excinfo:
        await run_eda_compute_impl(
            context=worker_context,
            task_id=uuid4(),
            progress=_Progress(),
            memory_store=None,
            **bad,
        )
    await client.close()
    assert "NOT_A_VALUE" in str(excinfo.value)
    assert not any(p.endswith("/computes/differentialexpression") for p in calls)


async def test_a_cached_job_completes_without_a_poll(
    monkeypatch: pytest.MonkeyPatch, worker_context: object
) -> None:
    """The job id is an input hash, so an identical request is already done."""
    from pathfinder.jobs.impls import eda_compute_impl

    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(_statuses("complete"))
    monkeypatch.setattr(eda_compute_impl, "get_eda_client", lambda _s: client)
    monkeypatch.setattr(eda_compute_impl, "_POLL_SECONDS", 0.0)
    monkeypatch.setattr(eda_compute_impl, "bound_analysis_for_worker", _bound)

    progress = _Progress()
    result = await run_eda_compute_impl(
        context=worker_context,
        task_id=uuid4(),
        progress=progress,
        memory_store=None,
        **_ARGS,
    )
    await client.close()
    assert result["status"] == "complete"
    assert len(progress.updates) <= 3
```

  `worker_context` is a `Context` for the worker; build it the way
  `apps/api/src/pathfinder/tests/integration/jobs/` already does for the other
  impls, and read one of those files before writing the fixture.
  `bound_analysis_for_worker` and `_bound`/`_bound_de` return the
  `(site_id, dataset_id, analysis_id)` triple the impl needs; the impl reads it
  from `conversation_analyses` in production, so it must be a module-level name
  a test can replace.

- [ ] **Implementation.** Create
      `apps/api/src/pathfinder/jobs/impls/eda_compute_impl.py`:

```python
"""Worker-side impl for ``run_eda_compute``.

The impl drives the compute to a terminal state and returns its statistics
summary. It creates no step: a worker context has no strategy session, and the
agent creates the step after the resume, when the job's cache is warm.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from assistant_core.memory.store import MemoryStore

from pathfinder.ai.graph.runtime import Context
from pathfinder.integrations.eda.factory import get_eda_client
from pathfinder.jobs.progress import TaskProgressEmitter
from pathfinder.services.eda.binding import bound_analysis_for_worker
from pathfinder.services.eda.catalog import get_study_detail_for_dataset
from pathfinder.services.eda.compute import (
    RUNNING_STATUSES,
    lookup_job,
    read_statistics,
    retained_summary,
    submit_job,
)

_COMPUTE_NAME = "differentialexpression"
_POLL_SECONDS = 3.0
_MAX_POLLS = 200

# The thresholds the review card defaults to upstream.
_DEFAULT_EFFECT_SIZE = 1.0
_DEFAULT_SIGNIFICANCE = 0.05

# A queued job has no position most of the time, so the percent is a floor
# rather than a measurement: the poll count moves it, never past the ceiling.
_QUEUED_PERCENT = 0.1
_RUNNING_CEILING = 0.85


async def run_eda_compute_impl(
    *,
    context: Context,
    task_id: UUID,
    progress: TaskProgressEmitter,
    memory_store: MemoryStore | None,
    identifier_variable: dict[str, str],
    value_variable: dict[str, str],
    comparator_variable: dict[str, str],
    group_a_labels: list[str],
    group_b_labels: list[str],
    method: str = "DESeq",
    **_extra: Any,
) -> dict[str, Any]:
    """Drive one differential-expression job and summarise its statistics."""
    del task_id, memory_store
    binding = await bound_analysis_for_worker(
        conversation_id=context.conversation_id
    )
    ...
```

  The body, in order, and every step is required:

  1. `bound_analysis_for_worker` gives the site, dataset and analysis. When
     there is none, raise `ValueError` naming `open_eda_analysis` - the runner
     turns an exception into a `failed` task and a message on the thread.
  2. Build the `EdaDifferentialExpressionConfig` from the six arguments through
     the real models, so a bad `method` is a `ValidationError` here.
  3. `get_study_detail_for_dataset`, then
     `domain.eda.validate_compute_config`. Raise `ValueError` with the joined
     errors when it rejects. This is the check the service does not do: an
     out-of-vocabulary label and a cross-entity pairing are both accepted at
     submit and produce a `failed` job minutes later.
  4. `progress.update(percent=0.0, message="Checking for a cached result", ...)`
     then `lookup_job(...)`. A `complete` status skips straight to step 7.
  5. `submit_job(...)` with `autostart=True`.
  6. Poll: while the status is in `RUNNING_STATUSES` and the poll count is
     under `_MAX_POLLS`, `asyncio.sleep(_POLL_SECONDS)` then
     `poll_job(...)`. Report progress each time: `_QUEUED_PERCENT` while
     `queued` (naming the `queuePosition` when the response carries one), and a
     value rising from `_QUEUED_PERCENT` toward `_RUNNING_CEILING` while
     `in-progress`, computed as
     `_QUEUED_PERCENT + (_RUNNING_CEILING - _QUEUED_PERCENT) * polls / _MAX_POLLS`.
     A percent that reaches 1.0 before the job does is a lie the researcher
     watches.
  7. A status other than `complete` raises `RuntimeError` naming it and what it
     means: `failed` is a bad configuration, `expired` needs a resubmit,
     `no-such-job` means the inputs changed.
  8. `progress.update(percent=0.9, message="Reading the statistics", ...)` then
     `read_statistics(...)`.
  9. `retained_summary(...)` at the default thresholds.
  10. `progress.update(percent=1.0, message="Compute complete", ...)`.
  11. Return the dict below. Keys are camelCase because the resumed value
      reaches the model as JSON, and the runner's `_to_dict` does not rename
      anything:

```python
    return {
        "jobId": job.job_id,
        "status": job.status,
        "computeName": _COMPUTE_NAME,
        "method": method,
        "effectSizeLabel": statistics.effect_size_label,
        "genesTested": summary.total_rows,
        "genesUnreadable": summary.unparseable_rows,
        "effectSizeThreshold": _DEFAULT_EFFECT_SIZE,
        "significanceThreshold": _DEFAULT_SIGNIFICANCE,
        "retained": summary.retained,
        "retainedUp": summary.retained_up,
        "retainedDown": summary.retained_down,
        "guidance": (
            f"{summary.retained} of {summary.total_rows} genes pass an effect "
            f"size of {_DEFAULT_EFFECT_SIZE} and a p-value of "
            f"{_DEFAULT_SIGNIFICANCE}: {summary.retained_up} up and "
            f"{summary.retained_down} down. Call create_eda_step with those "
            f"thresholds to export them, or with different ones to change the "
            f"cut."
        ),
    }
```

- [ ] **Register the impl.** In `jobs/impls/__init__.py`, import
      `run_eda_compute_impl` and add
      `register_tool("run_eda_compute", run_eda_compute_impl)` to
      `register_all_tools()`, keeping the existing order.

- [ ] **Add `bound_analysis_for_worker`.** It belongs in
      `services/eda/binding.py` beside the other three, and it returns the same
      `ConversationAnalysisView | None`. The worker's `Context` carries
      `conversation_id`; confirm that by reading
      `jobs/runtime.py::build_worker_runtime_context` before writing the call.

- [ ] **Gates**, with
      `src/pathfinder/tests/integration/jobs/test_eda_compute_impl.py` and
      `src/pathfinder/tests/unit/jobs/`.

---

### Task C4 - the resume flow, end to end

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/integration/jobs/test_eda_compute_resume.py`.
      Copy the structure of the existing durable-resume test - find it with
      `grep -rln "Command(resume" apps/api/src/pathfinder/tests` - so the graph,
      the checkpointer and the event writer are the real ones and only the LLM
      and the EDA wire are doubles.

```python
"""The graph suspends on run_eda_compute and resumes with the summary."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_the_turn_ends_with_a_background_task_started_part(...) -> None:
    """The dispatcher's clean end: the tab closes and the work continues."""


async def test_the_resumed_turn_carries_the_compute_summary_into_the_prose(...) -> None:
    """The scripted model is given the resumed dict and must quote its numbers."""


async def test_the_resumed_chunks_land_in_conversation_events(...) -> None:
    """A reconnecting client replays the same rows the resume wrote."""


async def test_a_failed_job_appends_a_task_completed_event_with_the_error(...) -> None:
```

  Each test's assertions:

  1. Drive one turn with `PATHFINDER_CHAT_PROVIDER=mock` and a scripted model
     that calls `run_eda_compute` once. Assert the persisted
     `conversation_events` rows include a `data-background-task-started` chunk
     and that the turn ended without an error part.
  2. Run the worker path by calling `jobs/runner.py::run_durable_task` directly
     with the task id, the thread id and the arguments, with the EDA transport
     doubled. Assert the resumed turn's final text part quotes the retained
     count the impl returned. The scripted model's second script step must read
     the tool return and emit it; that is what proves the value reached the
     model rather than only the database.
  3. Assert the resumed chunks are rows in `conversation_events` for the same
     conversation, after the `task_completed` row.
  4. With the transport answering `failed`, assert a `task_completed` event with
     `status: "failed"` and the status named in its error.

  Read `apps/api/src/pathfinder/tests/integration/jobs/test_task_progress_on_thread.py`
  first: it already builds the conversation, the task row and the runner call,
  and copying its fixtures is the difference between a test that runs and a test
  that hangs.

- [ ] **Rebuild and verify the worker updated**, then run the whole jobs suite:

  ```bash
  docker compose --env-file .env.dev up -d --build api worker web
  docker compose exec worker grep -c "run_eda_compute" \
    /app/src/pathfinder/jobs/impls/__init__.py
  cd apps/api && uv run pytest src/pathfinder/tests/integration/jobs/ -v
  ```

- [ ] **Section end.** Run the section-end ladder plus the `assistant-core` half.

---

## Verifier 1 - covers implementers A and B

### Re-run

```bash
cd apps/api
uv run ruff check src/
uv run mypy --strict src/pathfinder/
uv run pyright src/pathfinder/
uv run lint-imports
uv run pytest src/pathfinder/tests/unit/ -v
uv run pytest src/pathfinder/tests/integration/ -v
uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head
cd ../../packages/shared-py && uv run ruff check src/ && uv run mypy --strict src/
cd ../assistant-core && uv run pytest && uv run mypy --strict src/
```

### Traps to hunt, by name

1. **Reject any EDA name inside `packages/assistant-core/`.**
   `grep -rniE "study|entity|variable|filter|compute|VEUPATHDB_GENE_ID|eda" packages/assistant-core/src`
   must return only the pre-existing generic uses (`stream_parts` registry
   docstrings, `embeddings`), and no new line. The `assistant-core` boundary
   test must pass.
2. **Reject a stream-part payload model outside `shared_py`.** A payload in
   `pathfinder/` never reaches the generated TypeScript.
3. **Reject a registration that replaces the strategy hook instead of composing
   it.** `_register_product_stream_parts` must call both, and
   `test_pathfinder_spec.py` must assert both sets of kinds.
4. **Reject a tool that imports `pathfinder.integrations`.**
   `uv run lint-imports` catches it; also
   `grep -rn "integrations" apps/api/src/pathfinder/ai/tools/standalone/eda_*.py`.
5. **Reject a `services/eda/__init__.py` re-export of anything that is not a
   type in a `services/eda` public signature.** Read the list against the
   signatures.
6. **Reject a `set_eda_filters` that records something on the sheet call.** The
   first call must return a plain result with no `ToolReturn` and no chunk.
7. **Reject a `set_eda_filters` where `filters=None` and `filters=[]` behave the
   same.** One asks for the sheet; the other clears the subset.
8. **Reject a second sheet that resends the vocabularies.** The prompt cache is
   what pays for it.
9. **Reject a sheet entry with no example filter object.**
10. **Reject a `ModelRetry` message that does not name the offending value and
    the valid ones.** A retry the model cannot act on is a wasted turn.
11. **Reject a `preview_eda_subset` that treats zero as an error, and one that
    does not say a zero subset is a finding.**
12. **Reject a distribution part that does not report `isMultiValued`.** A
    consumer that sums a multi-valued histogram is off by nearly a factor of two.
13. **Reject a viz part whose cap can drop a retained point.** Retained points
    must be ordered first before the slice.
14. **Reject a `conversation_analyses` row that stores the descriptor.** The
    column set is exactly the five names.
15. **Reject a second row per conversation.** The primary key is
    `conversation_id` alone, and `bind` upserts.
16. **Reject a migration whose `down_revision` is not the real head**, and one
    whose `downgrade` does not drop the index before the table.
17. **Reject a `create_eda_step` that serializes the analysis itself.** Batch
    2's grep test must still pass, and the only `serialize_spec` caller in `ai/`
    is `eda_step.py`.
18. **Reject a `create_eda_step` that writes the thresholds as WDK parameters.**
    They travel inside the analysis JSON. The step's parameter set is exactly
    `{eda_dataset_id, eda_analysis_spec}`.
19. **Reject a compute-backed export whose volcano configuration lacks either
    threshold.** The plugin throws.
20. **Reject a second commit path.** `create_eda_step` must call
    `apply_operations_and_commit`, and must not build its own WDK push.
21. **Reject a `create_eda_step` that does not emit `data-graph-snapshot`.** The
    workbench listens to it, and without it the researcher sees nothing.
22. **Reject any `isinstance` chain, `getattr` with a default, `hasattr`,
    `dict.get` over untyped JSON, `# type: ignore`, `noqa` or `import as`** in
    the new modules. Name the allowed exceptions (a `match` over a discriminated
    union, a `.get` on a model-produced dict, an `isinstance` in a test JSON
    walker) so the lead can check the judgment.
23. **Reject an instruction block with a non-ASCII character.** The test asserts
    `isascii()`; also read the block, because a curly quote inside a code fence
    would pass a naive grep.

### Report format

One block per task (A1 to A7, B1 to B3), each with `evidence:`, `read:` and
`traps checked:` lines. A FAIL names the file, the line and the rule.

---

## Verifier 2 - covers implementer C, plus the end-to-end check

### Re-run

```bash
cd apps/api
uv run ruff check src/
uv run mypy --strict src/pathfinder/
uv run pyright src/pathfinder/
uv run lint-imports
uv run pytest src/pathfinder/tests/unit/ai/tools/ -v
uv run pytest src/pathfinder/tests/unit/jobs/ -v
uv run pytest src/pathfinder/tests/integration/jobs/ -v
uv run pytest src/pathfinder/tests/ -v
```

### Traps to hunt, by name

1. **Reject a `DurableIdentity` whose members are plain annotations rather than
   properties.** `LeadDeps` satisfies it only with `@property`.
2. **Reject a second durable decorator, or a copy of `durable_tool` for the
   Lead.** One decorator, one Protocol.
3. **Reject a `run_eda_compute` body that does anything.** It is a
   `NotImplementedError` stub; the decorator never calls it.
4. **Reject a `run_eda_compute` not registered `sequential=True`.** An interrupt
   escaping `_call_tools` cancels sibling tool returns and orphans them in the
   persisted history.
5. **Reject an impl that creates a step.** A worker context has no
   `StrategySession`. The step is created after the resume, and the input-hash
   cache is what makes that correct rather than merely convenient.
6. **Reject an impl that skips `validate_compute_config`.** An out-of-vocabulary
   group label and a cross-entity pairing are both accepted at submit and fail
   minutes later.
7. **Reject a progress percent that reaches 1.0 before the job is complete.**
8. **Reject a progress sequence that is not monotonic.**
9. **Reject an impl that does not try `lookup_job` first.** The job id is a
   client-derivable input hash, so a cache hit costs one call and no wait.
10. **Reject an impl that retries `submit_job`.** `autostart=true` starts work.
11. **Reject a terminal status other than `complete` being swallowed.**
    `failed`, `expired` and `no-such-job` each mean something different and the
    message must say which.
12. **Reject a resumed dict with snake_case keys.** The runner's `_to_dict` does
    not rename, and the model reads what the impl returned.
13. **Reject a resume test that asserts only on the database.** The proof is
    that the model quoted the number: a scripted second step must read the tool
    return.
14. **Reject a missing `register_tool("run_eda_compute", ...)`.**
15. **Reject any `isinstance` chain, `getattr` with a default, `hasattr`,
    `# type: ignore`, `noqa` or `import as`** in the new modules.

### The end-to-end check - the one thing only this verifier does

Write and run one scripted mock-LLM conversation that goes all the way through,
and assert on the REAL persisted chunks.

- [ ] Create
      `apps/api/src/pathfinder/tests/integration/eda/test_eda_conversation.py`.
      Read `docs/knowledge` reference `reference_mock_llm_architecture` and
      `apps/api/src/pathfinder/ai/models/mock.py` first: the mock is a
      deterministic `FunctionModel` and the script is driven by unique markers
      in the tool arguments.

The conversation, one turn, four tool calls, with the EDA transport doubled by
the recorded fixtures and Postgres real:

```
1. search_eda_studies(query="rodent malaria phenotypes")
   -> asserts the card for DS_53f554ec6a comes back
2. describe_eda_study(dataset_id="DS_53f554ec6a",
                      entity_id="GENE_PHENOTYPE_DATA_ENTITY")
   -> asserts VAR_035294d0 appears with filterType stringSet and its three
      vocabulary values
3. open_eda_analysis(dataset_id="DS_53f554ec6a", purpose="P. berghei rows")
   -> asserts a conversation_analyses row exists for the thread
   -> asserts a data-eda.analysis-state chunk is in conversation_events
4. set_eda_filters(dataset_id="DS_53f554ec6a",
                   filters=[the P. berghei stringSet])
   -> asserts a second data-eda.analysis-state chunk with numFilters 1
5. preview_eda_subset(entity_id="GENE_PHENOTYPE_DATA_ENTITY",
                      distributionVariableId="VAR_035294d0")
   -> asserts a data-eda.subset-preview chunk whose entityCounts[0].count is
      4011 and unfilteredCount is 4279
6. create_eda_step()
   -> asserts a data-graph-snapshot chunk
   -> asserts the created step's searchName is GenesByEdaSubset and its
      eda_analysis_spec parses to a document whose studyId is DS_53f554ec6a
```

- [ ] The assertions read `conversation_events` rows, not the in-memory return
      values. A chunk that a tool built and the writer dropped is exactly the
      failure this test exists to catch.

- [ ] Run it, then run it again with the worker container rebuilt, because chat
      turns run in the worker and a stale container makes this test lie.

### Report format

Same as verifier 1, one block per task C1 to C4, plus one block for the
end-to-end check quoting the four asserted numbers (4011, 4279, 1, and the
search name).

---

## Exit criteria

1. `cd apps/api && uv run ruff check src/ && uv run mypy --strict src/pathfinder/ && uv run pyright src/pathfinder/ && uv run lint-imports && uv run pytest src/pathfinder/tests/ -v` is green, run by the lead.
2. `cd packages/assistant-core && uv run pytest && uv run mypy --strict src/` is
   green, and no new EDA name appears anywhere under
   `packages/assistant-core/src`.
3. `cd packages/shared-py && uv run ruff check src/ && uv run mypy --strict src/`
   is green.
4. The alembic round trip runs: `upgrade head`, `downgrade -1`, `upgrade head`.
5. The three `data-eda.*` kinds are registered, and
   `test_pathfinder_spec.py` asserts both the strategy and the EDA sets.
6. The scripted end-to-end conversation passes and asserts on persisted chunks,
   with the four numbers above.
7. The resume test passes and proves the compute summary reached the model, not
   only the database.
8. Batch 2's `serialize_spec` grep test still passes: one analysis dump in the
   repository.
9. The containers were rebuilt and the worker was verified to hold the new
   prompt and the new registration.
10. Both verifier reports are PASS on every task, with evidence lines, and the
    lead has spot-read `eda_analysis.py`, `eda_step.py`, `eda_compute_impl.py`
    and the instruction block against this document.
11. The recap names the pending `yarn generate:types` for batch 4, and otherwise
    leads with "zero debt" or the batch stays open.
