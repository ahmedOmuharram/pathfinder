#!/usr/bin/env python3
"""Seed the experiments tab with realistic WDK strategies and import-mode experiments.

Usage:
    python scripts/seed_experiments.py [--api-url http://localhost:8000]

Flow:
  1. Creates WDK strategies via POST /api/v1/experiments/create-strategy
  2. Runs experiments via POST /api/v1/experiments/ with mode="import"
     and sourceStrategyId pointing to each created strategy
  3. Syncs strategies to the local DB (so they appear in the Chat sidebar)

Covers PlasmoDB, ToxoDB, CryptoDB, and TriTrypDB with real gene IDs,
biologically meaningful search configurations, and multi-step trees
using INTERSECT, UNION, and MINUS operators.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_SECRET_KEY = os.environ.get("API_SECRET_KEY", "")

CONTROLS_SEARCH = "GeneByLocusTag"
CONTROLS_PARAM = "ds_gene_ids"


def _create_auth_token(user_id: str, secret_key: str, expires_in: int = 3600) -> str:
    """Create a Pathfinder auth token (same logic as platform/security.py)."""
    expiry = int(time.time()) + expires_in
    signature = hmac.new(
        secret_key.encode(),
        f"{user_id}:{expiry}".encode(),
        hashlib.sha256,
    ).hexdigest()[:16]
    return f"{user_id}:{expiry}:{signature}"


def _discover_user_id(api_url: str) -> str | None:
    """Discover a user ID by calling the auth refresh endpoint.

    Falls back to querying well-known endpoints.
    """
    # Try the /api/v1/auth/refresh endpoint (returns user info)
    try:
        r = httpx.get(f"{api_url}/api/v1/auth/refresh", timeout=5)
        if r.status_code == 200:
            data = r.json()
            uid = data.get("userId") or data.get("user_id")
            if uid:
                return str(uid)
    except Exception:
        pass
    return None


def _sync_strategies_to_sidebar(
    api_url: str, sites: set[str], auth_token: str
) -> None:
    """Call sync-wdk for each site so strategies appear in the Chat sidebar."""
    print("\nSyncing strategies to local DB (Chat sidebar)...")
    headers = {"Cookie": f"pathfinder-auth={auth_token}"}
    for site in sorted(sites):
        try:
            r = httpx.post(
                f"{api_url}/api/v1/strategies/sync-wdk",
                params={"siteId": site},
                headers=headers,
                timeout=30,
            )
            if r.status_code == 200:
                data = r.json()
                print(f"  {site}: synced {len(data)} strategies")
            else:
                print(f"  {site}: sync failed (HTTP {r.status_code})")
        except Exception as exc:
            print(f"  {site}: sync error: {exc}")

# ---------------------------------------------------------------------------
# Gene data — real IDs from VEuPathDB (Feb 2026)
# ---------------------------------------------------------------------------

# PlasmoDB: P. falciparum 3D7 serine/threonine kinases (EC 2.7.11.1)
PLASMO_KINASES = [
    "PF3D7_0102600", "PF3D7_0107600", "PF3D7_0203100", "PF3D7_0211700",
    "PF3D7_0213400", "PF3D7_0214600", "PF3D7_0217500", "PF3D7_0301200",
    "PF3D7_0302100", "PF3D7_0309200", "PF3D7_0311400", "PF3D7_0312400",
    "PF3D7_0420100", "PF3D7_0424500", "PF3D7_0424700", "PF3D7_0500900",
    "PF3D7_0525900", "PF3D7_0605300", "PF3D7_0610600", "PF3D7_0628200",
]

# PlasmoDB: P. falciparum 3D7 ribosomal proteins (GO:0003735)
PLASMO_RIBOSOMAL = [
    "PF3D7_0210100", "PF3D7_0210400", "PF3D7_0212200", "PF3D7_0214200",
    "PF3D7_0217800", "PF3D7_0219200", "PF3D7_0304400", "PF3D7_0306900",
    "PF3D7_0307100", "PF3D7_0307200", "PF3D7_0309600", "PF3D7_0312800",
    "PF3D7_0315500", "PF3D7_0316100", "PF3D7_0316800", "PF3D7_0317600",
    "PF3D7_0322900", "PF3D7_0406800", "PF3D7_0412100", "PF3D7_0413800",
]

# ToxoDB: T. gondii ME49 kinases (EC 2.7.11.1 + GO:0004672)
TOXO_KINASES = [
    "TGME49_202310", "TGME49_203010", "TGME49_204280", "TGME49_206560",
    "TGME49_206590", "TGME49_207665", "TGME49_210280", "TGME49_210830",
    "TGME49_213800", "TGME49_214970", "TGME49_216400", "TGME49_218220",
    "TGME49_218550", "TGME49_218720", "TGME49_221720", "TGME49_224950",
    "TGME49_225490", "TGME49_226030", "TGME49_227260", "TGME49_228750",
]

# ToxoDB: T. gondii ME49 ribosomal proteins (GO:0003735)
TOXO_RIBOSOMAL = [
    "TGME49_202350", "TGME49_203630", "TGME49_204020", "TGME49_205340",
    "TGME49_207440", "TGME49_207840", "TGME49_207940", "TGME49_209290",
    "TGME49_209430", "TGME49_209710", "TGME49_210690", "TGME49_211870",
    "TGME49_212290", "TGME49_213350", "TGME49_213580", "TGME49_214870",
    "TGME49_215460", "TGME49_215470", "TGME49_216010", "TGME49_216040",
]

# CryptoDB: C. parvum Iowa II kinases (GO:0004672)
CRYPTO_KINASES = [
    "cgd1_1220", "cgd1_1490", "cgd1_2110", "cgd1_2630", "cgd1_2850",
    "cgd1_2960", "cgd1_3230", "cgd1_400", "cgd1_60", "cgd1_810",
    "cgd1_890", "cgd2_1060", "cgd2_1300", "cgd2_1610", "cgd2_1830",
    "cgd2_1880", "cgd2_1960", "cgd2_2310", "cgd2_3190", "cgd2_3340",
]

# CryptoDB: C. parvum Iowa II ribosomal proteins (GO:0003735)
CRYPTO_RIBOSOMAL = [
    "cgd1_1660", "cgd1_2270", "cgd1_300", "cgd1_3000", "cgd1_850",
    "cgd2_120", "cgd2_130", "cgd2_170", "cgd2_2200", "cgd2_280",
    "cgd2_2870", "cgd2_3000", "cgd2_350", "cgd2_4260", "cgd3_1250",
    "cgd3_1300", "cgd3_2090", "cgd3_2250", "cgd3_2440", "Cgd2_2990",
]

# CryptoDB: C. parvum Iowa II DNA replication genes (GO:0006260)
CRYPTO_DNA_REPLICATION = [
    "cgd2_1100", "cgd2_1250", "cgd2_1550", "cgd2_1600", "cgd2_2500",
    "cgd2_3180", "cgd3_1450", "cgd3_3170", "cgd3_3470", "cgd3_3820",
    "cgd3_4290", "cgd4_1283", "cgd4_1490", "cgd4_1930", "cgd4_430",
]

# TriTrypDB: L. major Friedlin kinases (GO:0004672)
TRITRYP_KINASES = [
    "LmjF.01.0750", "LmjF.02.0120", "LmjF.02.0290", "LmjF.02.0360",
    "LmjF.02.0570", "LmjF.03.0210", "LmjF.03.0350", "LmjF.03.0780",
    "LmjF.04.0440", "LmjF.04.0650", "LmjF.04.1210", "LmjF.05.0130",
    "LmjF.05.0390", "LmjF.05.0550", "LmjF.06.0640", "LmjF.06.1180",
    "LmjF.07.0160", "LmjF.07.0170", "LmjF.07.0250", "LmjF.07.0690",
]

# TriTrypDB: L. major Friedlin ribosomal proteins (GO:0003735)
TRITRYP_RIBOSOMAL = [
    "LmjF.01.0410", "LmjF.01.0420", "LmjF.03.0250", "LmjF.03.0430",
    "LmjF.03.0440", "LmjF.04.0270", "LmjF.04.0470", "LmjF.04.0750",
    "LmjF.04.0950", "LmjF.05.0340", "LmjF.06.0040", "LmjF.06.0410",
    "LmjF.06.0415", "LmjF.06.0570", "LmjF.06.0580", "LmjF.07.0680",
    "LmjF.08.0280", "LmjF.10.0070", "LmjF.11.0760", "LmjF.11.0780",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _org(names: list[str]) -> str:
    """Encode organism list as WDK JSON-array string."""
    return json.dumps(names)


def _go_search_params(organism: str, go_id: str) -> dict[str, str]:
    """Build GenesByGoTerm parameters."""
    return {
        "organism": _org([organism]),
        "go_term_evidence": json.dumps(["Curated", "Computed"]),
        "go_term_slim": "No",
        "go_typeahead": json.dumps([go_id]),
        "go_term": go_id,
    }


def _ec_kinase_params(organism: str, ec_sources: list[str]) -> dict[str, str]:
    """Build GenesByEcNumber parameters for kinases (EC 2.7.11.1)."""
    return {
        "organism": _org([organism]),
        "ec_source": json.dumps(ec_sources),
        "ec_number_pattern": "2.7.11.1",
        "ec_wildcard": "No",
    }


# ---------------------------------------------------------------------------
# Strategy + Experiment definitions
# ---------------------------------------------------------------------------


@dataclass
class SeedDef:
    """Combined strategy + experiment definition."""

    name: str
    description: str
    site_id: str
    step_tree: dict[str, Any]
    positive_controls: list[str]
    negative_controls: list[str]
    record_type: str = "transcript"
    enable_cross_validation: bool = False
    k_folds: int = 5


PF_ORG = "Plasmodium falciparum 3D7"
PF_EC_SOURCES = ["GeneDB", "KEGG_Enzyme", "MPMP"]

TG_ORG = "Toxoplasma gondii ME49"
TG_EC_SOURCES = ["KEGG_Enzyme", "MetabolicPath", "GenBank",
                 "computationally inferred from Orthology", "Uniprot"]

CP_ORG = "Cryptosporidium parvum Iowa II"

LM_ORG = "Leishmania major strain Friedlin"


SEEDS: list[SeedDef] = [
    # -----------------------------------------------------------------------
    # 1) PlasmoDB: EC kinases INTERSECT signal peptide → exported kinases
    # -----------------------------------------------------------------------
    SeedDef(
        name="PF3D7 Exported Kinases",
        description=(
            "Kinases with signal peptides in P. falciparum 3D7. "
            "INTERSECT of EC 2.7.11.1 kinases and predicted signal peptide genes."
        ),
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
        positive_controls=PLASMO_KINASES[:12],
        negative_controls=PLASMO_RIBOSOMAL[:12],
    ),

    # -----------------------------------------------------------------------
    # 2) PlasmoDB: EC kinases MINUS ribosomal proteins
    # -----------------------------------------------------------------------
    SeedDef(
        name="PF3D7 Non-Ribosomal Kinases",
        description=(
            "EC kinases MINUS ribosomal constituent genes. "
            "Uses cross-validation to check robustness."
        ),
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
        positive_controls=PLASMO_KINASES[:15],
        negative_controls=PLASMO_RIBOSOMAL[:15],
        enable_cross_validation=True,
        k_folds=3,
    ),

    # -----------------------------------------------------------------------
    # 3) PlasmoDB: 3-step tree — (EC kinases ∩ signal peptide) ∪ GO kinase
    # -----------------------------------------------------------------------
    SeedDef(
        name="PF3D7 Comprehensive Kinases",
        description=(
            "3-node tree: UNION of (EC kinases INTERSECT signal peptide) "
            "with GO kinase activity for maximum coverage."
        ),
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
        positive_controls=PLASMO_KINASES,
        negative_controls=PLASMO_RIBOSOMAL,
    ),

    # -----------------------------------------------------------------------
    # 4) ToxoDB: GO kinase ∩ EC kinase → high-confidence kinases
    # -----------------------------------------------------------------------
    SeedDef(
        name="TgME49 Confident Kinases",
        description=(
            "INTERSECT GO:0004672 (kinase activity) with EC 2.7.11.1 "
            "in T. gondii ME49 for high-confidence kinases."
        ),
        site_id="toxodb",
        step_tree={
            "id": "combine_kinase",
            "displayName": "GO ∩ EC Kinases",
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
        positive_controls=TOXO_KINASES[:15],
        negative_controls=TOXO_RIBOSOMAL[:15],
    ),

    # -----------------------------------------------------------------------
    # 5) ToxoDB: GO kinase MINUS ribosomal
    # -----------------------------------------------------------------------
    SeedDef(
        name="TgME49 Non-Ribosomal Kinases",
        description=(
            "T. gondii ME49 kinases (GO:0004672) MINUS ribosomal proteins "
            "(GO:0003735). With cross-validation."
        ),
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
        positive_controls=TOXO_KINASES[:15],
        negative_controls=TOXO_RIBOSOMAL[:15],
        enable_cross_validation=True,
        k_folds=3,
    ),

    # -----------------------------------------------------------------------
    # 6) CryptoDB: DNA replication ∪ kinases (broad coverage)
    # -----------------------------------------------------------------------
    SeedDef(
        name="CpIowaII Replication + Kinases",
        description=(
            "UNION of DNA replication (GO:0006260) and kinase activity "
            "(GO:0004672) in C. parvum Iowa II for broad coverage."
        ),
        site_id="cryptodb",
        step_tree={
            "id": "combine_union",
            "displayName": "Replication ∪ Kinases",
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
        positive_controls=CRYPTO_KINASES[:12] + CRYPTO_DNA_REPLICATION[:6],
        negative_controls=CRYPTO_RIBOSOMAL[:15],
    ),

    # -----------------------------------------------------------------------
    # 7) CryptoDB: DNA replication ∩ kinases (overlap)
    # -----------------------------------------------------------------------
    SeedDef(
        name="CpIowaII Replication Kinases",
        description=(
            "INTERSECT of DNA replication (GO:0006260) and kinase activity "
            "(GO:0004672) in C. parvum Iowa II for replication-associated kinases."
        ),
        site_id="cryptodb",
        step_tree={
            "id": "combine_intersect",
            "displayName": "Replication ∩ Kinases",
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
        positive_controls=CRYPTO_KINASES[:12],
        negative_controls=CRYPTO_RIBOSOMAL[:12],
    ),

    # -----------------------------------------------------------------------
    # 8) TriTrypDB: kinases MINUS ribosomal
    # -----------------------------------------------------------------------
    SeedDef(
        name="LmjF Non-Ribosomal Kinases",
        description=(
            "L. major Friedlin kinases (GO:0004672) MINUS ribosomal proteins "
            "(GO:0003735). With cross-validation."
        ),
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
        positive_controls=TRITRYP_KINASES[:15],
        negative_controls=TRITRYP_RIBOSOMAL[:15],
        enable_cross_validation=True,
        k_folds=3,
    ),

    # -----------------------------------------------------------------------
    # 9) TriTrypDB: 3-step — (kinase ∩ signal peptide) ∪ EC kinase
    # -----------------------------------------------------------------------
    SeedDef(
        name="LmjF Comprehensive Kinases",
        description=(
            "3-node tree: UNION of (GO kinase INTERSECT signal peptide) "
            "with EC kinases for broad kinase coverage in L. major."
        ),
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
                "parameters": _ec_kinase_params(LM_ORG, [
                    "GeneDB", "GenBank",
                    "computationally inferred from Orthology",
                ]),
            },
        },
        positive_controls=TRITRYP_KINASES,
        negative_controls=TRITRYP_RIBOSOMAL,
    ),
]


# ---------------------------------------------------------------------------
# SSE stream consumer
# ---------------------------------------------------------------------------


def _consume_sse(response: httpx.Response, name: str) -> dict[str, Any] | None:
    """Read an SSE stream line-by-line and return the final experiment data."""
    result = None
    event_type = ""

    for line in response.iter_lines():
        if not line:
            continue

        if line.startswith("event:"):
            event_type = line[6:].strip()
            continue

        if line.startswith("data:"):
            raw = line[5:].strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = event_type or payload.get("type", "")

            if msg_type == "experiment_progress":
                phase = payload.get("data", payload).get("phase", "")
                detail = payload.get("data", payload).get("detail", "")
                msg = payload.get("data", payload).get("message", "")
                if phase:
                    print(f"    [{phase}] {msg or detail}")

            elif msg_type == "experiment_complete":
                data = payload.get("data", payload)
                exp_id = data.get("id", "?")
                status = data.get("status", "?")
                metrics = data.get("metrics", {})
                f1 = metrics.get("f1Score", data.get("f1Score"))
                sens = metrics.get("sensitivity", data.get("sensitivity"))
                wdk_sid = data.get("wdkStrategyId")
                print(f"    -> Completed: id={exp_id}, F1={f1}, sens={sens}, wdkStrategy={wdk_sid}")
                result = data

            elif msg_type == "experiment_error":
                data = payload.get("data", payload)
                error = data.get("error", "unknown")
                print(f"    !! Error: {error}")

            elif msg_type == "experiment_end":
                break

            event_type = ""

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed strategies + experiments")
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help=f"Base URL for the Pathfinder API (default: {DEFAULT_API_URL})",
    )
    parser.add_argument(
        "--only",
        type=int,
        nargs="*",
        help="Only run seeds at these 1-based indices (e.g. --only 1 3 5)",
    )
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="Don't delete existing test experiments before seeding",
    )
    parser.add_argument(
        "--user-id",
        help="Pathfinder user UUID (for syncing strategies to Chat sidebar)",
    )
    parser.add_argument(
        "--secret-key",
        default=DEFAULT_SECRET_KEY,
        help="API secret key for auth token generation",
    )
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Skip syncing strategies to the local DB after seeding",
    )
    args = parser.parse_args()
    api_url = args.api_url.rstrip("/")

    # Verify API is reachable
    try:
        r = httpx.get(f"{api_url}/api/v1/sites", timeout=10)
        r.raise_for_status()
        sites = r.json()
        print(f"API reachable — {len(sites)} sites configured\n")
    except Exception as exc:
        print(f"Cannot reach API at {api_url}: {exc}", file=sys.stderr)
        sys.exit(1)

    seeds = SEEDS
    if args.only:
        indices = set(args.only)
        seeds = [s for i, s in enumerate(SEEDS, 1) if i in indices]
        print(f"Running {len(seeds)} of {len(SEEDS)} seeds\n")

    results: list[tuple[str, str, dict[str, Any] | None]] = []

    for i, seed in enumerate(seeds, 1):
        print(f"{'='*60}")
        print(f"[{i}/{len(seeds)}] {seed.name}")
        print(f"  Site: {seed.site_id} | CV: {seed.enable_cross_validation}")
        print(f"  Pos: {len(seed.positive_controls)} | Neg: {len(seed.negative_controls)}")
        print(f"{'='*60}")

        # Phase 1: Create WDK strategy
        print("  Creating WDK strategy...")
        try:
            r = httpx.post(
                f"{api_url}/api/v1/experiments/create-strategy",
                json={
                    "siteId": seed.site_id,
                    "recordType": seed.record_type,
                    "name": seed.name,
                    "description": seed.description,
                    "stepTree": seed.step_tree,
                },
                timeout=60,
            )
            r.raise_for_status()
            strategy_data = r.json()
            strategy_id = strategy_data["wdkStrategyId"]
            print(f"  Strategy created: wdkStrategyId={strategy_id}")
        except Exception as exc:
            print(f"  Failed to create strategy: {exc}")
            results.append((seed.name, "strategy_failed", None))
            continue

        # Phase 2: Run experiment via import
        print("  Running experiment (mode=import)...")
        body: dict[str, Any] = {
            "siteId": seed.site_id,
            "recordType": seed.record_type,
            "mode": "import",
            "sourceStrategyId": str(strategy_id),
            "searchName": "",
            "parameters": {},
            "stepTree": seed.step_tree,
            "positiveControls": seed.positive_controls,
            "negativeControls": seed.negative_controls,
            "controlsSearchName": CONTROLS_SEARCH,
            "controlsParamName": CONTROLS_PARAM,
            "controlsValueFormat": "newline",
            "enableCrossValidation": seed.enable_cross_validation,
            "kFolds": seed.k_folds,
            "enrichmentTypes": [],
            "name": seed.name,
            "description": seed.description,
        }

        t0 = time.time()
        try:
            with httpx.stream(
                "POST",
                f"{api_url}/api/v1/experiments/",
                json=body,
                headers={"Accept": "text/event-stream"},
                timeout=httpx.Timeout(connect=30, read=300, write=30, pool=30),
            ) as response:
                if response.status_code != 200:
                    error_body = response.read().decode()
                    print(f"  HTTP {response.status_code}: {error_body[:500]}")
                    results.append((seed.name, "http_error", None))
                    continue
                result = _consume_sse(response, seed.name)

            elapsed = time.time() - t0
            status = "ok" if result else "no_result"
            print(f"  Elapsed: {elapsed:.1f}s\n")
            results.append((seed.name, status, result))

        except Exception as exc:
            elapsed = time.time() - t0
            print(f"  Exception after {elapsed:.1f}s: {exc}\n")
            results.append((seed.name, "exception", None))

    # Sync strategies to the Chat sidebar (requires auth)
    if not args.no_sync:
        sites_used = {s.site_id for s in seeds}
        user_id = args.user_id or _discover_user_id(api_url)
        if user_id:
            token = _create_auth_token(user_id, args.secret_key)
            _sync_strategies_to_sidebar(api_url, sites_used, token)
        else:
            print(
                "\nWarning: Could not determine user ID for sidebar sync. "
                "Strategies will appear after you refresh the Chat page. "
                "Pass --user-id UUID to sync automatically."
            )

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for name, status, data in results:
        if status == "ok" and data:
            metrics = data.get("metrics", {})
            f1 = metrics.get("f1Score", "?")
            sens = metrics.get("sensitivity", "?")
            exp_id = data.get("id", "?")
            mode = data.get("config", {}).get("mode", "?")
            wdk_sid = data.get("wdkStrategyId", "?")
            print(f"  OK   {name}")
            print(f"       id={exp_id} mode={mode} F1={f1} sens={sens} wdk={wdk_sid}")
        else:
            print(f"  FAIL {name} — {status}")

    ok_count = sum(1 for _, s, _ in results if s == "ok")
    print(f"\n{ok_count}/{len(results)} experiments completed successfully")

    # Show importable strategies
    print("\nImportable strategies per site:")
    for site in sorted({s.site_id for s in SEEDS}):
        try:
            r = httpx.get(
                f"{api_url}/api/v1/experiments/importable-strategies",
                params={"siteId": site},
                timeout=10,
            )
            strats = r.json()
            print(f"  {site}: {len(strats)} strategies")
            for s in strats:
                print(f"    {s['wdkStrategyId']}: {s['name']} ({s.get('stepCount','?')} steps)")
        except Exception:
            print(f"  {site}: (failed to list)")

    if ok_count < len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
