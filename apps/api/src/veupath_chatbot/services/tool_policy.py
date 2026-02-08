"""Policy layer for constraining tool-driven strategy building.

This is service-layer code (not AI-framework specific) so it can be enforced from
any interface layer (HTTP, AI tools, CLI).
"""

from __future__ import annotations

from dataclasses import dataclass

from veupath_chatbot.platform.types import JSONObject


@dataclass
class PolicyViolation:
    """A policy violation."""

    code: str
    message: str
    severity: str = "error"  # "error", "warning", "info"


@dataclass
class PolicyResult:
    """Result of policy check."""

    allowed: bool
    violations: list[PolicyViolation]


class ToolPolicy:
    """Policy for tool call constraints."""

    def __init__(
        self,
        max_steps_per_strategy: int = 20,
        max_parameters_per_search: int = 50,
        allowed_record_types: list[str] | None = None,
        blocked_searches: list[str] | None = None,
    ) -> None:
        self.max_steps_per_strategy = max_steps_per_strategy
        self.max_parameters_per_search = max_parameters_per_search
        self.allowed_record_types = allowed_record_types
        self.blocked_searches = blocked_searches or []

    def check_create_search_step(
        self,
        record_type: str,
        search_name: str,
        parameters: JSONObject,
        current_step_count: int,
    ) -> PolicyResult:
        violations: list[PolicyViolation] = []

        if current_step_count >= self.max_steps_per_strategy:
            violations.append(
                PolicyViolation(
                    code="MAX_STEPS_EXCEEDED",
                    message=f"Maximum {self.max_steps_per_strategy} steps allowed per strategy",
                )
            )

        if self.allowed_record_types and record_type not in self.allowed_record_types:
            violations.append(
                PolicyViolation(
                    code="RECORD_TYPE_NOT_ALLOWED",
                    message=f"Record type '{record_type}' not allowed",
                )
            )

        if search_name in self.blocked_searches:
            violations.append(
                PolicyViolation(
                    code="SEARCH_BLOCKED",
                    message=f"Search '{search_name}' is blocked by policy",
                )
            )

        if len(parameters) > self.max_parameters_per_search:
            violations.append(
                PolicyViolation(
                    code="TOO_MANY_PARAMETERS",
                    message=f"Maximum {self.max_parameters_per_search} parameters allowed",
                )
            )

        return PolicyResult(allowed=len(violations) == 0, violations=violations)

    def check_combine_steps(
        self, operator: str, current_step_count: int
    ) -> PolicyResult:
        del operator  # reserved for future operator-specific constraints
        violations: list[PolicyViolation] = []

        if current_step_count >= self.max_steps_per_strategy:
            violations.append(
                PolicyViolation(
                    code="MAX_STEPS_EXCEEDED",
                    message=f"Maximum {self.max_steps_per_strategy} steps allowed",
                )
            )

        return PolicyResult(allowed=len(violations) == 0, violations=violations)

    def check_build_strategy(self, step_count: int) -> PolicyResult:
        violations: list[PolicyViolation] = []

        if step_count == 0:
            violations.append(
                PolicyViolation(
                    code="EMPTY_STRATEGY",
                    message="Cannot build an empty strategy",
                )
            )

        return PolicyResult(allowed=len(violations) == 0, violations=violations)


default_policy = ToolPolicy()


def get_policy() -> ToolPolicy:
    return default_policy
