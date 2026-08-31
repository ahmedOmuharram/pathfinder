"""PathFinder's script for the deterministic test model.

The Lead routes on the latest user message (plus consult-resume state) and
drives a scripted FRAME -> BUILD -> VERIFY flow; sub-agents emit their typed
delta via ``final_result``. The canned FRAME specs live in ``mock_specs``; the
machinery that runs this script lives in ``scripted``.
"""

from __future__ import annotations

from typing import Any, Literal

from assistant_core.models.scripted import (
    RoleMarkers,
    RoleScript,
    ScriptedModel,
    called_tool_parts,
    current_scope_id,
    current_turn,
    current_user_text,
    deferred_tool_resolved,
    has_any,
    joined_user_text,
    last_user_text,
    next_unmade_call,
    scripted_call,
    terminal_call,
    tool_return_parts,
)
from pydantic_ai.messages import ModelMessage, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from pathfinder.ai.models.mock_specs import (
    CriterionReply,
    SpecPlan,
    alt_organism_for,
    combined_spec,
    criterion_replies,
    edit_frame_call,
    frame_call,
    go_spec,
    interpro_spec,
    organism_for,
    single_spec,
    verification_delta,
)

LeadTurnState = Literal["await_user", "complete"]

_CLARIFY_PROSE = (
    "Before I build this, let me **clarify** a few things so the strategy "
    "matches what you mean:\n\n"
    "- **Which** evidence defines 'expressed' — a mass-spec stage or a "
    "microarray percentile?\n"
    "- **How strict** on 'doesn't vary much' — what dN/dS cutoff?\n"
    "- What counts as 'no human equivalent' — which phylogenetic profile "
    "pattern?\n\n"
    "Answer those and I'll frame the strategy."
)
_SUCCESS_PROSE = (
    "**Verified end-to-end.** The strategy framed, built, and verified "
    "cleanly: root size looks right and the leaves are non-empty."
)
_FEEDBACK_PROSE = (
    "**Verification found a problem.** One leaf **returned 0** rows, so the "
    "combined result is empty; that pattern is too narrow. Loosen it and I "
    "will re-verify."
)
_IMPACT_PROSE = (
    "Switching the combine to INTERSECT makes the **operator** **stricter**: "
    "the result **drops** to genes supported by *both* signals. That tightens "
    "specificity at the cost of recall, so expect a smaller candidate list."
)
_VARIANT_PROSE = (
    "I ran both search variants and compared their result sets above. Tell me "
    "which direction you'd like to carry into the strategy."
)
_CONTROLS_PROSE = (
    "I've saved your uploaded gene IDs as a control set. We can now score "
    "search variants against them whenever you're ready."
)
_LOOP_PROSE = (
    "I kept re-reading the same catalog listing and made no progress, so I "
    "stopped there."
)
_EDIT_PROSE = (
    "**Substituted the organism** on the seed criterion. Every other criterion "
    "is unchanged, and the steps behind them keep the ids they had."
)
_REMEMBER_PROSE = (
    "Stored for future sessions: your default organism. I built nothing - say "
    "the word and I will turn it into a strategy."
)
_CONTEXT_PROSE = (
    "Good area to be in. I have not built anything yet. Want me to put a "
    "candidate strategy together for it?"
)

LEAD = "lead"
FRAME = "frame"
VERIFICATION = "verification"
EXECUTION = "execution"

# Ordered: the first role whose markers intersect the agent's tool names wins.
# Lead is first: its dispatch tools are unique to the Lead and never appear on a
# sub-agent. (Do NOT key the Lead on consult_user: approval-required deferred
# tools are excluded from AgentInfo.function_tools.)
_ROLES: tuple[RoleMarkers, ...] = (
    RoleMarkers(
        role=LEAD,
        markers=frozenset(
            {
                "frame_problem",
                "build_strategy",
                "verify_strategy",
                "read_ledger_section",
            }
        ),
    ),
    RoleMarkers(role=FRAME, markers=frozenset({"set_criterion", "set_structure"})),
    RoleMarkers(role=VERIFICATION, markers=frozenset({"run_control_tests_on_step"})),
    RoleMarkers(
        role=EXECUTION, markers=frozenset({"update_leaf_params", "replace_subtree"})
    ),
)


