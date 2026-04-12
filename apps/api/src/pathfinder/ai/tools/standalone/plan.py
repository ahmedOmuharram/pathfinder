"""Standalone plan tools for pydantic-ai agents.

Provides:
- ``create_plan`` -- build a new strategy plan
- ``get_plan`` -- read the current active plan
- ``update_plan`` -- mutate the active plan in-place
- ``submit_plan`` -- present the plan for user review
- ``present_decision`` -- present a decision with options
"""

from datetime import UTC, datetime
from uuid import uuid4

from pydantic_ai import RunContext

from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.tools.standalone._plan_models import (
    ConnectionRef,
    DecisionOption,
    DecisionOptionInput,
    DecisionResponse,
    PlanCreatedResponse,
    PlannedConnectionInput,
    PlannedStepInput,
    StepPatch,
    UserQuestionInput,
    _apply_step_patches,
    _convert_connection,
    _convert_question,
    _convert_step,
    _validate_domain_parameters,
    _validate_domain_topology,
    _validate_plan_topology,
)
from pathfinder.domain.strategy.ast import PlanStepNode
from pathfinder.domain.strategy.plan import (
    PlannedStep,
    PlanStatus,
    StepType,
    StrategyPlan,
    UserQuestion,
)
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error
from pathfinder.platform.types import JSONObject


def _step_to_node(step: PlannedStep) -> PlanStepNode:
    """Convert a PlannedStep to a PlanStepNode for the artifact tree."""
    raw_params = {
        k: v.value or "" for k, v in step.parameters.items()
    } if step.parameters else {}
    return PlanStepNode(
        search_name=step.search_name,
        display_name=step.display_name,
        parameters=raw_params,
    )


def _build_proposed_plan(plan: StrategyPlan) -> JSONObject | None:
    """Build a wire-format proposedStrategyPlan from the domain plan.

    Constructs a proper step tree respecting connections. Leaf steps that
    feed into a combine step become its primary/secondary inputs.
    """
    if not plan.steps:
        return None

    step_by_id = {s.id: s for s in plan.steps}
    node_by_id: dict[str, PlanStepNode] = {}

    # Build nodes bottom-up: leaves first, then combines.
    for step in plan.steps:
        if step.step_type == StepType.LEAF:
            node_by_id[step.id] = _step_to_node(step)

    # Wire connections: from_step feeds into to_step.
    for conn in plan.connections:
        target = step_by_id.get(conn.to_step)
        target_node = node_by_id.get(conn.to_step)
        source_node = node_by_id.get(conn.from_step)
        if target is None or source_node is None:
            continue
        if target_node is None:
            target_node = _step_to_node(target)
            node_by_id[conn.to_step] = target_node
        if target_node.primary_input is None:
            target_node.primary_input = source_node
        else:
            target_node.secondary_input = source_node

    # Find root: step that is never a from_step target, or the last step.
    target_ids = {c.to_step for c in plan.connections}
    root_id = next(
        (s.id for s in plan.steps if s.id not in target_ids and s.step_type != StepType.LEAF),
        None,
    )
    if root_id is None:
        # Single-step plan or no combines — use the first step.
        root_id = plan.steps[0].id

    root_node = node_by_id.get(root_id)
    if root_node is None:
        root_node = _step_to_node(plan.steps[0])

    return {
        "recordType": plan.steps[0].record_type or "transcript",
        "root": root_node.model_dump(by_alias=True, exclude_none=True, mode="json"),
        "name": plan.title,
        "description": plan.description,
    }


def _normalize_question_text(value: str | None) -> str:
    """Normalize question text for semantic deduplication."""
    if value is None:
        return ""
    return " ".join(value.split()).casefold()


def _question_key(question: UserQuestion | UserQuestionInput) -> tuple[str, str, str, str]:
    """Build a stable semantic identity for a user question."""
    return (
        _normalize_question_text(question.question),
        _normalize_question_text(question.context),
        question.related_step or "",
        question.related_param or "",
    )


