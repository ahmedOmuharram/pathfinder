"""Deterministic mock engine for E2E testing.

Returns predetermined tool calls based on keyword matching on the user
message.  The ONLY fake in the stack — everything downstream (WDK API,
PostgreSQL, Redis, gene sets, auto-build) runs real.
"""

from collections.abc import AsyncIterable

from kani import AIFunction, ChatMessage
from kani.engines.base import BaseCompletion, BaseEngine, Completion
from kani.models import ChatRole, ToolCall

# Real WDK organism values per VEuPathDB site (verified against live APIs).
_SITE_ORGANISMS: dict[str, str] = {
    "plasmodb": "Plasmodium falciparum 3D7",
    "toxodb": "Toxoplasma gondii ME49",
    "tritrypdb": "Leishmania major strain Friedlin",
    "cryptodb": "Cryptosporidium parvum Iowa II",
    "fungidb": "Aspergillus fumigatus Af293",
}


def _organism_for_site(site_id: str) -> str:
    return _SITE_ORGANISMS.get(site_id, _SITE_ORGANISMS["plasmodb"])


def _last_user_text(messages: list[ChatMessage]) -> str:
    """Extract the text of the last user message."""
    for msg in reversed(messages):
        if msg.role == ChatRole.USER and msg.text:
            return msg.text
    return ""


def _has_function_result(messages: list[ChatMessage]) -> bool:
    """Check if the most recent non-system message is a function result."""
    for msg in reversed(messages):
        if msg.role == ChatRole.SYSTEM:
            continue
        return msg.role == ChatRole.FUNCTION
    return False


def _build_planning_artifact_call(site_id: str) -> list[ToolCall]:
    """Build a save_planning_artifact tool call with real WDK plan."""
    organism = _organism_for_site(site_id)
    plan = {
        "recordType": "gene",
        "root": {
            "id": "step_1",
            "searchName": "GenesByTaxon",
            "displayName": f"All {organism} genes",
            "parameters": {"organism": f'["{organism}"]'},
        },
        "metadata": {"name": f"{organism} gene search"},
    }
    return [
        ToolCall.from_function(
            "save_planning_artifact",
            title=f"{organism} gene search",
            summary_markdown=f"Search for all genes in {organism} using GenesByTaxon.",
            assumptions=[],
            parameters={},
            proposed_strategy_plan=plan,
        )
    ]


def _build_delegation_draft_call(site_id: str) -> list[ToolCall]:
    """Build a save_planning_artifact with delegation plan parameters."""
    organism = _organism_for_site(site_id)
    return [
        ToolCall.from_function(
            "save_planning_artifact",
            title="Delegation draft",
            summary_markdown=f"Build a gene strategy for {organism} using delegation.",
            assumptions=[],
            parameters={
                "delegationGoal": f"Build a gene strategy for {organism}.",
                "delegationPlan": {
                    "tasks": [
                        {
                            "id": "task_search",
                            "type": "search",
                            "searchName": "GenesByTaxon",
                            "context": f"Find genes in {organism}",
                        },
                    ],
                },
            },
            proposed_strategy_plan={
                "recordType": "gene",
                "root": {
                    "id": "step_1",
                    "searchName": "GenesByTaxon",
                    "displayName": f"All {organism} genes",
                    "parameters": {"organism": f'["{organism}"]'},
                },
                "metadata": {"name": f"{organism} delegation strategy"},
            },
        )
    ]


def _build_delegation_call(site_id: str) -> list[ToolCall]:
    """Build a delegate_strategy_subtasks tool call.

    The plan must be a valid tree node for ``build_delegation_plan``'s
    ``compile_node`` — either a task node or a combine tree.
    """
    organism = _organism_for_site(site_id)
    return [
        ToolCall.from_function(
            "delegate_strategy_subtasks",
            goal=f"Find all genes in {organism}",
            plan={
                "task": f"Search for {organism} genes using GenesByTaxon",
                "type": "task",
                "context": f"Find genes in {organism}",
            },
        )
    ]


def _build_create_step_call(site_id: str) -> list[ToolCall]:
    """Build a create_step tool call with real WDK params."""
    organism = _organism_for_site(site_id)
    return [
        ToolCall.from_function(
            "create_step",
            search_name="GenesByTaxon",
            parameters={"organism": f'["{organism}"]'},
            record_type="gene",
            display_name=f"All {organism} genes",
        )
    ]


def _route_tool_calls(
    user_text: str,
    site_id: str,
    functions: list[AIFunction] | None = None,
) -> list[ToolCall] | None:
    """Route user message to appropriate tool calls, or None for plain text.

    When no keyword matches but ``create_step`` is in the available
    functions (sub-kani context), creates a step automatically.
    """
    lower = user_text.lower()

    if "delegation draft" in lower:
        return _build_delegation_draft_call(site_id)
    if "delegate_strategy_subtasks" in lower or "delegation" in lower:
        return _build_delegation_call(site_id)
    if "artifact graph" in lower:
        return _build_planning_artifact_call(site_id)
    if "create step" in lower:
        return _build_create_step_call(site_id)

    # Sub-kani fallback: if create_step is available, create a step.
    # Sub-kanis always need to produce at least one step.
    if functions:
        fn_names = {f.name for f in functions}
        if "create_step" in fn_names:
            return _build_create_step_call(site_id)

    return None


class MockEngine(BaseEngine):
    """Deterministic kani engine for E2E testing.

    Returns predetermined tool calls based on keyword matching on the user
    message.  After tool results appear in history, returns plain text to
    exit the full_round loop.

    The ONLY mock in the stack — all downstream systems run real.
    """

    max_context_size: int = 128_000

    def __init__(self, site_id: str = "plasmodb") -> None:
        self.site_id = site_id

    def prompt_len(
        self,
        messages: list[ChatMessage],
        functions: list[AIFunction] | None = None,
        **kwargs: object,
    ) -> int:
        return sum(len(m.text or "") for m in messages)

    async def predict(
        self,
        messages: list[ChatMessage],
        functions: list[AIFunction] | None = None,
        **hyperparams: object,
    ) -> BaseCompletion:
        user_text = _last_user_text(messages)

        # Post-tool turn: model just saw function result → respond with text.
        if _has_function_result(messages):
            content = f"[mock] Processed tool results for: {user_text}"
            msg = ChatMessage.assistant(content)
            return Completion(msg, prompt_tokens=0, completion_tokens=len(content))

        # First turn: route keywords → tool calls or plain text.
        tool_calls = _route_tool_calls(user_text, self.site_id, functions)
        if tool_calls:
            msg = ChatMessage.assistant(content=None, tool_calls=tool_calls)
            return Completion(msg, prompt_tokens=0, completion_tokens=0)

        # Default: plain text response.
        content = f"[mock] I received your message: {user_text}"
        msg = ChatMessage.assistant(content)
        return Completion(msg, prompt_tokens=0, completion_tokens=len(content))

    async def stream(
        self,
        messages: list[ChatMessage],
        functions: list[AIFunction] | None = None,
        **hyperparams: object,
    ) -> AsyncIterable[str | BaseCompletion]:
        completion = await self.predict(messages, functions, **hyperparams)
        text = completion.message.text
        if text:
            # Yield word-by-word for realistic SSE delta simulation.
            words = text.split(" ")
            for i, word in enumerate(words):
                yield word + ("" if i == len(words) - 1 else " ")
        yield completion