# Markers are deliberately specific to the journeys' turn prompts so generic
# biology prompts fall through to the plain echo.
_FIX_MARKERS = ("loosen", "%mamm", "fix the phylogenetic", "fix the pattern")
_IMPACT_MARKERS = ("switching the interpro", "switch the interpro", "interpro/go")
_BUILD_MARKERS = ("3d7", "trophozoite", "derisi", "create step", "create delegation")
# A kinase-broadening request builds the two-leaf spec and fails verification,
# so the turn carries the zero-result guidance the editor specs read.
_FEEDBACK_MARKERS = ("interpro", "pf00069", "ec 2.7")
_GO_MARKERS = ("go term strategy", "protein kinase go genes")
_COMBINED_MARKERS = ("comprehensive kinase strategy", "all parameter types")
_CLARIFY_MARKERS = ("human equivalent", "vary much")
_VARIANT_MARKERS = ("compare two search variants", "compare search variants")
_CONSULT_MARKERS = ("consult me before planning", "ask me design questions")
# The FRAME arc that asks for one catalog listing over and over, which is what
# the repetition guard exists to stop.
_LOOP_MARKERS = ("read the catalog again and again",)
# An edit turn names a substitution and asks for the rest to stand.
_EDIT_MARKERS = ("keep the rest", "swap the organism", "substitute the organism")
# A request to store a preference, and a bare statement of what the user works
# on. Neither asks for a strategy.
_REMEMBER_MARKERS = ("please remember", "remember for future sessions")
_CONTEXT_MARKERS = ("i'm investigating", "i am investigating")
_LOOP_CALL_ARGS = {"record_type": "transcript"}

CLASSIFY = "classify_user_intent"


def _variant_text_params(expression: str) -> dict[str, Any]:
    return {
        "text_expression": {"type": "string", "value": expression},
        "text_fields": {"type": "multi-pick-vocabulary", "values": ["product"]},
        "document_type": {"type": "string", "value": "gene"},
        "text_search_organism": {
            "type": "multi-pick-vocabulary",
            "values": ["Plasmodium falciparum 3D7"],
        },
    }


def _variant_args() -> dict[str, Any]:
    return {
        "variants": [
            {
                "label": "kinase",
                "search_name": "GenesByText",
                "record_type": "transcript",
                "parameters": _variant_text_params("kinase"),
            },
            {
                "label": "phosphatase",
                "search_name": "GenesByText",
                "record_type": "transcript",
                "parameters": _variant_text_params("phosphatase"),
            },
        ],
    }


def _consult_args() -> dict[str, Any]:
    return {
        "questions": [
            {
                "id": "q1",
                "prompt": "Fold-change threshold?",
                "kind": "single_choice",
                "options": [
                    {"label": "2-fold", "recommended": True},
                    {"label": "5-fold"},
                ],
            },
            {
                "id": "q2",
                "prompt": "Include the microarray arm?",
                "kind": "single_choice",
                "options": [{"label": "Yes"}, {"label": "No"}],
            },
        ],
    }


def _attachment_gene_ids(text: str) -> list[str]:
    """Pull the cleaned gene IDs the composer's attachment adapter inlined as
    ``Attached gene-ID list from <name>: ID, ID, ...`` (plain framing so the
    input injection scanner doesn't flag it)."""
    marker = text.find("Attached gene-ID list from")
    if marker == -1:
        return []
    colon = text.find(":", marker)
    if colon == -1:
        return []
    line = text[colon + 1 :].splitlines()[0]
    return [token.strip() for token in line.split(",") if token.strip()]


