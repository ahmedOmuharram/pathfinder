"""A fork remaps every tracked WDK step id to the copied strategy.

WDK preserves topology on copy, so the source and copy trees pair by
position under the same pre-order walk.
"""

from typing import Any

import pytest

from pathfinder.integrations.veupathdb.wdk_models import (
    WDKIdentifier,
    WDKStepTree,
    WDKStrategyDetails,
)
from pathfinder.platform.errors import AppError, ErrorCode
from pathfinder.services.conversations import fork as fork_module
from pathfinder.services.conversations.fork import (
    _duplicate_wdk_strategy,
    _remap_wdk_step_ids,
    _walk_step_tree_dfs,
)


def _combine_tree(*, root: int, primary: int, secondary: int) -> WDKStepTree:
    """A 3-step combine: root combine over two leaves."""
    return WDKStepTree(
        step_id=root,
        primary_input=WDKStepTree(step_id=primary),
        secondary_input=WDKStepTree(step_id=secondary),
    )


def test_dfs_is_preorder_primary_before_secondary() -> None:
    """DFS yields root, then the whole primary subtree, then the secondary."""
    tree = WDKStepTree(
        step_id=100,
        primary_input=WDKStepTree(
            step_id=200,
            primary_input=WDKStepTree(step_id=300),
            secondary_input=WDKStepTree(step_id=400),
        ),
        secondary_input=WDKStepTree(step_id=500),
    )
    assert _walk_step_tree_dfs(tree) == [100, 200, 300, 400, 500]


def test_remap_three_step_combine_pins_exact_new_ids() -> None:
    """Fork of a real INTERSECT-over-two-leaves strategy remaps every id.

    Source WDK ids: combine=9000, GenesByTaxon leaf=9001,
    GenesByText leaf=9002. The copy gets fresh WDK ids 7000/7001/7002 in
    the SAME topology. The local AST keys (step_xxx) must each point at the
    copied WDK id, never the source's.
    """
    source = _combine_tree(root=9000, primary=9001, secondary=9002)
    copied = _combine_tree(root=7000, primary=7001, secondary=7002)

    old_ids = {
        "step_combine": 9000,
        "step_taxon": 9001,
        "step_text": 9002,
    }

    new_ids = _remap_wdk_step_ids(old_ids, source, copied)

    assert new_ids == {
        "step_combine": 7000,
        "step_taxon": 7001,
        "step_text": 7002,
    }
    # A fork must not alias the parent's steps.
    assert set(new_ids.values()).isdisjoint(set(old_ids.values()))


def test_remap_transform_chain_preserves_depth_order() -> None:
    """A transform chain (leaf -> transform -> transform) remaps in order."""
    source = WDKStepTree(
        step_id=10,
        primary_input=WDKStepTree(
            step_id=11,
            primary_input=WDKStepTree(step_id=12),
        ),
    )
    copied = WDKStepTree(
        step_id=20,
        primary_input=WDKStepTree(
            step_id=21,
            primary_input=WDKStepTree(step_id=22),
        ),
    )
    old_ids = {"top": 10, "mid": 11, "leaf": 12}
    assert _remap_wdk_step_ids(old_ids, source, copied) == {
        "top": 20,
        "mid": 21,
        "leaf": 22,
    }


def test_remap_drops_entry_absent_from_source_tree() -> None:
    """A wdkStepIds entry whose id is not in the source tree is dropped.

    Characterisation: ``_remap_wdk_step_ids`` only keeps local ids whose
    source WDK id appears in the source tree DFS. A stale entry (left over
    from a deleted step) silently disappears from the fork.
    """
    source = _combine_tree(root=9000, primary=9001, secondary=9002)
    copied = _combine_tree(root=7000, primary=7001, secondary=7002)
    old_ids = {
        "step_combine": 9000,
        "step_taxon": 9001,
        "step_text": 9002,
        "step_stale": 8888,  # not present in the source tree
    }
    new_ids = _remap_wdk_step_ids(old_ids, source, copied)
    assert "step_stale" not in new_ids
    assert new_ids == {
        "step_combine": 7000,
        "step_taxon": 7001,
        "step_text": 7002,
    }