def _merge_questions(
    existing: list[UserQuestion],
    incoming: list[UserQuestionInput],
) -> list[UserQuestion]:
    """Merge questions by semantic identity while preserving existing answers."""
    merged = list(existing)
    index_by_key = {_question_key(question): idx for idx, question in enumerate(merged)}

    for candidate in incoming:
        converted = _convert_question(candidate)
        key = _question_key(candidate)
        existing_index = index_by_key.get(key)
        if existing_index is None:
            merged.append(converted)
            index_by_key[key] = len(merged) - 1
            continue

        current = merged[existing_index]
        merged[existing_index] = converted.model_copy(
            update={
                "id": current.id,
                "answer": current.answer,
            },
        )

    return merged


async def create_plan(
    ctx: RunContext[AgentDeps],
    title: str,
    description: str,
    rationale: str,
    steps: list[PlannedStepInput],
    connections: list[PlannedConnectionInput],
    questions: list[UserQuestionInput] | None = None,
    uncertainties: list[str] | None = None,
) -> PlanCreatedResponse | ToolErrorPayload:
    """Create a new strategy plan and set it as the active plan.

    Returns an acknowledgment — NOT the full plan. The user cannot see the
    plan until you call submit_plan(). You can review with get_plan and
    refine with update_plan before submitting.

    Args:
        title: Plan title.
        description: What this strategy finds and why.
        rationale: Why this approach was chosen.
        steps: Planned steps.
        connections: Step connections.
        questions: Questions for the user.
        uncertainties: Things we don't know yet.
    """
    topology_error = _validate_plan_topology(steps, connections)
    if topology_error is not None:
        return topology_error

    domain_steps = [_convert_step(s) for s in steps]
    domain_connections = [_convert_connection(c) for c in connections]
    domain_questions = _merge_questions([], questions or [])

    plan = StrategyPlan(
        title=title,
        description=description,
        rationale=rationale,
        status=PlanStatus.DRAFT,
        steps=domain_steps,
        connections=domain_connections,
        questions=domain_questions,
        uncertainties=uncertainties or [],
    )

    ctx.deps.agent_state.set_plan(plan)

    # Build the planning artifact for the frontend's plan panel.
    proposed_plan = _build_proposed_plan(plan)

    artifact = {
        "id": plan.id,
        "title": plan.title,
        "summaryMarkdown": plan.description,
        "assumptions": plan.uncertainties or [],
        "proposedStrategyPlan": proposed_plan,
        "createdAt": datetime.now(UTC).isoformat(),
    }

    return PlanCreatedResponse(
        plan_id=plan.id,
        title=plan.title,
        step_count=len(plan.steps),
        planning_artifact=artifact,
    )


async def get_plan(
    ctx: RunContext[AgentDeps],
) -> StrategyPlan | ToolErrorPayload:
    """Read the current active strategy plan. Use this to review the plan before making updates."""
    plan = ctx.deps.agent_state.active_plan
    if plan is None:
        return tool_error("NO_ACTIVE_PLAN", "No plan exists yet. Use create_plan to build one.")
    return plan


def _mutate_plan(
    plan: StrategyPlan,
    *,
    title: str | None,
    description: str | None,
    step_updates: list[StepPatch] | None,
    add_steps: list[PlannedStepInput] | None,
    remove_steps: list[str] | None,
    add_connections: list[PlannedConnectionInput] | None,
    remove_connections: list[ConnectionRef] | None,
    questions: list[UserQuestionInput] | None,
) -> ToolErrorPayload | None:
    """Apply all mutations to a plan in-place. Returns an error payload or None."""
    if title is not None:
        plan.title = title
    if description is not None:
        plan.description = description

    if remove_steps:
        remove_set = set(remove_steps)
        plan.steps = [s for s in plan.steps if s.id not in remove_set]
        plan.connections = [
            c for c in plan.connections
            if c.from_step not in remove_set and c.to_step not in remove_set
        ]

    if step_updates:
        patch_err = _apply_step_patches(plan, step_updates)
        if patch_err is not None:
            return patch_err

    if add_steps:
        plan.steps.extend(_convert_step(s) for s in add_steps)

    if remove_connections:
        remove_pairs = {(r.from_step, r.to_step) for r in remove_connections}
        plan.connections = [
            c for c in plan.connections
            if (c.from_step, c.to_step) not in remove_pairs
        ]

    if add_connections:
        plan.connections.extend(_convert_connection(c) for c in add_connections)

    if questions is not None:
        plan.questions = _merge_questions(plan.questions, questions)

    return None