def spec_for(text: str, site_id: str) -> SpecPlan:
    """The canned spec a request builds, on the vocabulary of its own site.

    The Lead and the FRAME sub-agent both route through here, so the prose and
    the criteria always describe the same strategy.
    """
    lowered = text.lower()
    organism = organism_for(site_id)
    if has_any(lowered, _FIX_MARKERS) or has_any(lowered, _FEEDBACK_MARKERS):
        return interpro_spec(organism)
    if has_any(lowered, _GO_MARKERS):
        return go_spec(organism)
    if has_any(lowered, _COMBINED_MARKERS):
        return combined_spec(organism)
    return single_spec(organism)


def verification_succeeds(text: str) -> bool:
    """A broadening request fails verification until a fix request follows it."""
    lowered = text.lower()
    if has_any(lowered, _FIX_MARKERS):
        return True
    return not has_any(lowered, _FEEDBACK_MARKERS + _CLARIFY_MARKERS)


def _active_spec() -> SpecPlan:
    return spec_for(current_user_text.get(), current_scope_id.get())


def _lead_final(prose: str, next_state: LeadTurnState) -> ToolCallPart:
    return terminal_call({"prose": prose, "nextState": next_state})


def _classify(classification: str) -> ToolCallPart:
    return scripted_call(
        CLASSIFY,
        {
            "intent": {
                "rawText": current_user_text.get(),
                "classification": classification,
                "inferredGoal": f"[mock] {classification}",
            },
        },
    )


def _classified_this_turn(messages: list[ModelMessage]) -> bool:
    return any(
        part.tool_name == CLASSIFY for part in called_tool_parts(current_turn(messages))
    )


def _build_sequence(prose: str, next_state: LeadTurnState) -> list[ToolCallPart]:
    return [
        _classify("new_strategy"),
        scripted_call("frame_problem", {"reason": "mock frame"}),
        scripted_call("build_strategy", {}),
        scripted_call("verify_strategy", {"reason": "mock verification"}),
        _lead_final(prose, next_state),
    ]


def _lead_sequence(messages: list[ModelMessage]) -> list[ToolCallPart]:
    if deferred_tool_resolved(messages, "consult_user"):
        return _build_sequence(_SUCCESS_PROSE, "complete")
    raw = last_user_text(messages)
    ids = _attachment_gene_ids(joined_user_text(messages))
    if ids:
        return [
            scripted_call(
                "build_control_set",
                {"name": "Uploaded controls", "positive_ids": ids},
            ),
            _lead_final(_CONTROLS_PROSE, "await_user"),
        ]
    return _routed_sequence(raw)


def _prose_only_sequence(lowered: str) -> list[ToolCallPart] | None:
    """The arcs that answer in prose and call no tool."""
    if has_any(lowered, _IMPACT_MARKERS):
        return [_lead_final(_IMPACT_PROSE, "await_user")]
    if has_any(lowered, _CLARIFY_MARKERS):
        return [_lead_final(_CLARIFY_PROSE, "await_user")]
    if has_any(lowered, _CONTEXT_MARKERS):
        return [
            _classify("context_statement"),
            _lead_final(_CONTEXT_PROSE, "await_user"),
        ]
    return None


def _one_tool_sequence(lowered: str) -> list[ToolCallPart] | None:
    """The arcs that dispatch one tool and then answer."""
    if has_any(lowered, _EDIT_MARKERS):
        return [
            _classify("edit_strategy"),
            scripted_call("edit_strategy", {"reason": "mock edit: swap the organism"}),
            _lead_final(_EDIT_PROSE, "await_user"),
        ]
    if has_any(lowered, _REMEMBER_MARKERS):
        return [
            _classify("memory_request"),
            scripted_call(
                "remember",
                {
                    "kind": "preference",
                    "name": "default organism",
                    "summary": "The user works with Plasmodium falciparum 3D7.",
                    "content": {"organism": "Plasmodium falciparum 3D7"},
                },
            ),
            _lead_final(_REMEMBER_PROSE, "await_user"),
        ]
    if has_any(lowered, _LOOP_MARKERS):
        return [
            _classify("new_strategy"),
            scripted_call("frame_problem", {"reason": "mock loop"}),
            _lead_final(_LOOP_PROSE, "await_user"),
        ]
    if has_any(lowered, _VARIANT_MARKERS):
        return [
            scripted_call("compare_search_variants", _variant_args()),
            _lead_final(_VARIANT_PROSE, "await_user"),
        ]
    if has_any(lowered, _CONSULT_MARKERS):
        return [scripted_call("consult_user", _consult_args())]
    return None


