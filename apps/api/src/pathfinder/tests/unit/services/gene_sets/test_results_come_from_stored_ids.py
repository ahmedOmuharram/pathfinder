"""A gene set's results are the genes it stores, not what its source returns now.

The set records the ids it was made from. Reading results from the step it came
from instead means an edit to that strategy silently changes what the set shows,
so an enrichment saved against the set stops describing its own input.
"""

from __future__ import annotations

from pathfinder.services.gene_sets.frozen_step import frozen_step_cache_key


class TestTheCacheKeyFollowsTheMembership:
    def test_the_same_ids_reuse_one_step(self) -> None:
        a = frozen_step_cache_key("plasmodb", ["PF3D7_0100100", "PF3D7_0200200"])
        b = frozen_step_cache_key("plasmodb", ["PF3D7_0100100", "PF3D7_0200200"])

        assert a == b

    def test_order_does_not_make_a_new_step(self) -> None:
        a = frozen_step_cache_key("plasmodb", ["PF3D7_0100100", "PF3D7_0200200"])
        b = frozen_step_cache_key("plasmodb", ["PF3D7_0200200", "PF3D7_0100100"])

        assert a == b

    def test_different_membership_is_a_different_step(self) -> None:
        a = frozen_step_cache_key("plasmodb", ["PF3D7_0100100"])
        b = frozen_step_cache_key("plasmodb", ["PF3D7_0100100", "PF3D7_0200200"])

        assert a != b

    def test_a_site_is_part_of_the_key(self) -> None:
        # The same locus tag is a different record on a different site.
        a = frozen_step_cache_key("plasmodb", ["PF3D7_0100100"])
        b = frozen_step_cache_key("toxodb", ["PF3D7_0100100"])

        assert a != b