async def update_plan(
    ctx: RunContext[AgentDeps],
    step_updates: list[StepPatch] | None = None,
    add_steps: list[PlannedStepInput] | None = None,
    remove_steps: list[str] | None = None,
    add_connections: list[PlannedConnectionInput] | None = None,
    remove_connections: list[ConnectionRef] | None = None,
    title: str | None = None,
    description: str | None = None,
    questions: list[UserQuestionInput] | None = None,
) -> StrategyPlan | ToolErrorPayload:
    """Mutate the active plan in-place. Apply step patches, add/remove steps and connections.

    The plan stays in the tool loop — chain multiple update_plan calls, then
    call submit_plan when ready to show the user.

    Args:
        step_updates: Patches to existing steps (by step id). Merges parameters.
        add_steps: New steps to add to the plan.
        remove_steps: Step IDs to remove from the plan.
        add_connections: New connections to add.
        remove_connections: Connections to remove (by from_step + to_step).
        title: New plan title.
        description: New plan description.
        questions: User-facing questions to merge into the plan before presentation.
    """
    plan = ctx.deps.agent_state.active_plan
    if plan is None:
        return tool_error("NO_ACTIVE_PLAN", "No plan exists yet. Use create_plan to build one.")

    mutation_err = _mutate_plan(
        plan,
        title=title,
        description=description,
        step_updates=step_updates,
        add_steps=add_steps,
        remove_steps=remove_steps,
        add_connections=add_connections,
        remove_connections=remove_connections,
        questions=questions,
    )
    if mutation_err is not None:
        return mutation_err

    topo_err = _validate_domain_topology(plan)
    if topo_err is not None:
        return topo_err

    plan.version += 1
    plan.updated_at = datetime.now(UTC)

    return plan


async def submit_plan(
    ctx: RunContext[AgentDeps],
) -> StrategyPlan | ToolErrorPayload:
    """Submit the current plan for user review.

    Validates that all leaf steps have parameters and topology is valid,
    then presents the plan in the UI. Use after create_plan or update_plan.
    The pipeline pauses only when the planning phase later calls
    ``finish_planning(decision="present_plan")``. Put user-facing questions
    on the plan via create_plan or update_plan before calling submit_plan.
    """
    deps = ctx.deps
    plan = deps.agent_state.active_plan
    if plan is None:
        return tool_error("NO_ACTIVE_PLAN", "No plan exists yet. Use create_plan to build one.")

    param_err = _validate_domain_parameters(plan, deps.agent_state)
    if param_err is not None:
        return param_err

    topo_err = _validate_domain_topology(plan)
    if topo_err is not None:
        return topo_err

    plan.status = PlanStatus.PRESENTED
    plan.updated_at = datetime.now(UTC)

    plan_dict = plan.model_dump(by_alias=True, mode="json")
    deps.emit_event({
        "type": "plan_presented",
        "data": {"plan": plan_dict},
    })
    proposed = _build_proposed_plan(plan)
    if proposed is not None:
        deps.emit_event({
            "type": "graph_plan",
            "data": {"plan": proposed},
        })

    return plan


async def present_decision(
    ctx: RunContext[AgentDeps],
    question: str,
    options: list[DecisionOptionInput],
    context: str,
    recommendation: str | None = None,
) -> DecisionResponse:
    """Present a decision with options for the user to choose from.

    Unlike submit_plan, this does NOT pause the tool loop. The decision
    is emitted to the UI for display but execution continues. Use when
    you need to inform the user of a trade-off or ask a non-blocking
    question while continuing other work.

    Args:
        question: The decision question.
        options: Options with pros/cons.
        context: Why this decision matters.
        recommendation: Your recommended option.
    """
    decision_id = f"decision_{uuid4().hex[:12]}"

    response = DecisionResponse(
        decision_id=decision_id,
        question=question,
        options=[
            DecisionOption(
                label=opt.label,
                description=opt.description,
                pros=opt.pros,
                cons=opt.cons,
                recommended=opt.recommended,
            )
            for opt in options
        ],
        context=context,
        recommendation=recommendation,
    )

    ctx.deps.emit_event({
        "type": "decision_presented",
        "data": response.model_dump(by_alias=True, mode="json"),
    })

    return response
