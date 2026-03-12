"""Seed definitions for OrthoMCL.

Ortholog group strategies covering conserved kinase orthologs, apicomplexa-specific
groups, core metabolism, pathogen-enriched proteases, and stress response signaling.
All group IDs (OG7_XXXXXXX) verified against live OrthoMCL API (Mar 2026).
"""

import json

from veupath_chatbot.services.experiment.seed.types import ControlSetDef, SeedDef

# ---------------------------------------------------------------------------
# Group ID lists — verified against live API
# ---------------------------------------------------------------------------

# Protein Kinase domain groups (PF00069) — kinases across all taxa
# Source: GroupsByPFamIdOrKeyword with pfam_id_type_ahead=PF00069, min_fraction=0.3
KINASE_GROUPS = [
    "OG7_0000000",  # 177 members — serine/threonine protein kinase
    "OG7_0000001",  # 20 members — protein kinase (single-copy orthogroup)
    "OG7_0000002",  # 114 members — protein kinase domain containing
    "OG7_0000003",  # 9521 members — large kinase superfamily
    "OG7_0000004",  # 1538 members — serine/threonine-protein kinase
    "OG7_0000005",  # 21 members — protein kinase domain containing
    "OG7_0000006",  # 44 members — NEK kinase family
    "OG7_0000007",  # 1985 members — protein kinase
    "OG7_0000008",  # 1943 members — protein kinase domain containing
]

# Protease/peptidase groups (PF00082 = Subtilase/Peptidase S8)
# Source: GroupsByPFamIdOrKeyword with pfam_id_type_ahead=PF00082
PROTEASE_GROUPS = [
    "OG7_0001372",  # 627 members — peptidase_S8 domain containing
    "OG7_0001373",  # 39 members — peptidase_S8 domain containing
    "OG7_0001375",  # 737 members — peptidase_S8 domain containing
    "OG7_0001376",  # 2623 members — subtilase family
    "OG7_0002302",  # 1368 members — convertase domain containing
    "OG7_0003250",  # 372 members — subtilisin protease
    "OG7_0006983",  # 1133 members — peptidase S53
    "OG7_0007386",  # 304 members — tripeptidyl-peptidase 2
]

# ABC transporter groups (PF00005)
# Source: GroupsByPFamIdOrKeyword with pfam_id_type_ahead=PF00005
TRANSPORTER_GROUPS = [
    "OG7_0000138",  # 43 members — ABC transporter domain containing
    "OG7_0000139",  # 5 members — ABC transporter ATP binding
    "OG7_0000140",  # 5 members — ABC transporter ATP binding
    "OG7_0000141",  # 8 members — vitamin B12 import ATP binding
    "OG7_0000142",  # 23 members — iron ABC transporter
    "OG7_0000145",  # 19 members — hemin import ATP binding
    "OG7_0000147",  # 6 members — ABC transporter ATP binding
    "OG7_0000148",  # 6 members — ABC transporter ATP binding
]

# Heat shock protein groups (PF00012 = HSP70)
# Source: GroupsByPFamIdOrKeyword with pfam_id_type_ahead=PF00012
HSP_GROUPS = [
    "OG7_0000776",  # 992 members — heat shock protein
    "OG7_0000777",  # 159 members — heat shock protein 70
    "OG7_0000778",  # 58 members — mitochondrial chaperone protein
    "OG7_0000779",  # 6840 members — heat shock protein superfamily
    "OG7_0000780",  # 90 members — chaperone protein dnaK
    "OG7_0000781",  # 28 members — chaperone protein dnaK
]

# Apicomplexa-specific groups (APIC>=2, absent in human and mouse)
# Source: GroupsByPhyleticPattern with "APIC>=2T AND hsap=0 AND mmus=0"
APICOMPLEXA_SPECIFIC_GROUPS = [
    "OG7_0000022",  # 197 members — 3-oxoacyl acyl-carrier-protein reductase
    "OG7_0000049",  # 90 members — short chain dehydrogenase
    "OG7_0000087",  # 365 members — maoC domain containing
    "OG7_0000108",  # 77 members — ATP dependent RNA helicase
    "OG7_0000115",  # 641 members — RNA helicase
    "OG7_0000380",  # 375 members — ABC transporter
    "OG7_0000394",  # 155 members — ABC transporter domain containing
    "OG7_0000414",  # 414 members — J domain containing protein
    "OG7_0000452",  # 118 members — thioredoxin domain containing
]

