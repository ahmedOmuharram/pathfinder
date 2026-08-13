"""OrthoMCL seed strategies and their ortholog-group control sets."""

import json

from pathfinder.services.experiment.seed.types import ControlSetDef, SeedDef

# Protein kinase domain groups, from GroupsByPFamIdOrKeyword on PF00069.
KINASE_GROUPS = [
    "OG7_0000000",  # serine/threonine protein kinase
    "OG7_0000001",  # protein kinase, single-copy orthogroup
    "OG7_0000002",  # protein kinase domain containing
    "OG7_0000003",  # large kinase superfamily
    "OG7_0000004",  # serine/threonine-protein kinase
    "OG7_0000005",  # protein kinase domain containing
    "OG7_0000006",  # NEK kinase family
    "OG7_0000007",  # protein kinase
    "OG7_0000008",  # protein kinase domain containing
]

# Subtilase and peptidase S8 groups, from GroupsByPFamIdOrKeyword on PF00082.
PROTEASE_GROUPS = [
    "OG7_0001372",  # peptidase S8 domain containing
    "OG7_0001373",  # peptidase S8 domain containing
    "OG7_0001375",  # peptidase S8 domain containing
    "OG7_0001376",  # subtilase family
    "OG7_0002302",  # convertase domain containing
    "OG7_0003250",  # subtilisin protease
    "OG7_0006983",  # peptidase S53
    "OG7_0007386",  # tripeptidyl-peptidase 2
]

# ABC transporter groups, from GroupsByPFamIdOrKeyword on PF00005.
TRANSPORTER_GROUPS = [
    "OG7_0000138",  # ABC transporter domain containing
    "OG7_0000139",  # ABC transporter ATP binding
    "OG7_0000140",  # ABC transporter ATP binding
    "OG7_0000141",  # vitamin B12 import ATP binding
    "OG7_0000142",  # iron ABC transporter
    "OG7_0000145",  # hemin import ATP binding
    "OG7_0000147",  # ABC transporter ATP binding
    "OG7_0000148",  # ABC transporter ATP binding
]

# HSP70 groups, from GroupsByPFamIdOrKeyword on PF00012.
HSP_GROUPS = [
    "OG7_0000776",  # heat shock protein
    "OG7_0000777",  # heat shock protein 70
    "OG7_0000778",  # mitochondrial chaperone protein
    "OG7_0000779",  # heat shock protein superfamily
    "OG7_0000780",  # chaperone protein dnaK
    "OG7_0000781",  # chaperone protein dnaK
]

# Apicomplexa groups absent from human and mouse, from GroupsByPhyleticPattern.
APICOMPLEXA_SPECIFIC_GROUPS = [
    "OG7_0000022",  # 3-oxoacyl acyl-carrier-protein reductase
    "OG7_0000049",  # short chain dehydrogenase
    "OG7_0000087",  # maoC domain containing
    "OG7_0000108",  # ATP dependent RNA helicase
    "OG7_0000115",  # RNA helicase
    "OG7_0000380",  # ABC transporter
    "OG7_0000394",  # ABC transporter domain containing
    "OG7_0000414",  # J domain containing protein
    "OG7_0000452",  # thioredoxin domain containing
]

# Groups present in eukaryotes, bacteria, and archaea, from GroupsByPhyleticPattern.
UNIVERSAL_GROUPS = [
    "OG7_0000012",  # conserved across all domains
    "OG7_0000032",  # 3-dehydrogenase
    "OG7_0000034",  # short-chain dehydrogenase/reductase
    "OG7_0000035",  # conserved unknown
    "OG7_0000054",  # short-chain dehydrogenase
    "OG7_0000069",  # dehydrogenase
    "OG7_0000074",  # carrier domain containing
    "OG7_0000085",  # dehydrogenase
]

# Groups spanning many taxa, from GroupsByGenomeCount.
CORE_METABOLISM_GROUPS = [
    "OG7_0000048",  # SDR dehydrogenase/reductase
    "OG7_0000079",  # SDR dehydrogenase/reductase
    "OG7_0000537",  # acyl-CoA synthetase
    "OG7_0000759",  # enoyl-CoA hydratase
    "OG7_0001008",  # RNA helicase
    "OG7_0001201",  # long-chain-fatty-acid-CoA ligase
    "OG7_0001305",  # hexosyltransferase
    "OG7_0001432",  # propionyl-CoA carboxylase
    "OG7_0001471",  # alanine-glyoxylate aminotransferase
    "OG7_0001596",  # nudix hydrolase
]

# Ras and GTPase groups, from GroupsByPFamIdOrKeyword on PF00071.
GTPASE_GROUPS = [
    "OG7_0000131",  # ras superfamily
    "OG7_0001070",  # ras family
    "OG7_0001254",  # GTPase
    "OG7_0003858",  # GTPase domain and ankyrin repeat
    "OG7_0004122",  # mitochondrial rho GTPase
    "OG7_0005954",  # GTP binding nuclear protein
]

# Phosphofructokinase groups, from GroupsByEcNumber on EC 2.7.1.11.
GLYCOLYSIS_GROUPS = [
    "OG7_0002780",  # ATP dependent 6-phosphofructokinase
    "OG7_0002781",  # ATP dependent 6-phosphofructokinase
    "OG7_0002782",  # pyrophosphate-fructose phosphotransferase
    "OG7_0002783",  # phosphofructokinase
    "OG7_0002784",  # ATP dependent 6-phosphofructokinase
    "OG7_0010524",  # 6-phosphofructokinase
]


def _pfam_search_params(
    pfam_id: str, min_proteins: str = "5", min_fraction: str = "0.3"
) -> dict[str, str]:
    """Build the parameters for a PFam-domain group search."""
    return {
        "pfam_id_type_ahead": pfam_id,
        "min_num_proteins": min_proteins,
        "min_fraction_proteins": min_fraction,
    }


def _phyletic_pattern_params(expression: str) -> dict[str, str]:
    """Build the parameters for a phyletic-pattern group search."""
    return {
        "phyletic_expression": expression,
    }


def _ec_search_params(ec_number: str) -> dict[str, str]:
    """Build the parameters for an EC-number group search."""
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
    """Build the parameters for a genome-count group search."""
    return {
        "all_taxon": json.dumps({"min": all_min, "max": all_max}),
        "core_taxon": json.dumps({"min": core_min, "max": core_max}),
        "peripheral_taxon": json.dumps({"min": periph_min, "max": periph_max}),
    }


SEEDS: list[SeedDef] = [
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
