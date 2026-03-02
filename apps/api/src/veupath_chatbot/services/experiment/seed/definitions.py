"""Seed strategy and control-set definitions.

Defines :class:`SeedDef` and :class:`ControlSetDef` dataclasses plus the
master :data:`SEEDS` list that drives :func:`run_seed`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from veupath_chatbot.services.experiment.seed.gene_lists import (
    CP_ORG,
    CRYPTO_DNA_REPLICATION,
    CRYPTO_KINASES,
    CRYPTO_RIBOSOMAL,
    LM_ORG,
    PF_EC_SOURCES,
    PF_ORG,
    PLASMO_KINASES,
    PLASMO_RIBOSOMAL,
    TG_EC_SOURCES,
    TG_ORG,
    TOXO_KINASES,
    TOXO_RIBOSOMAL,
    TRITRYP_KINASES,
    TRITRYP_RIBOSOMAL,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _org(names: list[str]) -> str:
    return json.dumps(names)


def _go_search_params(organism: str, go_id: str) -> dict[str, str]:
    return {
        "organism": _org([organism]),
        "go_term_evidence": json.dumps(["Curated", "Computed"]),
        "go_term_slim": "No",
        "go_typeahead": json.dumps([go_id]),
        "go_term": go_id,
    }


def _ec_kinase_params(organism: str, ec_sources: list[str]) -> dict[str, str]:
    return {
        "organism": _org([organism]),
        "ec_source": json.dumps(ec_sources),
        "ec_number_pattern": "2.7.11.1",
        "ec_wildcard": "No",
    }


# ---------------------------------------------------------------------------
# Seed definitions
# ---------------------------------------------------------------------------


@dataclass
class ControlSetDef:
    """Definition for a curated control set."""

    name: str
    positive_ids: list[str]
    negative_ids: list[str]
    provenance_notes: str
    tags: list[str] = field(default_factory=list)


@dataclass
class SeedDef:
    """Definition for a seeded strategy + associated control set."""

    name: str
    description: str
    site_id: str
    step_tree: dict[str, Any]
    control_set: ControlSetDef
    record_type: str = "transcript"


SEEDS: list[SeedDef] = [
    # -- PlasmoDB --------------------------------------------------------
    SeedDef(
        name="PF3D7 Exported Kinases",
        description="Kinases with signal peptides in P. falciparum 3D7.",
        site_id="plasmodb",
        step_tree={
            "id": "combine_1",
            "displayName": "Exported Kinases",
            "operator": "INTERSECT",
            "primaryInput": {
                "id": "step_kinases",
                "displayName": "Kinases (EC 2.7.11.1)",
                "searchName": "GenesByEcNumber",
                "parameters": _ec_kinase_params(PF_ORG, PF_EC_SOURCES),
            },
            "secondaryInput": {
                "id": "step_signal",
                "displayName": "Signal Peptide",
                "searchName": "GenesWithSignalPeptide",
                "parameters": {"organism": _org([PF_ORG])},
            },
        },
        control_set=ControlSetDef(
            name="P. falciparum Kinases (curated)",
            positive_ids=PLASMO_KINASES[:12],
            negative_ids=PLASMO_RIBOSOMAL[:12],
            provenance_notes=(
                "Positives: validated protein kinases from PlasmoDB annotation "
                "(EC 2.7.11.1, serine/threonine-protein kinase activity). "
                "Negatives: 40S/60S ribosomal structural proteins — housekeeping "
                "genes with no kinase function."
            ),
            tags=["kinase", "plasmodium", "seed"],
        ),
    ),
    SeedDef(
        name="PF3D7 Non-Ribosomal Kinases",
        description="EC kinases MINUS ribosomal constituent genes.",
        site_id="plasmodb",
        step_tree={
            "id": "combine_minus",
            "displayName": "Kinases minus Ribosomal",
            "operator": "MINUS",
            "primaryInput": {
                "id": "step_ec_kinases",
                "displayName": "All Kinases",
                "searchName": "GenesByEcNumber",
                "parameters": _ec_kinase_params(PF_ORG, PF_EC_SOURCES),
            },
            "secondaryInput": {
                "id": "step_ribosomal",
                "displayName": "Ribosomal Proteins",
                "searchName": "GenesByGoTerm",
                "parameters": _go_search_params(PF_ORG, "GO:0003735"),
            },
        },
        control_set=ControlSetDef(
            name="P. falciparum Kinases vs Ribosomal",
            positive_ids=PLASMO_KINASES[:15],
            negative_ids=PLASMO_RIBOSOMAL[:15],
            provenance_notes=(
                "Positives: annotated serine/threonine kinases (EC 2.7.11.1). "
                "Negatives: structural constituents of ribosome (GO:0003735) — "
                "highly conserved housekeeping genes."
            ),
            tags=["kinase", "plasmodium", "seed"],
        ),
    ),
    SeedDef(
        name="PF3D7 Comprehensive Kinases",
        description="3-node tree: UNION of (EC kinases INTERSECT signal peptide) with GO kinase.",
        site_id="plasmodb",
        step_tree={
            "id": "root_union",
            "displayName": "Comprehensive Kinases",
            "operator": "UNION",
            "primaryInput": {
                "id": "intersect_exported",
                "displayName": "Exported Kinases",
                "operator": "INTERSECT",
                "primaryInput": {
                    "id": "leaf_ec",
                    "displayName": "EC Kinases",
                    "searchName": "GenesByEcNumber",
                    "parameters": _ec_kinase_params(PF_ORG, PF_EC_SOURCES),
                },
                "secondaryInput": {
                    "id": "leaf_signal",
                    "displayName": "Signal Peptide",
                    "searchName": "GenesWithSignalPeptide",
                    "parameters": {"organism": _org([PF_ORG])},
                },
            },
            "secondaryInput": {
                "id": "leaf_go_kinase",
                "displayName": "GO Kinase Activity",
                "searchName": "GenesByGoTerm",
                "parameters": _go_search_params(PF_ORG, "GO:0004672"),
            },
        },
        control_set=ControlSetDef(
            name="P. falciparum Full Kinase Panel",
            positive_ids=PLASMO_KINASES,
            negative_ids=PLASMO_RIBOSOMAL,
            provenance_notes=(
                "Positives: comprehensive set of 20 validated P. falciparum "
                "protein kinases (EC + GO annotations). "
                "Negatives: 20 ribosomal structural proteins — stable housekeeping "
                "genes serving as reliable negative controls."
            ),
            tags=["kinase", "plasmodium", "seed", "comprehensive"],
        ),
    ),
    # -- ToxoDB ----------------------------------------------------------
    SeedDef(
        name="TgME49 Confident Kinases",
        description="INTERSECT GO:0004672 with EC 2.7.11.1 in T. gondii ME49.",
        site_id="toxodb",
        step_tree={
            "id": "combine_kinase",
            "displayName": "GO intersect EC Kinases",
            "operator": "INTERSECT",
            "primaryInput": {
                "id": "step_go_kinase",
                "displayName": "GO: Kinase Activity",
                "searchName": "GenesByGoTerm",
                "parameters": _go_search_params(TG_ORG, "GO:0004672"),
            },
            "secondaryInput": {
                "id": "step_ec_kinase",
                "displayName": "EC: Ser/Thr Kinase",
                "searchName": "GenesByEcNumber",
                "parameters": _ec_kinase_params(TG_ORG, TG_EC_SOURCES),
            },
        },
        control_set=ControlSetDef(
            name="T. gondii Kinases (curated)",
            positive_ids=TOXO_KINASES[:15],
            negative_ids=TOXO_RIBOSOMAL[:15],
            provenance_notes=(
                "Positives: T. gondii ME49 kinases confirmed by both GO:0004672 "
                "(kinase activity) and EC 2.7.11.1 annotations. "
                "Negatives: ribosomal structural proteins (housekeeping)."
            ),
            tags=["kinase", "toxoplasma", "seed"],
        ),
    ),
    SeedDef(
        name="TgME49 Non-Ribosomal Kinases",
        description="T. gondii ME49 kinases MINUS ribosomal proteins.",
        site_id="toxodb",
        step_tree={
            "id": "combine_minus",
            "displayName": "Kinases - Ribosomal",
            "operator": "MINUS",
            "primaryInput": {
                "id": "step_kinase",
                "displayName": "Kinase Activity",
                "searchName": "GenesByGoTerm",
                "parameters": _go_search_params(TG_ORG, "GO:0004672"),
            },
            "secondaryInput": {
                "id": "step_ribosomal",
                "displayName": "Ribosomal Proteins",
                "searchName": "GenesByGoTerm",
                "parameters": _go_search_params(TG_ORG, "GO:0003735"),
            },
        },
        control_set=ControlSetDef(
            name="T. gondii Kinases vs Ribosomal",
            positive_ids=TOXO_KINASES[:15],
            negative_ids=TOXO_RIBOSOMAL[:15],
            provenance_notes=(
                "Positives: GO-annotated T. gondii kinases. "
                "Negatives: structural ribosome constituents (GO:0003735)."
            ),
            tags=["kinase", "toxoplasma", "seed"],
        ),
    ),
    # -- CryptoDB --------------------------------------------------------
    SeedDef(
        name="CpIowaII Replication + Kinases",
        description="UNION of DNA replication and kinase activity in C. parvum Iowa II.",
        site_id="cryptodb",
        step_tree={
            "id": "combine_union",
            "displayName": "Replication union Kinases",
            "operator": "UNION",
            "primaryInput": {
                "id": "step_replication",
                "displayName": "DNA Replication",
                "searchName": "GenesByGoTerm",
                "parameters": _go_search_params(CP_ORG, "GO:0006260"),
            },
            "secondaryInput": {
                "id": "step_kinases",
                "displayName": "Kinase Activity",
                "searchName": "GenesByGoTerm",
                "parameters": _go_search_params(CP_ORG, "GO:0004672"),
            },
        },
        control_set=ControlSetDef(
            name="C. parvum Kinases + Replication",
            positive_ids=CRYPTO_KINASES[:12] + CRYPTO_DNA_REPLICATION[:6],
            negative_ids=CRYPTO_RIBOSOMAL[:15],
            provenance_notes=(
                "Positives: C. parvum Iowa II kinases (GO:0004672) and DNA "
                "replication genes (GO:0006260). "
                "Negatives: ribosomal structural proteins."
            ),
            tags=["kinase", "replication", "cryptosporidium", "seed"],
        ),
    ),
    SeedDef(
        name="CpIowaII Replication Kinases",
        description="INTERSECT of DNA replication and kinase activity in C. parvum Iowa II.",
        site_id="cryptodb",
        step_tree={
            "id": "combine_intersect",
            "displayName": "Replication intersect Kinases",
            "operator": "INTERSECT",
            "primaryInput": {
                "id": "step_replication",
                "displayName": "DNA Replication",
                "searchName": "GenesByGoTerm",
                "parameters": _go_search_params(CP_ORG, "GO:0006260"),
            },
            "secondaryInput": {
                "id": "step_kinases",
                "displayName": "Kinase Activity",
                "searchName": "GenesByGoTerm",
                "parameters": _go_search_params(CP_ORG, "GO:0004672"),
            },
        },
        control_set=ControlSetDef(
            name="C. parvum Replication Kinases",
            positive_ids=CRYPTO_KINASES[:12],
            negative_ids=CRYPTO_RIBOSOMAL[:12],
            provenance_notes=(
                "Positives: C. parvum kinases involved in DNA replication. "
                "Negatives: ribosomal structural proteins."
            ),
            tags=["kinase", "replication", "cryptosporidium", "seed"],
        ),
    ),
    # -- TriTrypDB -------------------------------------------------------
    SeedDef(
        name="LmjF Non-Ribosomal Kinases",
        description="L. major Friedlin kinases MINUS ribosomal proteins.",
        site_id="tritrypdb",
        step_tree={
            "id": "combine_minus",
            "displayName": "Kinases - Ribosomal",
            "operator": "MINUS",
            "primaryInput": {
                "id": "step_kinases",
                "displayName": "Kinase Activity",
                "searchName": "GenesByGoTerm",
                "parameters": _go_search_params(LM_ORG, "GO:0004672"),
            },
            "secondaryInput": {
                "id": "step_ribosomal",
                "displayName": "Ribosomal Proteins",
                "searchName": "GenesByGoTerm",
                "parameters": _go_search_params(LM_ORG, "GO:0003735"),
            },
        },
        control_set=ControlSetDef(
            name="L. major Kinases vs Ribosomal",
            positive_ids=TRITRYP_KINASES[:15],
            negative_ids=TRITRYP_RIBOSOMAL[:15],
            provenance_notes=(
                "Positives: L. major Friedlin kinases (GO:0004672). "
                "Negatives: ribosomal structural proteins (GO:0003735) — "
                "highly conserved housekeeping genes."
            ),
            tags=["kinase", "leishmania", "seed"],
        ),
    ),
    SeedDef(
        name="LmjF Comprehensive Kinases",
        description="3-node tree: UNION of (GO kinase INTERSECT signal peptide) with EC kinases.",
        site_id="tritrypdb",
        step_tree={
            "id": "root_union",
            "displayName": "Comprehensive Kinases",
            "operator": "UNION",
            "primaryInput": {
                "id": "intersect_secreted",
                "displayName": "Secreted Kinases",
                "operator": "INTERSECT",
                "primaryInput": {
                    "id": "leaf_go_kinase",
                    "displayName": "GO Kinase",
                    "searchName": "GenesByGoTerm",
                    "parameters": _go_search_params(LM_ORG, "GO:0004672"),
                },
                "secondaryInput": {
                    "id": "leaf_signal",
                    "displayName": "Signal Peptide",
                    "searchName": "GenesWithSignalPeptide",
                    "parameters": {"organism": _org([LM_ORG])},
                },
            },
            "secondaryInput": {
                "id": "leaf_ec",
                "displayName": "EC Kinases",
                "searchName": "GenesByEcNumber",
                "parameters": _ec_kinase_params(
                    LM_ORG,
                    ["GeneDB", "GenBank", "computationally inferred from Orthology"],
                ),
            },
        },
        control_set=ControlSetDef(
            name="L. major Full Kinase Panel",
            positive_ids=TRITRYP_KINASES,
            negative_ids=TRITRYP_RIBOSOMAL,
            provenance_notes=(
                "Positives: comprehensive set of 20 L. major Friedlin protein "
                "kinases (EC + GO annotations). "
                "Negatives: 20 ribosomal structural proteins."
            ),
            tags=["kinase", "leishmania", "seed", "comprehensive"],
        ),
    ),
]