def _routed_sequence(raw: str) -> list[ToolCallPart]:
    lowered = raw.lower()
    dispatched = _one_tool_sequence(lowered)
    if dispatched is not None:
        return dispatched
    prose = _prose_only_sequence(lowered)
    if prose is not None:
        return prose
    build = (
        _FIX_MARKERS
        + _FEEDBACK_MARKERS
        + _GO_MARKERS
        + _BUILD_MARKERS
        + _COMBINED_MARKERS
    )
    if has_any(lowered, build):
        return _build_branch(raw)
    return [_lead_final(f"[mock] {raw}", "await_user")]


def _build_branch(raw: str) -> list[ToolCallPart]:
    if verification_succeeds(raw):
        return _build_sequence(_SUCCESS_PROSE, "complete")
    return _build_sequence(_FEEDBACK_PROSE, "await_user")


def _lead_script(messages: list[ModelMessage]) -> ToolCallPart:
    """The next call of this turn's arc.

    The classification is the turn's own: an arc that opens with it re-runs it
    on every turn, so the intent the Lead gates its tools on is never a
    previous turn's.
    """
    sequence = _lead_sequence(messages)
    if sequence[0].tool_name != CLASSIFY:
        return next_unmade_call(sequence, messages)
    if not _classified_this_turn(messages):
        return sequence[0]
    return next_unmade_call(sequence[1:], messages)


def _criterion_replies(messages: list[ModelMessage]) -> list[CriterionReply]:
    return criterion_replies(tool_return_parts(messages))


def _frame_script(messages: list[ModelMessage]) -> ToolCallPart:
    if has_any(current_user_text.get().lower(), _LOOP_MARKERS):
        return scripted_call("list_searches", _LOOP_CALL_ARGS)
    work_order = last_user_text(messages)
    if work_order.startswith("EDIT work order"):
        return edit_frame_call(
            work_order,
            alt_organism_for(current_scope_id.get()),
            called_tool_parts(messages),
            _criterion_replies(messages),
        )
    return frame_call(
        _active_spec(),
        called_tool_parts(messages),
        _criterion_replies(messages),
    )


def _verification_script(messages: list[ModelMessage]) -> ToolCallPart:
    del messages
    success = verification_succeeds(current_user_text.get())
    prose = _SUCCESS_PROSE if success else _FEEDBACK_PROSE
    return terminal_call(verification_delta(success=success, prose=prose))


def _execution_script(messages: list[ModelMessage]) -> ToolCallPart:
    del messages
    return terminal_call({"actionsTaken": ["[mock] recovery"], "followUpNeeded": False})


def _silent_script(messages: list[ModelMessage]) -> ToolCallPart:
    del messages
    return terminal_call({})


_SCRIPTS: dict[str, RoleScript] = {
    LEAD: _lead_script,
    FRAME: _frame_script,
    VERIFICATION: _verification_script,
    EXECUTION: _execution_script,
}

PATHFINDER_SCRIPT = ScriptedModel(
    roles=_ROLES,
    scripts=_SCRIPTS,
    unknown=_silent_script,
)


def get_mock_model() -> FunctionModel:
    return PATHFINDER_SCRIPT.as_function_model()


__all__ = ["PATHFINDER_SCRIPT", "get_mock_model"]
