"""Site help's script for the deterministic test model.

Three arcs for the site-help agent: a fixed reply to the check prompt, one
tool call for a question about the sites, and an echo for anything else.
"""

from __future__ import annotations

from assistant_core.models.scripted import (
    RoleMarkers,
    RoleScript,
    ScriptedModel,
    ScriptedPart,
    has_any,
    last_user_text,
    scripted_call,
    scripted_text,
    tool_return_parts,
)
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import FunctionModel

SITE_HELP = "site_help"
LIST_SITES_TOOL = "list_veupathdb_sites"
DESCRIBE_SITE_TOOL = "describe_site"

CHECK_MARKER = "site help check"
CHECK_REPLY = "Site help is online."
SITES_REPLY = "Those are the VEuPathDB sites I can point you around."

_SITES_MARKERS = ("which sites", "what sites", "list the sites")

_ROLES: tuple[RoleMarkers, ...] = (
    RoleMarkers(
        role=SITE_HELP,
        markers=frozenset({LIST_SITES_TOOL, DESCRIBE_SITE_TOOL}),
    ),
)


def _site_help_script(messages: list[ModelMessage]) -> ScriptedPart:
    if any(part.tool_name == LIST_SITES_TOOL for part in tool_return_parts(messages)):
        return scripted_text(SITES_REPLY)
    text = last_user_text(messages)
    lowered = text.lower()
    if CHECK_MARKER in lowered:
        return scripted_text(CHECK_REPLY)
    if has_any(lowered, _SITES_MARKERS):
        return scripted_call(LIST_SITES_TOOL, {})
    return scripted_text(f"[mock] {text}")


def _unknown_agent_script(messages: list[ModelMessage]) -> ScriptedPart:
    """An agent offering no site-help tool lands here. The conversation-title
    agent is one, and its prompt carries the user's message on the last line.
    """
    lines = last_user_text(messages).splitlines()
    return scripted_text(lines[-1] if lines else "")


_SCRIPTS: dict[str, RoleScript] = {SITE_HELP: _site_help_script}

SITE_HELP_SCRIPT = ScriptedModel(
    roles=_ROLES,
    scripts=_SCRIPTS,
    unknown=_unknown_agent_script,
)


def build_site_help_mock() -> FunctionModel:
    return SITE_HELP_SCRIPT.as_function_model()


__all__ = [
    "CHECK_MARKER",
    "CHECK_REPLY",
    "DESCRIBE_SITE_TOOL",
    "LIST_SITES_TOOL",
    "SITES_REPLY",
    "SITE_HELP_SCRIPT",
    "build_site_help_mock",
]