# The copy keeps the source topology and changes every id.


def _wdk_details(*, strategy_id: int, signature: str, tree: WDKStepTree) -> Any:
    return WDKStrategyDetails.model_validate(
        {
            "strategyId": strategy_id,
            "name": "Pf invasion",
            "rootStepId": tree.step_id,
            "signature": signature,
            "stepTree": tree.model_dump(by_alias=True),
            "steps": {},
        }
    )


class _FakeStrategyAPI:
    """Returns source on the source id, copy on the copied id."""

    def __init__(self, source: Any, copied: Any, copied_id: int) -> None:
        self._source = source
        self._copied = copied
        self._copied_id = copied_id
        self.copy_calls: list[str] = []

    async def get_strategy(self, strategy_id: int) -> Any:
        if strategy_id == self._source.strategy_id:
            return self._source
        if strategy_id == self._copied_id:
            return self._copied
        msg = f"unexpected get_strategy({strategy_id})"
        raise AssertionError(msg)

    async def copy_strategy(self, signature: str) -> WDKIdentifier:
        self.copy_calls.append(signature)
        return WDKIdentifier(id=self._copied_id)


async def test_duplicate_wdk_strategy_remaps_ast_to_copied_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The full fork WDK path remaps wdkStepIds onto the copy's step ids.

    Source strategy 4242 (combine 9000 over leaves 9001/9002) is copied to
    strategy 4343 (combine 7000 over 7001/7002). The forked AST's
    ``wdkStepIds`` must end up pointing at 7000/7001/7002, and the source
    signature must be the value passed to ``copy_strategy``.
    """
    source = _wdk_details(
        strategy_id=4242,
        signature="sig-source",
        tree=_combine_tree(root=9000, primary=9001, secondary=9002),
    )
    copied = _wdk_details(
        strategy_id=4343,
        signature="sig-copy",
        tree=_combine_tree(root=7000, primary=7001, secondary=7002),
    )
    fake = _FakeStrategyAPI(source, copied, copied_id=4343)
    monkeypatch.setattr(fork_module, "get_strategy_api", lambda _site: fake)

    forked_ast: dict[str, Any] = {
        "recordType": "transcript",
        "wdkStepIds": {
            "step_combine": 9000,
            "step_taxon": 9001,
            "step_text": 9002,
        },
    }

    new_id = await _duplicate_wdk_strategy(
        site_id="plasmodb",
        source_wdk_strategy_id=4242,
        forked_ast=forked_ast,
    )

    assert new_id == 4343
    assert fake.copy_calls == ["sig-source"]
    assert forked_ast["wdkStepIds"] == {
        "step_combine": 7000,
        "step_taxon": 7001,
        "step_text": 7002,
    }


async def test_duplicate_wdk_strategy_returns_none_on_wdk_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If WDK duplication raises AppError, the fork falls back to no-WDK."""

    class _FailingAPI:
        async def get_strategy(self, strategy_id: int) -> Any:
            raise AppError(code=ErrorCode.STRATEGY_NOT_FOUND, title="boom")

        async def copy_strategy(self, signature: str) -> WDKIdentifier:
            msg = "should not reach copy_strategy"
            raise AssertionError(msg)

    monkeypatch.setattr(fork_module, "get_strategy_api", lambda _site: _FailingAPI())

    forked_ast: dict[str, Any] = {"wdkStepIds": {"step_taxon": 9001}}
    new_id = await _duplicate_wdk_strategy(
        site_id="plasmodb",
        source_wdk_strategy_id=4242,
        forked_ast=forked_ast,
    )
    assert new_id is None
    # The caller strips the map when there is no new id.
