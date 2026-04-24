"""StrategyStepNode auto-decodes wire-form parameter strings.

Guards against regression of the load-side validator. The DB stored
wire-form strings for months — any future reload must auto-decode so
the canonicalizer / vocab matcher / frontend never sees the wire form
inside the domain layer.
"""

from __future__ import annotations

from pathfinder.domain.strategy.ast import StrategyStepNode


class TestLoadDecodes:
    def test_wire_form_organism_decodes_on_load(self) -> None:
        node = StrategyStepNode.model_validate(
            {
                "searchName": "GenesByGoTerm",
                "parameters": {
                    "organism": '["Plasmodium"]',
                    "go_term": "GO:0016301",
                    "go_term_evidence": '["Curated", "Computed"]',
                    "go_term_slim": "No",
                },
            },
        )
        assert node.parameters == {
            "organism": ["Plasmodium"],
            "go_term": "GO:0016301",
            "go_term_evidence": ["Curated", "Computed"],
            "go_term_slim": "No",
        }

    def test_native_shapes_kept(self) -> None:
        node = StrategyStepNode.model_validate(
            {
                "searchName": "GenesByGoTerm",
                "parameters": {
                    "organism": ["Plasmodium falciparum 3D7"],
                    "go_term": "GO:0016301",
                },
            },
        )
        assert node.parameters == {
            "organism": ["Plasmodium falciparum 3D7"],
            "go_term": "GO:0016301",
        }

    def test_recursive_input_also_decoded(self) -> None:
        node = StrategyStepNode.model_validate(
            {
                "searchName": "__combine__",
                "operator": "INTERSECT",
                "parameters": {},
                "primaryInput": {
                    "searchName": "GenesByGoTerm",
                    "parameters": {"organism": '["Plasmodium"]'},
                },
                "secondaryInput": {
                    "searchName": "GenesByTaxon",
                    "parameters": {"organism": '["Toxoplasma"]'},
                },
            },
        )
        assert node.primary_input is not None
        assert node.secondary_input is not None
        assert node.primary_input.parameters == {"organism": ["Plasmodium"]}
        assert node.secondary_input.parameters == {"organism": ["Toxoplasma"]}
