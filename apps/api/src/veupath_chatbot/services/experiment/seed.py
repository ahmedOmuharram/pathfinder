"""Seed strategy and control-set definitions.

Creates real WDK strategies (visible in the sidebar) and curated control sets
(available in the Experiments tab) across multiple VEuPathDB sites.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

logger = get_logger(__name__)


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
# Organisms
# ---------------------------------------------------------------------------

PF_ORG = "Plasmodium falciparum 3D7"
PF_EC_SOURCES = ["GeneDB", "KEGG_Enzyme", "MPMP"]

TG_ORG = "Toxoplasma gondii ME49"
TG_EC_SOURCES = [
    "KEGG_Enzyme",
    "MetabolicPath",
    "GenBank",
    "computationally inferred from Orthology",
    "Uniprot",
]

CP_ORG = "Cryptosporidium parvum Iowa II"
LM_ORG = "Leishmania major strain Friedlin"

# ---------------------------------------------------------------------------
# Gene lists — real VEuPathDB gene IDs
# ---------------------------------------------------------------------------

PLASMO_KINASES = [
    "PF3D7_0102600",
    "PF3D7_0107600",
    "PF3D7_0203100",
    "PF3D7_0211700",
    "PF3D7_0213400",
    "PF3D7_0214600",
    "PF3D7_0217500",
    "PF3D7_0301200",
    "PF3D7_0302100",
    "PF3D7_0309200",
    "PF3D7_0311400",
    "PF3D7_0312400",
    "PF3D7_0420100",
    "PF3D7_0424500",
    "PF3D7_0424700",
    "PF3D7_0500900",
    "PF3D7_0525900",
    "PF3D7_0605300",
    "PF3D7_0610600",
    "PF3D7_0628200",
]

PLASMO_RIBOSOMAL = [
    "PF3D7_0210100",
    "PF3D7_0210400",
    "PF3D7_0212200",
    "PF3D7_0214200",
    "PF3D7_0217800",
    "PF3D7_0219200",
    "PF3D7_0304400",
    "PF3D7_0306900",
    "PF3D7_0307100",
    "PF3D7_0307200",
    "PF3D7_0309600",
    "PF3D7_0312800",
    "PF3D7_0315500",
    "PF3D7_0316100",
    "PF3D7_0316800",
    "PF3D7_0317600",
    "PF3D7_0322900",
    "PF3D7_0406800",
    "PF3D7_0412100",
    "PF3D7_0413800",
]

TOXO_KINASES = [
    "TGME49_202310",
    "TGME49_203010",
    "TGME49_204280",
    "TGME49_206560",
    "TGME49_206590",
    "TGME49_207665",
    "TGME49_210280",
    "TGME49_210830",
    "TGME49_213800",
    "TGME49_214970",
    "TGME49_216400",
    "TGME49_218220",
    "TGME49_218550",
    "TGME49_218720",
    "TGME49_221720",
    "TGME49_224950",
    "TGME49_225490",
    "TGME49_226030",
    "TGME49_227260",
    "TGME49_228750",
]

TOXO_RIBOSOMAL = [
    "TGME49_202350",
    "TGME49_203630",
    "TGME49_204020",
    "TGME49_205340",
    "TGME49_207440",
    "TGME49_207840",
    "TGME49_207940",
    "TGME49_209290",
    "TGME49_209430",
    "TGME49_209710",
    "TGME49_210690",
    "TGME49_211870",
    "TGME49_212290",
    "TGME49_213350",
    "TGME49_213580",
    "TGME49_214870",
    "TGME49_215460",
    "TGME49_215470",
    "TGME49_216010",
    "TGME49_216040",
]

CRYPTO_KINASES = [
    "cgd1_1220",
    "cgd1_1490",
    "cgd1_2110",
    "cgd1_2630",
    "cgd1_2850",
    "cgd1_2960",
    "cgd1_3230",
    "cgd1_400",
    "cgd1_60",
    "cgd1_810",
    "cgd1_890",
    "cgd2_1060",
    "cgd2_1300",
    "cgd2_1610",
    "cgd2_1830",
    "cgd2_1880",
    "cgd2_1960",
    "cgd2_2310",
    "cgd2_3190",
    "cgd2_3340",
]

CRYPTO_RIBOSOMAL = [
    "cgd1_1660",
    "cgd1_2270",
    "cgd1_300",
    "cgd1_3000",
    "cgd1_850",
    "cgd2_120",
    "cgd2_130",
    "cgd2_170",
    "cgd2_2200",
    "cgd2_280",
    "cgd2_2870",
    "cgd2_3000",
    "cgd2_350",
    "cgd2_4260",
    "cgd3_1250",
    "cgd3_1300",
    "cgd3_2090",
    "cgd3_2250",
    "cgd3_2440",
    "Cgd2_2990",
]

CRYPTO_DNA_REPLICATION = [
    "cgd2_1100",
    "cgd2_1250",
    "cgd2_1550",
    "cgd2_1600",
    "cgd2_2500",
    "cgd2_3180",
    "cgd3_1450",
    "cgd3_3170",
    "cgd3_3470",
    "cgd3_3820",
    "cgd3_4290",
    "cgd4_1283",
    "cgd4_1490",
    "cgd4_1930",
    "cgd4_430",
]

TRITRYP_KINASES = [
    "LmjF.01.0750",
    "LmjF.02.0120",
    "LmjF.02.0290",
    "LmjF.02.0360",
    "LmjF.02.0570",
    "LmjF.03.0210",
    "LmjF.03.0350",
    "LmjF.03.0780",
    "LmjF.04.0440",
    "LmjF.04.0650",
    "LmjF.04.1210",
    "LmjF.05.0130",
    "LmjF.05.0390",
    "LmjF.05.0550",
    "LmjF.06.0640",
    "LmjF.06.1180",
    "LmjF.07.0160",
    "LmjF.07.0170",
    "LmjF.07.0250",
    "LmjF.07.0690",
]

TRITRYP_RIBOSOMAL = [
    "LmjF.01.0410",
    "LmjF.01.0420",
    "LmjF.03.0250",
    "LmjF.03.0430",
    "LmjF.03.0440",
    "LmjF.04.0270",
    "LmjF.04.0470",
    "LmjF.04.0750",
    "LmjF.04.0950",
    "LmjF.05.0340",
    "LmjF.06.0040",
    "LmjF.06.0410",
    "LmjF.06.0415",
    "LmjF.06.0570",
    "LmjF.06.0580",
    "LmjF.07.0680",
    "LmjF.08.0280",
    "LmjF.10.0070",
    "LmjF.11.0760",
    "LmjF.11.0780",
]


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


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


async def run_seed(
    *,
    user_id: UUID,
    strategy_repo: Any,
    control_set_repo: Any,
) -> AsyncIterator[JSONObject]:
    """Create seed strategies and control sets, yielding SSE progress events.

    For each :class:`SeedDef`:
    1. Create a WDK strategy via ``_materialize_step_tree`` + ``create_strategy``
    2. Sync the strategy to the user's sidebar via ``_sync_single_wdk_strategy``
    3. Create a control set via ``control_set_repo.create``

    Imports are deferred to avoid circular dependencies.
    """
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
    from veupath_chatbot.services.experiment.service import _materialize_step_tree
    from veupath_chatbot.transport.http.routers.strategies.wdk_import import (
        _sync_single_wdk_strategy,
    )

    total = len(SEEDS)
    yield {
        "type": "seed_progress",
        "data": {
            "phase": "starting",
            "message": f"Seeding {total} strategies and control sets...",
        },
    }

    strategies_ok = 0
    control_sets_ok = 0

    for i, seed in enumerate(SEEDS):
        idx = i + 1
        yield {
            "type": "seed_progress",
            "data": {
                "phase": "running",
                "current": idx,
                "total": total,
                "name": seed.name,
                "message": f"[{idx}/{total}] Creating strategy: {seed.name}",
            },
        }

        t0 = time.monotonic()
        try:
            api = get_strategy_api(seed.site_id)

            # 1. Materialize step tree into real WDK steps
            root_tree = await _materialize_step_tree(
                api, seed.step_tree, seed.record_type
            )

            # 2. Create the WDK strategy (visible, not internal)
            created = await api.create_strategy(
                step_tree=root_tree,
                name=seed.name,
                description=seed.description,
                is_saved=True,
            )
            wdk_strategy_id: int | None = None
            if isinstance(created, dict):
                raw = created.get("id")
                if isinstance(raw, int):
                    wdk_strategy_id = raw

            if wdk_strategy_id is None:
                raise ValueError(f"WDK did not return a strategy ID for '{seed.name}'")

            # 3. Sync to local DB (sidebar)
            await _sync_single_wdk_strategy(
                wdk_id=wdk_strategy_id,
                site_id=seed.site_id,
                api=api,
                strategy_repo=strategy_repo,
                user_id=user_id,
            )
            strategies_ok += 1

            elapsed_strategy = time.monotonic() - t0
            yield {
                "type": "seed_strategy_complete",
                "data": {
                    "current": idx,
                    "total": total,
                    "name": seed.name,
                    "wdkStrategyId": wdk_strategy_id,
                    "elapsed": round(elapsed_strategy, 1),
                    "message": (f"[{idx}/{total}] Strategy created: {seed.name}"),
                },
            }

            # 4. Create control set
            cs = seed.control_set
            await control_set_repo.create(
                name=cs.name,
                site_id=seed.site_id,
                record_type=seed.record_type,
                positive_ids=cs.positive_ids,
                negative_ids=cs.negative_ids,
                source="curation",
                tags=cs.tags,
                provenance_notes=cs.provenance_notes,
                is_public=True,
                user_id=user_id,
            )
            control_sets_ok += 1

        except Exception as exc:
            elapsed = time.monotonic() - t0
            logger.error("Seed failed", name=seed.name, error=str(exc))
            yield {
                "type": "seed_item_error",
                "data": {
                    "current": idx,
                    "total": total,
                    "name": seed.name,
                    "error": str(exc),
                    "elapsed": round(elapsed, 1),
                    "message": f"[{idx}/{total}] Failed: {seed.name} — {exc}",
                },
            }

    yield {
        "type": "seed_complete",
        "data": {
            "total": total,
            "strategiesCreated": strategies_ok,
            "controlSetsCreated": control_sets_ok,
            "failed": total - strategies_ok,
            "message": (
                f"Seeding complete: {strategies_ok}/{total} strategies, "
                f"{control_sets_ok}/{total} control sets"
            ),
        },
    }