# Universally conserved groups (EUKA>=10, BACT>=5, ARCH>=3)
# Source: GroupsByPhyleticPattern with "EUKA>=10T AND BACT>=5T AND ARCH>=3T"
UNIVERSAL_GROUPS = [
    "OG7_0000012",  # 148 members — conserved across all domains
    "OG7_0000032",  # 469 members — 3-dehydrogenase
    "OG7_0000034",  # 43 members — short-chain dehydrogenase/reductase
    "OG7_0000035",  # 177 members — conserved unknown
    "OG7_0000054",  # 86 members — short-chain dehydrogenase
    "OG7_0000069",  # 41 members — dehydrogenase
    "OG7_0000074",  # 219 members — carrier domain containing
    "OG7_0000085",  # 3283 members — dehydrogenase
]

# Highly conserved across many taxa (>100 taxa, >50 core taxa)
# Source: GroupsByGenomeCount with all_taxon min=100
CORE_METABOLISM_GROUPS = [
    "OG7_0000048",  # 268 members — SDR dehydrogenase/reductase
    "OG7_0000079",  # 469 members — SDR dehydrogenase/reductase
    "OG7_0000537",  # 232 members — acyl-CoA synthetase
    "OG7_0000759",  # 241 members — enoyl-CoA hydratase
    "OG7_0001008",  # 678 members — RNA helicase
    "OG7_0001201",  # 473 members — long-chain-fatty-acid-CoA ligase
    "OG7_0001305",  # 1832 members — hexosyltransferase
    "OG7_0001432",  # 213 members — propionyl-CoA carboxylase
    "OG7_0001471",  # 384 members — alanine-glyoxylate aminotransferase
    "OG7_0001596",  # 197 members — nudix hydrolase
]

# GTPase/Ras family groups (PF00071)
# Source: GroupsByPFamIdOrKeyword with pfam_id_type_ahead=PF00071
GTPASE_GROUPS = [
    "OG7_0000131",  # 16791 members — ras superfamily
    "OG7_0001070",  # 4490 members — ras family
    "OG7_0001254",  # 4259 members — GTPase
    "OG7_0003858",  # 450 members — GTPase domain/ankyrin repeat
    "OG7_0004122",  # 753 members — mitochondrial rho GTPase
    "OG7_0005954",  # 921 members — GTP binding nuclear protein
]

# Phosphofructokinase groups (EC 2.7.1.11) — glycolysis
# Source: GroupsByEcNumber with ec_number_type_ahead=2.7.1.11
GLYCOLYSIS_GROUPS = [
    "OG7_0002780",  # 725 members — ATP dependent 6-phosphofructokinase
    "OG7_0002781",  # 273 members — ATP dependent 6-phosphofructokinase
    "OG7_0002782",  # 10 members — pyrophosphate-fructose phosphotransferase
    "OG7_0002783",  # 49 members — phosphofructokinase
    "OG7_0002784",  # 9 members — ATP dependent 6-phosphofructokinase
    "OG7_0010524",  # 388 members — 6-phosphofructokinase
]


# ---------------------------------------------------------------------------
# Parameter helpers
# ---------------------------------------------------------------------------


def _pfam_search_params(
    pfam_id: str, min_proteins: str = "5", min_fraction: str = "0.3"
) -> dict[str, str]:
    """Build GroupsByPFamIdOrKeyword parameters."""
    return {
        "pfam_id_type_ahead": pfam_id,
        "min_num_proteins": min_proteins,
        "min_fraction_proteins": min_fraction,
    }


def _phyletic_pattern_params(expression: str) -> dict[str, str]:
    """Build GroupsByPhyleticPattern parameters."""
    return {
        "phyletic_expression": expression,
    }


def _ec_search_params(ec_number: str) -> dict[str, str]:
    """Build GroupsByEcNumber parameters."""
    return {
        "ec_number_type_ahead": ec_number,
        "ec_wildcard": "N/A",
    }


def _genome_count_params(
    all_min: str,
    all_max: str,
    core_min: str = "0",
    core_max: str = "100000",
    periph_min: str = "0",
    periph_max: str = "100000",
) -> dict[str, str]:
    """Build GroupsByGenomeCount parameters."""
    return {
        "all_taxon": json.dumps({"min": all_min, "max": all_max}),
        "core_taxon": json.dumps({"min": core_min, "max": core_max}),
        "peripheral_taxon": json.dumps({"min": periph_min, "max": periph_max}),
    }


# ---------------------------------------------------------------------------
# Seed definitions
# ---------------------------------------------------------------------------


