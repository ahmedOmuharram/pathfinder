"""Unit tests for ``deep_clone_with_fresh_ids`` (save-substrategy / insert-saved).

When a subtree is saved as a new WDK strategy, or a saved strategy is
inserted back into a conversation, every node must get a FRESH local id so
the clone never shares ids with the source graph (which would violate the
``StrategyAst`` unique-id invariant and WDK's "step belongs to one strategy"
rule). These tests pin id-freshness, topology preservation, and parameter
isolation for a real INTERSECT-over-two-leaves subtree.
"""

from pathfinder.domain.parameters.values import MultiPickValue, StringValue
from pathfinder.domain.strategy.ast import StrategyStepNode, walk_step_tree
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.services.strategies.save_substrategy import (
    deep_clone_with_fresh_ids,
)


def _combine_subtree() -> StrategyStepNode:
    return StrategyStepNode(
        id="step_combine",
        search_name="__combine__",
        operator=CombineOp.INTERSECT,
        primary_input=StrategyStepNode(
            id="step_taxon",
            search_name="GenesByTaxon",
            parameters={
                "organism": MultiPickValue(values=["Plasmodium falciparum 3D7"]),
            },
        ),
        secondary_input=StrategyStepNode(
            id="step_text",
            search_name="GenesByText",
            parameters={"text_expression": StringValue(value="invasion")},
        ),
    )


def test_clone_assigns_fresh_ids_to_every_node() -> None:
    src = _combine_subtree()
    clone = deep_clone_with_fresh_ids(src)

    src_ids = {n.id for n in walk_step_tree(src)}
    clone_ids = {n.id for n in walk_step_tree(clone)}
    assert len(clone_ids) == 3
    assert src_ids.isdisjoint(clone_ids), "clone reused a source step id"


def test_clone_preserves_topology_operator_and_params() -> None:
    src = _combine_subtree()
    clone = deep_clone_with_fresh_ids(src)

    assert clone.search_name == "__combine__"
    assert clone.operator == CombineOp.INTERSECT
    assert clone.primary_input is not None
    assert clone.secondary_input is not None
    assert clone.primary_input.search_name == "GenesByTaxon"
    assert clone.primary_input.parameters["organism"] == MultiPickValue(
        values=["Plasmodium falciparum 3D7"],
    )
    assert clone.secondary_input.search_name == "GenesByText"
    assert clone.secondary_input.parameters["text_expression"] == StringValue(
        value="invasion",
    )


def test_clone_parameters_dict_is_isolated_from_source() -> None:
    """Mutating the clone's parameters dict must not bleed into the source.

    ``model_copy`` is a shallow copy: fields not in ``update`` (here,
    ``parameters``) keep their object identity. If the cloned node's
    ``parameters`` dict is the SAME object as the source's, inserting or
    editing a parameter on the saved/inserted strategy corrupts the
    originating conversation's step. This is the shared-by-reference
    artifact-copy bug (lead #4/#5).
    """
    src = _combine_subtree()
    clone = deep_clone_with_fresh_ids(src)

    assert clone.primary_input is not None
    assert src.primary_input is not None
    # The cloned leaf must not share the SAME dict object as its source.
    assert clone.primary_input.parameters is not src.primary_input.parameters, (
        "clone shares the source node's parameters dict object (shallow copy)"
    )

    clone.primary_input.parameters["added_on_clone"] = StringValue(value="x")
    assert "added_on_clone" not in src.primary_input.parameters, (
        "mutating the clone's parameters dict leaked into the source step"
    )
