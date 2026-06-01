from __future__ import annotations

import pytest
from pydantic import ValidationError

from pathfinder.domain.strategy.plan import (
    PlannedConnection,
    PlannedStep,
    PlanTopologyError,
    StepStatus,
    StepType,
    StrategyPlan,
)


def _leaf(sid: str) -> PlannedStep:
    return PlannedStep(
        id=sid,
        search_name=f"Search_{sid}",
        display_name=sid,
        step_type=StepType.LEAF,
        status=StepStatus.READY,
    )


def _combine(sid: str) -> PlannedStep:
    return PlannedStep(
        id=sid,
        search_name="__combine__",
        display_name=sid,
        step_type=StepType.COMBINE,
        status=StepStatus.READY,
    )


def _transform(sid: str) -> PlannedStep:
    return PlannedStep(
        id=sid,
        search_name="__transform__",
        display_name=sid,
        step_type=StepType.TRANSFORM,
        status=StepStatus.READY,
    )


def _conn(frm: str, to: str) -> PlannedConnection:
    return PlannedConnection(from_step=frm, to_step=to)


def _plan(
    steps: list[PlannedStep],
    connections: list[PlannedConnection],
) -> StrategyPlan:
    return StrategyPlan(
        title="T",
        description="d",
        rationale="r",
        steps=steps,
        connections=connections,
    )


def _topology_message(exc: ValidationError) -> str:
    for err in exc.errors():
        ctx = err.get("ctx") or {}
        inner = ctx.get("error")
        if isinstance(inner, PlanTopologyError):
            return str(inner)
    return ""


class TestLeafArity:
    def test_leaf_accepts_zero_inbound(self) -> None:
        _plan([_leaf("a")], [])

    def test_leaf_rejects_inbound(self) -> None:
        with pytest.raises(ValidationError) as exc:
            _plan([_leaf("a"), _leaf("b")], [_conn("a", "b")])
        assert "leaf" in _topology_message(exc.value)


class TestCombineArity:
    def test_combine_accepts_two_inputs(self) -> None:
        _plan(
            [_leaf("a"), _leaf("b"), _combine("c")],
            [_conn("a", "c"), _conn("b", "c")],
        )

    def test_combine_rejects_one_input(self) -> None:
        with pytest.raises(ValidationError) as exc:
            _plan(
                [_leaf("a"), _combine("c")],
                [_conn("a", "c")],
            )
        msg = _topology_message(exc.value)
        assert "combine" in msg
        assert "expected 2" in msg

    def test_combine_rejects_three_inputs(self) -> None:
        with pytest.raises(ValidationError) as exc:
            _plan(
                [_leaf("a"), _leaf("b"), _leaf("c"), _combine("d")],
                [_conn("a", "d"), _conn("b", "d"), _conn("c", "d")],
            )
        msg = _topology_message(exc.value)
        assert "combine" in msg
        assert "expected 2" in msg

    def test_combine_rejects_zero_inputs(self) -> None:
        with pytest.raises(ValidationError) as exc:
            _plan([_combine("c")], [])
        assert "combine" in _topology_message(exc.value)


class TestTransformArity:
    def test_transform_accepts_one_input(self) -> None:
        _plan([_leaf("a"), _transform("t")], [_conn("a", "t")])

    def test_transform_rejects_two_inputs(self) -> None:
        with pytest.raises(ValidationError) as exc:
            _plan(
                [_leaf("a"), _leaf("b"), _transform("t")],
                [_conn("a", "t"), _conn("b", "t")],
            )
        assert "transform" in _topology_message(exc.value)

    def test_transform_rejects_zero_inputs(self) -> None:
        with pytest.raises(ValidationError) as exc:
            _plan([_transform("t")], [])
        assert "transform" in _topology_message(exc.value)


class TestConnectionRefs:
    def test_rejects_dangling_from(self) -> None:
        with pytest.raises(ValidationError) as exc:
            _plan([_leaf("a")], [_conn("ghost", "a")])
        assert "ghost" in _topology_message(exc.value)

    def test_rejects_dangling_to(self) -> None:
        with pytest.raises(ValidationError) as exc:
            _plan([_leaf("a")], [_conn("a", "ghost")])
        assert "ghost" in _topology_message(exc.value)

    def test_rejects_self_loop(self) -> None:
        with pytest.raises(ValidationError) as exc:
            _plan([_leaf("a")], [_conn("a", "a")])
        assert "self-loop" in _topology_message(exc.value).lower()


class TestRootArity:
    def test_single_root_ok(self) -> None:
        _plan(
            [_leaf("a"), _leaf("b"), _combine("c")],
            [_conn("a", "c"), _conn("b", "c")],
        )

    def test_rejects_multiple_roots(self) -> None:
        with pytest.raises(ValidationError) as exc:
            _plan(
                [_leaf("a"), _leaf("b")],
                [],
            )
        msg = _topology_message(exc.value)
        assert "multiple roots" in msg


class TestCycles:
    def test_rejects_cycle(self) -> None:
        with pytest.raises(ValidationError) as exc:
            _plan(
                [_combine("a"), _combine("b"), _combine("c")],
                [_conn("a", "b"), _conn("b", "c"), _conn("c", "a")],
            )
        msg = _topology_message(exc.value).lower()
        assert ("cycle" in msg) or ("expected 2" in msg)


class TestGoldKinaseStructure:
    def test_seven_step_kinase_membrane_est_plan(self) -> None:
        _plan(
            [
                _leaf("go_kinase"),
                _leaf("tm"),
                _leaf("sp"),
                _combine("membrane"),
                _combine("kinase_membrane"),
                _leaf("est"),
                _combine("final"),
            ],
            [
                _conn("tm", "membrane"),
                _conn("sp", "membrane"),
                _conn("go_kinase", "kinase_membrane"),
                _conn("membrane", "kinase_membrane"),
                _conn("kinase_membrane", "final"),
                _conn("est", "final"),
            ],
        )

    def test_six_step_plan_with_three_way_intersect_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            _plan(
                [
                    _leaf("go_kinase"),
                    _leaf("tm"),
                    _leaf("sp"),
                    _combine("membrane"),
                    _leaf("est"),
                    _combine("final"),
                ],
                [
                    _conn("tm", "membrane"),
                    _conn("sp", "membrane"),
                    _conn("go_kinase", "final"),
                    _conn("membrane", "final"),
                    _conn("est", "final"),
                ],
            )
        msg = _topology_message(exc.value)
        assert "combine" in msg
        assert "expected 2" in msg