SEEDS: list[SeedDef] = [
    # -------------------------------------------------------------------
    # 1) Conserved Kinase Orthologs — kinase domain groups INTERSECT
    #    universally conserved groups (present across euk/bact/arch)
    # -------------------------------------------------------------------
    SeedDef(
        name="Conserved Kinase Orthologs",
        description=(
            "Ortholog groups containing the protein kinase domain (PF00069) "
            "INTERSECT with groups conserved across eukaryotes, bacteria, and "
            "archaea. Identifies the most ancient, universally retained kinases."
        ),
        site_id="orthomcl",
        step_tree={
            "id": "combine_1",
            "displayName": "Universal Kinase Groups",
            "operator": "INTERSECT",
            "primaryInput": {
                "id": "step_kinase_pfam",
                "displayName": "Protein Kinase Domain (PF00069)",
                "searchName": "GroupsByPFamIdOrKeyword",
                "parameters": _pfam_search_params("PF00069", "5", "0.3"),
            },
            "secondaryInput": {
                "id": "step_universal",
                "displayName": "Universally Conserved Groups",
                "searchName": "GroupsByPhyleticPattern",
                "parameters": _phyletic_pattern_params(
                    "EUKA>=10T AND BACT>=5T AND ARCH>=3T"
                ),
            },
        },
        control_set=ControlSetDef(
            name="Kinase vs Protease Groups",
            positive_ids=KINASE_GROUPS[:6],
            negative_ids=PROTEASE_GROUPS[:6],
            provenance_notes=(
                "Positives: protein kinase domain (PF00069) ortholog groups. "
                "Negatives: peptidase S8 domain (PF00082) groups — structurally "
                "distinct enzyme families."
            ),
            tags=["kinase", "orthomcl", "seed"],
        ),
        record_type="group",
    ),
    # -------------------------------------------------------------------
    # 2) Apicomplexan-Specific Ortholog Groups — present in Apicomplexa
    #    but ABSENT in humans and mice (potential drug targets)
    # -------------------------------------------------------------------
    SeedDef(
        name="Apicomplexan-Specific Groups",
        description=(
            "Ortholog groups present in at least 3 Apicomplexa species but "
            "completely absent from human (hsap) and mouse (mmus). These "
            "lineage-specific groups represent potential drug targets for "
            "malaria and toxoplasmosis since they lack mammalian orthologs."
        ),
        site_id="orthomcl",
        step_tree={
            "id": "step_apicomplexa_only",
            "displayName": "Apicomplexa-Specific (No Human/Mouse)",
            "searchName": "GroupsByPhyleticPattern",
            "parameters": _phyletic_pattern_params("APIC>=3T AND hsap=0 AND mmus=0"),
        },
        control_set=ControlSetDef(
            name="Apicomplexa-Specific vs Universal",
            positive_ids=APICOMPLEXA_SPECIFIC_GROUPS[:6],
            negative_ids=UNIVERSAL_GROUPS[:6],
            provenance_notes=(
                "Positives: Apicomplexa-specific groups absent in mammals. "
                "Negatives: universally conserved groups present in eukaryotes, "
                "bacteria, and archaea."
            ),
            tags=["apicomplexa", "drug-target", "orthomcl", "seed"],
        ),
        record_type="group",
    ),
    # -------------------------------------------------------------------
    # 3) Core Metabolism Groups — highly conserved across >100 taxa,
    #    INTERSECT with specific EC number (glycolysis enzymes)
    # -------------------------------------------------------------------
    SeedDef(
        name="Core Metabolism Groups",
        description=(
            "3-node strategy: UNION of (groups conserved across >100 taxa "
            "INTERSECT glycolysis enzyme groups EC 2.7.1.11) with universally "
            "conserved enoyl-CoA hydratase/lipid metabolism groups. Captures "
            "the most fundamental metabolic enzyme orthologs shared across "
            "all domains of life."
        ),
        site_id="orthomcl",
        step_tree={
            "id": "root_union",
            "displayName": "Core Metabolism",
            "operator": "UNION",
            "primaryInput": {
                "id": "intersect_glycolysis",
                "displayName": "Conserved Glycolysis Enzymes",
                "operator": "INTERSECT",
                "primaryInput": {
                    "id": "leaf_conserved_taxa",
                    "displayName": "Groups in >100 Taxa",
                    "searchName": "GroupsByGenomeCount",
                    "parameters": _genome_count_params(
                        all_min="100",
                        all_max="200",
                        core_min="50",
                        core_max="200",
                    ),
                },
                "secondaryInput": {
                    "id": "leaf_glycolysis_ec",
                    "displayName": "Phosphofructokinase (EC 2.7.1.11)",
                    "searchName": "GroupsByEcNumber",
                    "parameters": _ec_search_params("2.7.1.11"),
                },
            },
            "secondaryInput": {
                "id": "leaf_universal_phyletic",
                "displayName": "Universal Conservation Pattern",
                "searchName": "GroupsByPhyleticPattern",
                "parameters": _phyletic_pattern_params(
                    "EUKA>=10T AND BACT>=5T AND ARCH>=3T"
                ),
            },
        },
        control_set=ControlSetDef(
            name="Core Metabolism vs Apicomplexa-Specific",
            positive_ids=CORE_METABOLISM_GROUPS[:6],
            negative_ids=APICOMPLEXA_SPECIFIC_GROUPS[:6],
            provenance_notes=(
                "Positives: highly conserved metabolic groups present in >100 taxa. "
                "Negatives: Apicomplexa-specific groups absent in mammals — "
                "lineage-restricted, not universally conserved."
            ),
            tags=["metabolism", "glycolysis", "orthomcl", "seed"],
        ),
        record_type="group",
    ),
    # -------------------------------------------------------------------
    # 4) Drug Target Discovery — protease groups MINUS universally
    #    conserved groups (pathogen-enriched proteases)
    # -------------------------------------------------------------------
    SeedDef(
        name="Pathogen-Enriched Proteases",
        description=(
            "Protease ortholog groups (Subtilase/Peptidase S8 domain PF00082) "
            "MINUS universally conserved groups. The remaining groups are "
            "enriched in pathogens and parasites, representing potential "
            "drug targets that can be inhibited without affecting host enzymes."
        ),
        site_id="orthomcl",
        step_tree={
            "id": "combine_minus",
            "displayName": "Pathogen-Enriched Proteases",
            "operator": "MINUS",
            "primaryInput": {
                "id": "step_protease_pfam",
                "displayName": "Subtilase/S8 Proteases (PF00082)",
                "searchName": "GroupsByPFamIdOrKeyword",
                "parameters": _pfam_search_params("PF00082", "3", "0.2"),
            },
            "secondaryInput": {
                "id": "step_universal_groups",
                "displayName": "Universal Groups (All Domains of Life)",
                "searchName": "GroupsByPhyleticPattern",
                "parameters": _phyletic_pattern_params(
                    "EUKA>=10T AND BACT>=5T AND ARCH>=3T"
                ),
            },
        },
        control_set=ControlSetDef(
            name="Protease vs Universal Groups",
            positive_ids=PROTEASE_GROUPS[:6],
            negative_ids=UNIVERSAL_GROUPS[:6],
            provenance_notes=(
                "Positives: peptidase S8 domain (PF00082) ortholog groups. "
                "Negatives: universally conserved groups — housekeeping enzymes "
                "present across all domains of life."
            ),
            tags=["protease", "drug-target", "orthomcl", "seed"],
        ),
        record_type="group",
    ),
    # -------------------------------------------------------------------
    # 5) Stress Response Orthologs — HSP70 UNION GTPase signaling,
    #    representing conserved stress and signaling networks
    # -------------------------------------------------------------------
    SeedDef(
        name="Stress Response and Signaling Orthologs",
        description=(
            "UNION of heat shock protein 70 groups (PF00012) and Ras/GTPase "
            "signaling groups (PF00071). Captures the interplay between "
            "protein folding stress responses and signal transduction "
            "across eukaryotes — key for understanding pathogen adaptation."
        ),
        site_id="orthomcl",
        step_tree={
            "id": "combine_union",
            "displayName": "HSP70 + GTPase Signaling",
            "operator": "UNION",
            "primaryInput": {
                "id": "step_hsp70",
                "displayName": "HSP70 Chaperones (PF00012)",
                "searchName": "GroupsByPFamIdOrKeyword",
                "parameters": _pfam_search_params("PF00012", "3", "0.2"),
            },
            "secondaryInput": {
                "id": "step_gtpase",
                "displayName": "Ras/GTPase Family (PF00071)",
                "searchName": "GroupsByPFamIdOrKeyword",
                "parameters": _pfam_search_params("PF00071", "5", "0.3"),
            },
        },
        control_set=ControlSetDef(
            name="HSP + GTPase vs Transporter Groups",
            positive_ids=HSP_GROUPS[:4] + GTPASE_GROUPS[:4],
            negative_ids=TRANSPORTER_GROUPS[:6],
            provenance_notes=(
                "Positives: HSP70 chaperones (PF00012) and Ras/GTPase (PF00071) "
                "groups — stress response and signaling. "
                "Negatives: ABC transporter (PF00005) groups — membrane transport, "
                "functionally distinct from stress/signaling."
            ),
            tags=["stress", "signaling", "orthomcl", "seed"],
        ),
        record_type="group",
    ),
]
