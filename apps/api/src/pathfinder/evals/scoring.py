"""The structural signature of a strategy, and the difference report of one case.

The signature drops step ids and parameter values, so two builds of the same
shape compare equal. A failing case reports every difference it found, each
naming the field, the expectation and what the run produced.
"""

from __future__ import annotations

from assistant_core.platform.pydantic_base import CamelModel
from pydantic import ConfigDict, Field

from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.evals.case import EvalCase

NO_STRATEGY = "(none)"


def _node_signature(node: StrategyStepNode) -> str:
    kind = node.infer_kind()
    if kind == "combine":
        operator = node.operator.value if node.operator else "?"
        left = _node_signature(node.primary_input) if node.primary_input else "?"
        right = _node_signature(node.secondary_input) if node.secondary_input else "?"
        return f"({left} {operator} {right})"
    if kind == "transform":
        inner = _node_signature(node.primary_input) if node.primary_input else "?"
        return f"{node.search_name}({inner})"
    return node.search_name


def structure_signature(ast: StrategyAst) -> str:
    """The shape of *ast* as one string: search names and operators, no ids."""
    return _node_signature(ast.root)


class ObservedOutcome(CamelModel):
    """What one run of a case produced."""

    model_config = ConfigDict(frozen=True)

    built_strategy: bool
    structure: str | None = None
    record_type: str | None = None
    step_count: int | None = None
    verified: bool | None = None
    reply_text: str = ""


class CaseDifference(CamelModel):
    """One named disagreement between the expectation and the run."""

    model_config = ConfigDict(frozen=True)

    field: str
    expected: str
    actual: str


class CaseScore(CamelModel):
    """The verdict on one case, and every difference behind it."""

    model_config = ConfigDict(frozen=True)

    name: str
    passed: bool
    differences: list[CaseDifference] = Field(default_factory=list)


def _build_difference(
    case: EvalCase,
    observed: ObservedOutcome,
) -> CaseDifference | None:
    if case.expected.builds_strategy == observed.built_strategy:
        return None
    return CaseDifference(
        field="builtStrategy",
        expected=str(case.expected.builds_strategy).lower(),
        actual=observed.structure or str(observed.built_strategy).lower(),
    )


def _value_differences(
    case: EvalCase,
    observed: ObservedOutcome,
) -> list[CaseDifference]:
    expected = case.expected
    compared: tuple[tuple[str, object | None, object | None], ...] = (
        ("structure", expected.structure, observed.structure or NO_STRATEGY),
        ("recordType", expected.record_type, observed.record_type),
        ("stepCount", expected.step_count, observed.step_count),
        ("verified", expected.verified, observed.verified),
    )
    return [
        CaseDifference(field=field, expected=str(want), actual=str(got))
        for field, want, got in compared
        if want is not None and want != got
    ]


def _phrase_differences(
    case: EvalCase,
    observed: ObservedOutcome,
) -> list[CaseDifference]:
    reply = observed.reply_text.casefold()
    missing = [p for p in case.expected.reply_mentions if p.casefold() not in reply]
    present = [p for p in case.expected.reply_omits if p.casefold() in reply]
    differences: list[CaseDifference] = []
    if missing:
        differences.append(
            CaseDifference(
                field="replyMentions",
                expected=", ".join(missing),
                actual=observed.reply_text[:200],
            ),
        )
    if present:
        differences.append(
            CaseDifference(
                field="replyOmits",
                expected=", ".join(present),
                actual=observed.reply_text[:200],
            ),
        )
    return differences


def score_case(case: EvalCase, observed: ObservedOutcome) -> CaseScore:
    """Compare one run against its case. Every difference is reported."""
    build = _build_difference(case, observed)
    if build is not None:
        return CaseScore(name=case.name, passed=False, differences=[build])
    differences = _value_differences(case, observed) + _phrase_differences(
        case,
        observed,
    )
    return CaseScore(
        name=case.name,
        passed=not differences,
        differences=differences,
    )


__all__ = [
    "NO_STRATEGY",
    "CaseDifference",
    "CaseScore",
    "ObservedOutcome",
    "score_case",
    "structure_signature",
]
