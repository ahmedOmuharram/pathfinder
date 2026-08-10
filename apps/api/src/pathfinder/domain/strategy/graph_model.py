"""Step data keyed by id, with structure held as id references.

``StrategyStepNode`` nests a whole node inside ``primaryInput`` /
``secondaryInput``. ``StrategyGraph.steps`` then indexes those same objects, so
the flat view and the tree view are the same memory: an in-place edit changes
both, ``apply_and_commit`` needs a defensive deep copy to detect what changed,
and an operation that fails midway leaves the graph half-edited.

WDK's own ``StrategyDetails`` does not conflate them::

    stepTree: StepTree            // nested, carries only stepId
    steps: Record<number, Step>   // the data

Same separation here, with structure carried as ``primary_input_id`` /
``secondary_input_id`` on the step - which is also exactly the shape the
frontend already uses (``Step.primaryInputStepId``), so both sides finally
describe the graph the same way. The nested form is rebuilt only when
projecting to WDK, which genuinely wants a tree.

``kind`` becomes explicit rather than inferred from which inputs happen to be
set. That inference is why ``__combine__`` exists at all: a combine had to
carry SOME search name to look like a node, so a placeholder was invented and
then had to be recognised and stripped at every boundary. With kind stated,
``search_name`` is simply absent on a combine, and the placeholder is put back
only on the way to WDK.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from pathfinder.domain.parameters.values import ParamValue
from pathfinder.domain.strategy.ast import (
    COMBINE_SEARCH_NAME,
    StepAnalysis,
    StepFilter,
    StepReport,
    StrategyStepNode,
)
from pathfinder.domain.strategy.ops import ColocationParams, CombineOp
from pathfinder.domain.strategy.validation import StepValidation
from pathfinder.platform.pydantic_base import CamelModel


class StepStatus(StrEnum):
    """What state a step is in, from the researcher's point of view.

    ``READY`` is the state the three-way split kept missing: a step that is
    complete but has not reached WDK yet. Calling that a draft would defer it
    forever, since pushing is exactly how it stops being unbuilt.
    """

    DRAFT = "draft"
    READY = "ready"
    BUILT = "built"
    INVALID = "invalid"

    @property
    def is_pushable(self) -> bool:
        """A draft is not ready for WDK; everything else is."""
        return self is not StepStatus.DRAFT


class StepKind(StrEnum):
    SEARCH = "search"
    TRANSFORM = "transform"
    COMBINE = "combine"


class StrategyStep(CamelModel):
    """One step: its own data plus which steps feed it, by id.

    ``search_name`` is None for a combine: a set operation is not a WDK
    question, and saying so is what retires the ``__combine__`` placeholder.
    """

    id: str
    kind: StepKind
    search_name: str | None = None
    parameters: dict[str, ParamValue] = Field(default_factory=dict)
    primary_input_id: str | None = None
    secondary_input_id: str | None = None
    display_name: str | None = None
    operator: CombineOp | None = None
    colocation_params: ColocationParams | None = None
    filters: list[StepFilter] = Field(default_factory=list)
    analyses: list[StepAnalysis] = Field(default_factory=list)
    reports: list[StepReport] = Field(default_factory=list)
    wdk_weight: int | None = None
    expanded_strategy_id: int | None = None
    expanded_name: str | None = None

    @property
    def display_label(self) -> str:
        """User-facing label; a combine with no name renders as "Combine"."""
        if self.display_name:
            return self.display_name
        if self.kind is StepKind.COMBINE:
            return "Combine"
        return self.search_name or self.id

    def inputs(self) -> list[str]:
        """Input step ids in slot order, omitting empty slots."""
        return [
            step_id
            for step_id in (self.primary_input_id, self.secondary_input_id)
            if step_id is not None
        ]


def _kind_of(node: StrategyStepNode) -> StepKind:
    if node.primary_input is not None and node.secondary_input is not None:
        return StepKind.COMBINE
    if node.primary_input is not None:
        return StepKind.TRANSFORM
    return StepKind.SEARCH


class DuplicateStepIdError(ValueError):
    """The same step id occupies two positions in one tree."""


def flatten_tree(root: StrategyStepNode) -> dict[str, StrategyStep]:
    """Split a nested node into a map of steps that reference each other by id.

    A repeated id is rejected rather than silently collapsed: WDK requires a
    step to belong to exactly one position, and keying by id would quietly
    turn the duplicate into a single shared step.
    """
    steps: dict[str, StrategyStep] = {}

    def visit(node: StrategyStepNode) -> None:
        if node.id in steps:
            msg = (
                f"step id {node.id!r} appears twice in the tree; "
                f"every step must occupy exactly one position"
            )
            raise DuplicateStepIdError(msg)
        kind = _kind_of(node)
        steps[node.id] = StrategyStep(
            id=node.id,
            kind=kind,
            search_name=(
                None
                if kind is StepKind.COMBINE and node.search_name == COMBINE_SEARCH_NAME
                else node.search_name
            ),
            parameters=dict(node.parameters),
            primary_input_id=(
                node.primary_input.id if node.primary_input is not None else None
            ),
            secondary_input_id=(
                node.secondary_input.id if node.secondary_input is not None else None
            ),
            display_name=node.display_name,
            operator=node.operator,
            colocation_params=node.colocation_params,
            filters=list(node.filters),
            analyses=list(node.analyses),
            reports=list(node.reports),
            wdk_weight=node.wdk_weight,
            expanded_strategy_id=node.expanded_strategy_id,
            expanded_name=node.expanded_name,
        )
        if node.primary_input is not None:
            visit(node.primary_input)
        if node.secondary_input is not None:
            visit(node.secondary_input)

    visit(root)
    return steps


def rebuild_tree(root_id: str, steps: dict[str, StrategyStep]) -> StrategyStepNode:
    """Project the keyed graph back to the nested shape WDK is given."""

    def visit(step_id: str) -> StrategyStepNode:
        step = steps[step_id]
        return StrategyStepNode(
            id=step.id,
            search_name=(
                COMBINE_SEARCH_NAME
                if step.kind is StepKind.COMBINE and step.search_name is None
                else step.search_name or ""
            ),
            parameters=dict(step.parameters),
            display_name=step.display_name,
            operator=step.operator,
            colocation_params=step.colocation_params,
            filters=list(step.filters),
            analyses=list(step.analyses),
            reports=list(step.reports),
            wdk_weight=step.wdk_weight,
            expanded_strategy_id=step.expanded_strategy_id,
            expanded_name=step.expanded_name,
            primary_input=(
                visit(step.primary_input_id)
                if step.primary_input_id is not None
                else None
            ),
            secondary_input=(
                visit(step.secondary_input_id)
                if step.secondary_input_id is not None
                else None
            ),
        )

    return visit(root_id)


def root_ids(steps: dict[str, StrategyStep]) -> set[str]:
    """Steps no other step consumes."""
    consumed = {
        input_id for step in steps.values() for input_id in step.inputs()
    }
    return {step_id for step_id in steps if step_id not in consumed}


def subtree_ids(root_id: str, steps: dict[str, StrategyStep]) -> list[str]:
    """``root_id`` and everything feeding it, descendants before ancestors."""
    out: list[str] = []
    seen: set[str] = set()

    def visit(step_id: str) -> None:
        if step_id in seen or step_id not in steps:
            return
        seen.add(step_id)
        for input_id in steps[step_id].inputs():
            visit(input_id)
        out.append(step_id)

    visit(root_id)
    return out


def find_parent(
    step_id: str, steps: dict[str, StrategyStep]
) -> tuple[StrategyStep, str] | None:
    """The step consuming ``step_id`` and which slot it occupies."""
    for step in steps.values():
        if step.primary_input_id == step_id:
            return step, "primary"
        if step.secondary_input_id == step_id:
            return step, "secondary"
    return None


def wdk_search_name(step: StrategyStep) -> str:
    """The question name WDK expects for this step.

    A combine has no question of its own, so the placeholder that used to be
    stored on every combine is supplied here instead - at the one boundary
    that actually needs it.
    """
    if step.kind is StepKind.COMBINE:
        return step.search_name or COMBINE_SEARCH_NAME
    return step.search_name or ""


def is_computable(step: StrategyStep) -> bool:
    """Whether WDK could actually run this step.

    A combine is a set operation over two results, so it needs both inputs and
    an operator. Detaching an edge deliberately leaves one behind - the canvas
    keeps the node so the researcher can rewire it - and that intermediate
    state is real but not runnable.
    """
    if step.kind is not StepKind.COMBINE:
        return True
    return (
        step.primary_input_id is not None
        and step.secondary_input_id is not None
        and step.operator is not None
    )


def pushable_root_id(
    root_id: str, steps: dict[str, StrategyStep]
) -> str | None:
    """The deepest node WDK can be asked to compute, starting at ``root_id``.

    A half-wired combine is walked past to its surviving input: pushing it
    would be rejected, and the branch below it is still a real result the
    researcher should see.
    """
    current: str | None = root_id
    while current is not None:
        step = steps.get(current)
        if step is None:
            return None
        if is_computable(step):
            return current
        inputs = step.inputs()
        current = inputs[0] if inputs else None
    return None


def step_status(
    step: StrategyStep,
    *,
    wdk_step_id: int | None,
    validation: StepValidation | None,
    has_open_params: bool,
) -> StepStatus:
    """The one answer to what state a step is in.

    Derived rather than stored: a copy on the step would need updating at every
    push, parameter edit and rewire, and a missed path would leave a step
    claiming to be built when it is not - the same failure as the stale counts.
    """
    if has_open_params or not is_computable(step):
        return StepStatus.DRAFT
    if wdk_step_id is None:
        return StepStatus.READY
    if validation is not None and not validation.is_valid:
        return StepStatus.INVALID
    return StepStatus.BUILT
