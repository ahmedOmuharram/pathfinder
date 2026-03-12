"""Seed definitions for MicrosporidiaDB.

Covers Encephalitozoon cuniculi GB-M1 with real gene IDs from MicrosporidiaDB,
biologically meaningful search configurations targeting:
  - Polar tube proteins (unique invasion apparatus)
  - Spore wall components (chitin-rich endospore + protein exospore)
  - Host-dependency transporters (ATP/ADP translocases, nutrient theft)
  - Drug targets (MetAP2/fumagillin, tubulin/albendazole, DHFR/antifolates)
  - Reduced genome essentials (kinases, glycolysis, ubiquitin-proteasome)
  - Intracellular survival (heat shock, GTPases)

Biology context:
  - Microsporidia are obligate intracellular parasites with the smallest known
    eukaryotic genomes (~2.9 Mbp, ~2000 genes for E. cuniculi)
  - They lack canonical mitochondria (have reduced "mitosomes")
  - Unique invasion apparatus: the polar tube (coiled filament)
  - Extreme host dependency: steal ATP/ADP from host via nucleotide translocases
"""

import json

from veupath_chatbot.services.experiment.seed.types import ControlSetDef, SeedDef

# ---------------------------------------------------------------------------
# Organism constants
# ---------------------------------------------------------------------------

EC_ORG = "Encephalitozoon cuniculi GB-M1"
EC_EC_SOURCES = [
    "KEGG_Enzyme",
    "GenBank",
    "computationally inferred from Orthology",
    "Uniprot",
]

# ---------------------------------------------------------------------------
# Gene ID lists (all real VEuPathDB IDs, verified Mar 2026)
# ---------------------------------------------------------------------------

# Polar tube proteins — the unique invasion apparatus of Microsporidia
MICRO_POLAR_TUBE = [
    "ECU06_0250",  # POLAR TUBE PROTEIN PTP1
    "ECU06_0240",  # POLAR TUBE PROTEIN PTP2
]

# Spore wall proteins — chitin-rich endospore + protein exospore
MICRO_SPORE_WALL = [
    "ECU10_1660",  # SPORE WALL PROTEIN 1 (SWP1)
    "ECU01_0820",  # EnP1 - endospore protein
    "ECU01_1270",  # EnP2/SWP3 - endospore protein
    "ECU01_1390",  # CHITIN SYNTHASE 1 - builds endospore chitin layer
    "ECU09_1320",  # ENDOCHITINASE - chitin metabolism
    "ECU11_0510",  # similarity to chitooligosaccharide deacetylase
]

# Transporters — host exploitation machinery
MICRO_TRANSPORTERS = [
    "ECU08_1300",  # ADP/ATP CARRIER PROTEIN 1 (nucleotide translocase)
    "ECU10_0420",  # similarity to ADP/ATP CARRIER PROTEIN
    "ECU10_0520",  # similarity to ATP/ADP CARRIER PROTEIN
    "ECU10_0540",  # similarity to ADP/ATP CARRIER PROTEIN
    "ECU11_1880",  # NUCLEOSIDE TRANSPORTER
    "ECU04_0210",  # GLUCOSE TRANSPORTER TYPE 3
    "ECU07_1100",  # GLUCOSE TRANSPORTER TYPE 1
    "ECU11_1640",  # INORGANIC PHOSPHATE TRANSPORTER
    "ECU05_0160",  # putative AMINOACID TRANSPORTER
    "ECU05_0580",  # putative AMINOACID TRANSPORTER
    "ECU09_1190",  # putative AMINOACID TRANSPORTER
    "ECU11_1510",  # ZINC TRANSPORTER
    "ECU08_0640",  # NICOTINIC ACID TRANSPORTER
    "ECU11_1600",  # similarity to FOLATE TRANSPORTER
    "ECU11_1050",  # OLIGOPEPTIDE TRANSPORTER
]

# ABC transporters — major transporter superfamily in small genome
MICRO_ABC_TRANSPORTERS = [
    "ECU01_0200",  # ABC TRANSPORTER
    "ECU01_1410",  # ABC TRANSPORTER
    "ECU03_0240",  # ABC TRANSPORTER
    "ECU03_0390",  # ABC TRANSPORTER
    "ECU04_0480",  # ABC TRANSPORTER
    "ECU07_0560",  # ABC TRANSPORTER
    "ECU10_1230",  # ABC TRANSPORTER
    "ECU10_1520",  # ABC TRANSPORTER
    "ECU08_0110",  # PROBABLE ABC TRANSPORTER
    "ECU11_1200",  # ABC TRANSPORTER (mitochondrial type)
    "ECU11_1340",  # ABC TRANSPORTER-LIKE PROTEIN
    "ECU05_1190",  # BELONGS TO THE ABC TRANSPORTER SUPERFAMILY
]

# Kinases — signaling (remarkably retained despite genome reduction)
MICRO_KINASES = [
    "ECU01_0740i",  # THYMIDINE KINASE
    "ECU01_1220",  # GUANYLATE KINASE
    "ECU03_1270",  # CYTIDYLATE KINASE
    "ECU04_1220",  # THYMIDYLATE KINASE
    "ECU05_0320",  # PHOSPHOGLYCERATE KINASE
    "ECU09_0640",  # PYRUVATE KINASE
    "ECU09_1780",  # MEVALONATE KINASE
    "ECU08_1480",  # SNF1-RELATED PROTEIN KINASE
    "ECU11_1980",  # CASEINE KINASE 1
    "ECU03_0630",  # CALMODULIN-DEPENDENT PROTEIN KINASE
    "ECU05_0630",  # SER/THR PROTEIN KINASE
    "ECU08_0230",  # CELL DIVISION PROTEIN KINASE
    "ECU08_1620",  # SER/THR PROTEIN KINASE
    "ECU10_0570",  # RIBOSOMAL PROTEIN S6 KINASE
    "ECU01_1320",  # PROTEIN KINASE C (EPSILON TYPE)
    "ECU02_0550",  # SPK1-LIKE SER/THR PROTEIN KINASE
    "ECU05_1510",  # CASEIN KINASE II ALPHA CHAIN
    "ECU07_0360",  # SER/THR/TYR PROTEIN KINASE
    "ECU07_1270",  # MRK1-LIKE SER/THR PROTEIN KINASE
    "ECU08_1920",  # CDK2-LIKE CELL CYCLE PROTEIN KINASE
]

# Ribosomal proteins — translation machinery (used as negative controls)
MICRO_RIBOSOMAL = [
    "ECU01_0310",  # 60S RIBOSOMAL PROTEIN L8
    "ECU01_0920",  # 40S RIBOSOMAL PROTEIN S12
    "ECU02_0610",  # 60S RIBOSOMAL PROTEIN L11
    "ECU02_0770",  # 40S RIBOSOMAL PROTEIN S17
    "ECU02_0800",  # 60S RIBOSOMAL PROTEIN L9
    "ECU02_0810",  # 60S RIBOSOMAL PROTEIN L24
    "ECU03_0230",  # 60S RIBOSOMAL PROTEIN L31
    "ECU03_0310",  # 40S RIBOSOMAL PROTEIN S16
    "ECU03_0320",  # 60S RIBOSOMAL PROTEIN L13
    "ECU03_0650",  # 40S RIBOSOMAL PROTEIN S14
    "ECU03_0710",  # 60S RIBOSOMAL PROTEIN L34
    "ECU03_0950",  # 60S RIBOSOMAL PROTEIN L7
    "ECU03_1220",  # 60S RIBOSOMAL PROTEIN L3
    "ECU03_1490",  # 60S RIBOSOMAL PROTEIN L18
    "ECU04_0140",  # 40S RIBOSOMAL PROTEIN S5
    "ECU04_0330",  # 60S RIBOSOMAL PROTEIN L27
    "ECU04_0640",  # 40S RIBOSOMAL PROTEIN S11
    "ECU04_0740",  # 60S RIBOSOMAL PROTEIN L22
    "ECU05_0670",  # 40S RIBOSOMAL PROTEIN S6
    "ECU05_0900",  # 60S RIBOSOMAL PROTEIN L21
]

# Drug targets — MetAP2 (fumagillin), chitin synthase, tubulin
MICRO_DRUG_TARGETS = [
    "ECU10_0750",  # METHIONINE AMINOPEPTIDASE 2 (fumagillin target)
    "ECU01_1390",  # CHITIN SYNTHASE 1 (nikkomycin target)
    "ECU03_0820i",  # TUBULIN BETA CHAIN (albendazole target)
    "ECU07_1190",  # TUBULIN ALPHA CHAIN (albendazole target)
    "ECU08_0670",  # TUBULIN GAMMA CHAIN
    "ECU01_0170",  # DIHYDROFOLATE REDUCTASE (antifolate target)
    "ECU01_1450",  # DIHYDROFOLATE REDUCTASE
    "ECU08_0080",  # DIHYDROFOLATE REDUCTASE
    "ECU01_0180",  # THYMIDYLATE SYNTHASE
    "ECU01_1430",  # THYMIDYLATE SYNTHASE
    "ECU08_0090",  # THYMIDYLATE SYNTHASE
]

# Heat shock / chaperone proteins — stress response in obligate parasite
MICRO_HEAT_SHOCK = [
    "ECU03_0520",  # HEAT SHOCK RELATED 70kDa PROTEIN (HSP 70 FAMILY)
    "ECU02_1100",  # HEAT-SHOCK PROTEIN HSP90 HOMOLOG
    "ECU11_1830",  # DNAK-LIKE PROTEIN (HSP70 FAMILY)
    "ECU11_1420",  # HSP 101 RELATED PROTEIN
    "ECU02_0690",  # HSB-LIKE CHAPERONE
    "ECU04_0400",  # HEAT SHOCK TRANSCRIPTION FACTOR
    "ECU08_0970",  # HEAT SHOCK TRANSCRIPTION FACTOR HSF
]

# Proteases / peptidases — protein turnover in minimal proteome
MICRO_PROTEASES = [
    "ECU01_1130",  # SUBTILISIN-LIKE SERINE PROTEASE PRECURSOR
    "ECU03_1180",  # SUBTILISIN-RELATED ENDOPEPTIDASE K
    "ECU06_0750",  # ZINC PROTEASE (INSULINASE FAMILY)
    "ECU06_0380",  # ZINC METALLOPEPTIDASE
    "ECU05_1370",  # ZINC METALLOPROTEASE
    "ECU02_1380",  # CAAX PRENYL PROTEASE 1
    "ECU09_1070",  # putative PEPTIDASE
    "ECU10_0750",  # METHIONINE AMINOPEPTIDASE 2
    "ECU01_0140",  # GLUTAMYL-AMINOPEPTIDASE
    "ECU01_1470",  # GLUTAMYL-AMINOPEPTIDASE
    "ECU08_0070",  # GLUTAMYL AMINOPEPTIDASE
]

# Proteasome subunits — ubiquitin-proteasome system
MICRO_PROTEASOME = [
    "ECU02_0340",  # 26S PROTEASOME BETA SUBUNIT, theta chain
    "ECU05_0290",  # 26S PROTEASOME BETA-TYPE SUBUNIT
    "ECU05_1340",  # 26S PROTEASOME ALPHA-TYPE SUBUNIT C9
    "ECU05_1400",  # 26S PROTEASOME ZETA CHAIN
    "ECU07_1040",  # 26S PROTEASOME SUBUNIT ALPHA-4
    "ECU07_1420",  # 20S PROTEASOME ALPHA-TYPE SUBUNIT
    "ECU08_0280",  # PROTEASOME BETA-TYPE COMPONENT C7-1
    "ECU08_1580",  # 20S PROTEASOME COMPONENT C3
    "ECU08_1870",  # 20S PROTEASOME BETA-TYPE SUBUNIT COMPONENT PRE2
    "ECU09_0330",  # PROTEASOME REGULATORY SUBUNIT 8
    "ECU09_0720",  # PROTEASOME BETA-TYPE SUBUNIT (MACROPAIN SUBUNIT PUP1)
    "ECU10_0410",  # 26S PROTEASOME REGULATORY SUBUNIT S5A
    "ECU10_0550",  # PROTEASOME ALPHA SUBUNIT C6
    "ECU10_1450",  # PROTEASOME B-TYPE SUBUNIT DELTA CHAIN
    "ECU11_1670",  # 20S PROTEASOME ALPHA SUBUNIT (C2)
]

# Ubiquitin pathway — essential protein degradation
MICRO_UBIQUITIN = [
    "ECU02_0740i",  # UBIQUITIN
    "ECU03_0930",  # UBIQUITIN-ACTIVATING ENZYME E1
    "ECU01_0940",  # UBIQUITIN CONJUGATING ENZYME E2
    "ECU01_1010",  # UBIQUITIN CONJUGATING ENZYME E2
    "ECU08_0860",  # UBIQUITIN-CONJUGATING ENZYME E2-24KD
    "ECU10_1310i",  # UBIQUITIN CONJUGATING ENZYME E2-17kDa
    "ECU10_1540",  # UBIQUITIN CONJUGATING ENZYME E2-20K
    "ECU11_1990",  # UBIQUITIN CONJUGATING ENZYME E2-16kDa
    "ECU04_0490",  # UBIQUITIN PROTEIN LIGASE E3A
    "ECU10_1380",  # UBIQUITIN LIGASE
    "ECU03_0580",  # UBIQUITIN CARBOXY-TERMINAL HYDROLASE
    "ECU06_0910",  # UBIQUITIN CARBOXYL-TERMINAL HYDROLASE
    "ECU07_0410",  # UBIQUITIN CARBOXYL TERMINAL HYDROLASE
]

# Glycolysis — core energy metabolism (retained despite genome reduction)
MICRO_GLYCOLYSIS = [
    "ECU11_1540",  # HEXOKINASE
    "ECU03_0680",  # 6-PHOSPHOFRUCTOKINASE
    "ECU01_0240",  # FRUCTOSE-BISPHOSPHATE ALDOLASE B
    "ECU07_0800",  # GLYCERALDEHYDE-3-PHOSPHATE DEHYDROGENASE
    "ECU05_0320",  # PHOSPHOGLYCERATE KINASE
    "ECU10_1060",  # PHOSPHOGLYCERATE MUTASE
    "ECU10_1690",  # ENOLASE
    "ECU09_0640",  # PYRUVATE KINASE
]

# Trehalose metabolism — energy storage in spores
MICRO_TREHALOSE = [
    "ECU01_0800",  # ALPHA,ALPHA TREHALOSE-PHOSPHATE SYNTHASE
    "ECU01_0870",  # TREHALOSE-6-PHOSPHATE PHOSPHATASE
    "ECU02_1370",  # ALPHA ALPHA TREHALASE PRECURSOR
]

# Mitosome / mitochondrial remnant proteins
MICRO_MITOSOME = [
    "ECU11_1770",  # NIFS-LIKE PROTEIN (CYSTEINE DESULFURASE) - Fe-S cluster
    "ECU11_0540",  # HSP70-LIKE PROTEIN (MITOCHONDRIAL TYPE)
    "ECU11_1200",  # ABC TRANSPORTER (mitochondrial type)
    "ECU09_0870",  # similarity to MITOCHONDRIAL TRANSLOCASE TOM70
    "ECU10_0870",  # MITOCHONDRIAL GLYCEROL-3-PHOSPHATE DEHYDROGENASE
]

# GTPases / signaling — conserved eukaryotic signaling
MICRO_GTPASES = [
    "ECU08_0240",  # GTP BINDING PROTEIN
    "ECU09_0170",  # GTP-BINDING PROTEIN
    "ECU04_0680",  # RAS-RELATED GTP-BINDING PROTEIN RAB11
    "ECU09_1450",  # RAS-RELATED PROTEIN GTP-BINDING PROTEIN
    "ECU02_0410",  # RAS-LIKE GTP-BINDING PROTEIN (RHO subfamily)
    "ECU04_1560",  # GTP-BINDING NUCLEAR PROTEIN
    "ECU10_0350",  # RAS-LIKE GTP-BINDING PROTEIN OF THE RHO1 FAMILY
    "ECU08_0730",  # RAS-RELATED PROTEIN RAB5
    "ECU03_1430",  # similarity to RAS-LIKE GTP-BINDING PROTEIN YPT1
    "ECU08_1270i",  # DEVELOPMENTALLY REGULATED GTP BINDING PROTEIN
]

# DNA replication licensing factors (MCM family)
MICRO_DNA_REPLICATION = [
    "ECU04_0850",  # DNA REPLICATION LICENSING FACTOR MCM2
    "ECU11_0800",  # DNA REPLICATION LICENSING FACTOR MCM4
    "ECU02_1150",  # DNA REPLICATION LICENSING FACTOR MCM4
    "ECU05_0780",  # DNA REPLICATION LICENSING FACTOR MCM6
    "ECU06_0340",  # DNA REPLICATION LICENSING FACTOR MCM5
    "ECU07_0490",  # DNA REPLICATION LICENSING FACTOR MCM7
    "ECU08_0290",  # DNA REPLICATION LICENSING FACTOR MCM3
    "ECU09_1360",  # DNA REPLICATION LICENSING FACTOR MCM7
    "ECU09_1800",  # DNA REPLICATION HELICASE
    "ECU10_0600",  # DNA REPLICATION FACTOR A PROTEIN 1
]

# Metabolic enzymes (synthases, reductases, dehydrogenases)
MICRO_METABOLIC_ENZYMES = [
    "ECU01_0680",  # THIOREDOXIN REDUCTASE
    "ECU02_0940",  # THIOREDOXIN REDUCTASE
    "ECU01_0970",  # ALDOSE REDUCTASE
    "ECU10_0920",  # RIBONUCLEOSIDE DIPHOSPHATE REDUCTASE
    "ECU10_1720",  # 3-HYDROXY-3-METHYLGLUTARYL CoA REDUCTASE
    "ECU05_0860",  # 6-PHOSPHOGLUCONATE DEHYDROGENASE
    "ECU05_1250",  # CDP-DIACYLGLYCEROL SYNTHASE
    "ECU09_0910",  # DEOXYHYPUSINE SYNTHASE
    "ECU11_0480",  # CTP SYNTHASE
    "ECU05_0240",  # NADPH CYTOCHROME P450 REDUCTASE
    "ECU05_0270",  # GLYCEROL 3-PHOSPHATE DEHYDROGENASE
    "ECU10_0510",  # 3-HYDROXY-3-METHYLGLUTARYL-CoA SYNTHASE 2
    "ECU09_1560",  # PROTEIN DISULFIDE ISOMERASE
    "ECU02_0850",  # PROTEIN DISULFIDE ISOMERASE
]

# ---------------------------------------------------------------------------
# Parameter helpers
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


def _ec_search_params(
    organism: str,
    ec_sources: list[str],
    ec_number: str = "2.7.11.1",
) -> dict[str, str]:
    return {
        "organism": _org([organism]),
        "ec_source": json.dumps(ec_sources),
        "ec_number_pattern": ec_number,
        "ec_wildcard": "No",
    }


def _text_search_params(
    organism: str,
    text: str,
    fields: list[str] | None = None,
) -> dict[str, str]:
    if fields is None:
        fields = ["product"]
    return {
        "text_expression": text,
        "text_search_organism": json.dumps([organism]),
        "document_type": "gene",
        "text_fields": json.dumps(fields),
    }


def _tm_search_params(
    organism: str,
    min_tm: int = 1,
    max_tm: int = 99,
) -> dict[str, str]:
    return {
        "organism": _org([organism]),
        "min_tm": str(min_tm),
        "max_tm": str(max_tm),
    }


def _signal_peptide_params(organism: str) -> dict[str, str]:
    return {"organism": _org([organism])}


def _mw_search_params(
    organism: str,
    min_mw: int,
    max_mw: int,
) -> dict[str, str]:
    return {
        "organism": _org([organism]),
        "min_molecular_weight": str(min_mw),
        "max_molecular_weight": str(max_mw),
    }


# ---------------------------------------------------------------------------
# Seed definitions
# ---------------------------------------------------------------------------

SEEDS: list[SeedDef] = [
    # 1) EcGBM1 Spore Machinery (8 nodes)
    SeedDef(
        name="EcGBM1 Spore Machinery",
        description=(
            "Comprehensive spore biogenesis apparatus in E. cuniculi GB-M1. "
            "Combines polar tube proteins, spore wall proteins, secreted "
            "components, and chitin-related enzymes. Microsporidia spores "
            "contain the unique polar tube (invasion filament) and a chitin-"
            "rich spore wall essential for environmental survival."
        ),
        site_id="microsporidiadb",
        step_tree={
            "id": "root_union_2",
            "displayName": "Spore Machinery Union",
            "operator": "UNION",
            "primaryInput": {
                "id": "mid_union_1",
                "displayName": "Secreted + Chitin Components",
                "operator": "UNION",
                "primaryInput": {
                    "id": "intersect_secreted_spore",
                    "displayName": "Secreted Spore Proteins",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "union_tube_wall",
                        "displayName": "Polar Tube + Spore Wall",
                        "operator": "UNION",
                        "primaryInput": {
                            "id": "leaf_polar_tube",
                            "displayName": "Polar Tube Text",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                EC_ORG,
                                "polar tube",
                                ["product", "Products", "name", "Notes"],
                            ),
                        },
                        "secondaryInput": {
                            "id": "leaf_spore_wall",
                            "displayName": "Spore Wall Text",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                EC_ORG,
                                "spore wall OR spore OR endospore OR exospore",
                                ["product", "Products", "name", "Notes"],
                            ),
                        },
                    },
                    "secondaryInput": {
                        "id": "leaf_signal_peptide_1",
                        "displayName": "Signal Peptide",
                        "searchName": "GenesWithSignalPeptide",
                        "parameters": _signal_peptide_params(EC_ORG),
                    },
                },
                "secondaryInput": {
                    "id": "intersect_chitin_tm",
                    "displayName": "Chitin + TM Domains",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "leaf_chitin_text",
                        "displayName": "Chitin-Related",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            EC_ORG,
                            "chitin OR chitinase OR chitin synthase",
                            ["product", "Products", "Notes"],
                        ),
                    },
                    "secondaryInput": {
                        "id": "leaf_tm_1",
                        "displayName": "Transmembrane (1+)",
                        "searchName": "GenesByTransmembraneDomains",
                        "parameters": _tm_search_params(EC_ORG, 1, 99),
                    },
                },
            },
            "secondaryInput": {
                "id": "intersect_small_secreted",
                "displayName": "Small Secreted (<30kDa)",
                "operator": "INTERSECT",
                "primaryInput": {
                    "id": "leaf_small_mw",
                    "displayName": "Small Proteins (<30kDa)",
                    "searchName": "GenesByMolecularWeight",
                    "parameters": _mw_search_params(EC_ORG, 1000, 30000),
                },
                "secondaryInput": {
                    "id": "leaf_signal_peptide_2",
                    "displayName": "Signal Peptide",
                    "searchName": "GenesWithSignalPeptide",
                    "parameters": _signal_peptide_params(EC_ORG),
                },
            },
        },
        control_set=ControlSetDef(
            name="E. cuniculi Spore Machinery (curated)",
            positive_ids=MICRO_POLAR_TUBE + MICRO_SPORE_WALL,
            negative_ids=MICRO_RIBOSOMAL[:15],
            provenance_notes=(
                "Positives: polar tube proteins (PTP1, PTP2) and spore wall "
                "proteins (SWP1, EnP1, EnP2, chitin synthase, endochitinase). "
                "Negatives: ribosomal structural proteins — housekeeping."
            ),
            tags=["spore", "microsporidium", "seed"],
        ),
    ),
    # 2) EcGBM1 Host Exploitation (7 nodes)
    SeedDef(
        name="EcGBM1 Host Exploitation",
        description=(
            "Host-dependency machinery in E. cuniculi GB-M1. Microsporidia "
            "have lost most biosynthetic pathways and depend on stealing "
            "ATP, amino acids, nucleotides, and other metabolites from the "
            "host cell. This strategy identifies transporters (including "
            "the characteristic ATP/ADP translocases), membrane metabolic "
            "enzymes, and ABC transporters."
        ),
        site_id="microsporidiadb",
        step_tree={
            "id": "root_minus_ribo",
            "displayName": "Host Exploitation - Ribosomal",
            "operator": "MINUS",
            "primaryInput": {
                "id": "union_transport_abc",
                "displayName": "Transporters + ABC",
                "operator": "UNION",
                "primaryInput": {
                    "id": "intersect_transport_tm",
                    "displayName": "Membrane Transporters",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "union_transport_metab",
                        "displayName": "Transporters + Metabolic",
                        "operator": "UNION",
                        "primaryInput": {
                            "id": "leaf_transporter_text",
                            "displayName": "Transporter Text",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                EC_ORG,
                                "transporter OR permease OR carrier",
                            ),
                        },
                        "secondaryInput": {
                            "id": "leaf_metabolic_text",
                            "displayName": "Metabolic Enzymes",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                EC_ORG,
                                "synthase OR reductase OR dehydrogenase",
                            ),
                        },
                    },
                    "secondaryInput": {
                        "id": "leaf_tm_2",
                        "displayName": "Transmembrane (1+)",
                        "searchName": "GenesByTransmembraneDomains",
                        "parameters": _tm_search_params(EC_ORG, 1, 99),
                    },
                },
                "secondaryInput": {
                    "id": "leaf_abc_text",
                    "displayName": "ABC Transporters",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(
                        EC_ORG,
                        '"ABC transporter"',
                    ),
                },
            },
            "secondaryInput": {
                "id": "leaf_ribosomal_go",
                "displayName": "Ribosomal Proteins",
                "searchName": "GenesByGoTerm",
                "parameters": _go_search_params(EC_ORG, "GO:0003735"),
            },
        },
        control_set=ControlSetDef(
            name="E. cuniculi Host Exploitation (curated)",
            positive_ids=MICRO_TRANSPORTERS[:12] + MICRO_ABC_TRANSPORTERS[:5],
            negative_ids=MICRO_RIBOSOMAL[:15],
            provenance_notes=(
                "Positives: ATP/ADP translocases, nutrient transporters, and "
                "ABC transporters — host exploitation machinery. "
                "Negatives: ribosomal structural proteins."
            ),
            tags=["transporter", "microsporidium", "seed"],
        ),
    ),
    # 3) EcGBM1 Drug Targets (6 nodes)
    SeedDef(
        name="EcGBM1 Drug Targets",
        description=(
            "Potential therapeutic targets in E. cuniculi GB-M1. Includes "
            "MetAP2 (fumagillin target), tubulin (albendazole target), "
            "DHFR-TS (antifolate targets), chitin synthase (nikkomycin), "
            "and proteolytic enzymes. Excludes ribosomal proteins and heat "
            "shock chaperones to focus on druggable enzyme targets."
        ),
        site_id="microsporidiadb",
        step_tree={
            "id": "root_minus_housekeeping",
            "displayName": "Drug Targets - Housekeeping",
            "operator": "MINUS",
            "primaryInput": {
                "id": "union_drug_protease",
                "displayName": "Enzymes + Proteolysis",
                "operator": "UNION",
                "primaryInput": {
                    "id": "leaf_drug_text",
                    "displayName": "Drug Target Enzymes",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(
                        EC_ORG,
                        "tubulin OR chitin OR methionine aminopeptidase "
                        "OR dihydrofolate reductase OR thymidylate synthase",
                    ),
                },
                "secondaryInput": {
                    "id": "leaf_proteolysis_go",
                    "displayName": "GO: Proteolysis",
                    "searchName": "GenesByGoTerm",
                    "parameters": _go_search_params(EC_ORG, "GO:0006508"),
                },
            },
            "secondaryInput": {
                "id": "union_ribo_hsp",
                "displayName": "Ribosomal + Heat Shock",
                "operator": "UNION",
                "primaryInput": {
                    "id": "leaf_ribosomal_text",
                    "displayName": "Ribosomal Proteins",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(
                        EC_ORG,
                        '"ribosomal protein"',
                    ),
                },
                "secondaryInput": {
                    "id": "leaf_hsp_text",
                    "displayName": "Heat Shock Proteins",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(
                        EC_ORG,
                        "heat shock OR chaperone OR hsp",
                    ),
                },
            },
        },
        control_set=ControlSetDef(
            name="E. cuniculi Drug Targets (curated)",
            positive_ids=MICRO_DRUG_TARGETS,
            negative_ids=MICRO_RIBOSOMAL[:15],
            provenance_notes=(
                "Positives: MetAP2, tubulins, DHFR, thymidylate synthase, "
                "chitin synthase — validated drug targets. "
                "Negatives: ribosomal structural proteins."
            ),
            tags=["drug-target", "microsporidium", "seed"],
        ),
    ),
    # 4) EcGBM1 Reduced Genome Essentials (8 nodes)
    SeedDef(
        name="EcGBM1 Reduced Genome Essentials",
        description=(
            "Essential retained functions in E. cuniculi's extremely reduced "
            "genome (~2000 genes). Despite losing most metabolic pathways, "
            "Microsporidia retain: protein kinases for signaling, glycolytic "
            "enzymes for energy, and the ubiquitin-proteasome system for "
            "protein turnover. This strategy identifies high-confidence "
            "essential enzymes via intersections with GO/EC annotations."
        ),
        site_id="microsporidiadb",
        step_tree={
            "id": "root_minus_ribo_2",
            "displayName": "Essentials - Ribosomal",
            "operator": "MINUS",
            "primaryInput": {
                "id": "union_all_essential",
                "displayName": "All Essential Enzymes",
                "operator": "UNION",
                "primaryInput": {
                    "id": "union_kinase_glycolysis",
                    "displayName": "Kinases + Glycolysis",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "intersect_kinase_go",
                        "displayName": "Confirmed Kinases",
                        "operator": "INTERSECT",
                        "primaryInput": {
                            "id": "leaf_kinase_text",
                            "displayName": "Kinase Text",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                EC_ORG,
                                "kinase",
                            ),
                        },
                        "secondaryInput": {
                            "id": "leaf_kinase_go",
                            "displayName": "GO: Kinase Activity",
                            "searchName": "GenesByGoTerm",
                            "parameters": _go_search_params(EC_ORG, "GO:0004672"),
                        },
                    },
                    "secondaryInput": {
                        "id": "intersect_glycolysis_ec",
                        "displayName": "Glycolytic Enzymes",
                        "operator": "INTERSECT",
                        "primaryInput": {
                            "id": "leaf_glycolysis_text",
                            "displayName": "Glycolysis Text",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                EC_ORG,
                                "hexokinase OR phosphofructokinase OR aldolase "
                                "OR enolase OR pyruvate OR phosphoglycerate "
                                "OR glyceraldehyde",
                            ),
                        },
                        "secondaryInput": {
                            "id": "leaf_ec_transferase",
                            "displayName": "EC: Transferases",
                            "searchName": "GenesByEcNumber",
                            "parameters": _ec_search_params(
                                EC_ORG, EC_EC_SOURCES, "2.7.1.1"
                            ),
                        },
                    },
                },
                "secondaryInput": {
                    "id": "intersect_ubiq_proteo",
                    "displayName": "Ubiquitin-Proteasome",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "leaf_ubiquitin_text",
                        "displayName": "Ubiquitin Text",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            EC_ORG,
                            "ubiquitin OR proteasome",
                        ),
                    },
                    "secondaryInput": {
                        "id": "leaf_proteolysis_go_2",
                        "displayName": "GO: Proteolysis",
                        "searchName": "GenesByGoTerm",
                        "parameters": _go_search_params(EC_ORG, "GO:0006508"),
                    },
                },
            },
            "secondaryInput": {
                "id": "leaf_ribosomal_go_2",
                "displayName": "Ribosomal Proteins",
                "searchName": "GenesByGoTerm",
                "parameters": _go_search_params(EC_ORG, "GO:0003735"),
            },
        },
        control_set=ControlSetDef(
            name="E. cuniculi Reduced Genome Essentials (curated)",
            positive_ids=(
                MICRO_KINASES[:10] + MICRO_GLYCOLYSIS[:5] + MICRO_UBIQUITIN[:5]
            ),
            negative_ids=MICRO_RIBOSOMAL,
            provenance_notes=(
                "Positives: kinases, glycolytic enzymes, and ubiquitin pathway "
                "components — essential functions retained in minimal genome. "
                "Negatives: ribosomal structural proteins."
            ),
            tags=["essential", "microsporidium", "seed"],
        ),
    ),
    # 5) EcGBM1 Intracellular Survival (5 nodes)
    SeedDef(
        name="EcGBM1 Intracellular Survival",
        description=(
            "Genes enabling intracellular survival in E. cuniculi GB-M1. "
            "Combines stress response (heat shock proteins, chaperones) "
            "with GTPase signaling (Rab, Ras, Rho family) that are either "
            "secreted or membrane-associated. These proteins mediate "
            "parasite adaptation to the intracellular niche."
        ),
        site_id="microsporidiadb",
        step_tree={
            "id": "root_minus_ribo_3",
            "displayName": "Survival - Ribosomal",
            "operator": "MINUS",
            "primaryInput": {
                "id": "intersect_survival_membrane",
                "displayName": "Membrane Survival",
                "operator": "INTERSECT",
                "primaryInput": {
                    "id": "union_hsp_gtpase",
                    "displayName": "HSP + GTPase",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "leaf_hsp_text_2",
                        "displayName": "Heat Shock / Chaperone",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            EC_ORG,
                            "heat shock OR chaperone OR hsp OR dnaK",
                        ),
                    },
                    "secondaryInput": {
                        "id": "leaf_gtpase_text",
                        "displayName": "GTPase / Ras / Rab",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            EC_ORG,
                            'GTPase OR "GTP-binding" OR "GTP binding" OR Ras OR Rab',
                        ),
                    },
                },
                "secondaryInput": {
                    "id": "leaf_tm_3",
                    "displayName": "Transmembrane (1+)",
                    "searchName": "GenesByTransmembraneDomains",
                    "parameters": _tm_search_params(EC_ORG, 1, 99),
                },
            },
            "secondaryInput": {
                "id": "leaf_ribosomal_go_3",
                "displayName": "Ribosomal Proteins",
                "searchName": "GenesByGoTerm",
                "parameters": _go_search_params(EC_ORG, "GO:0003735"),
            },
        },
        control_set=ControlSetDef(
            name="E. cuniculi Intracellular Survival (curated)",
            positive_ids=MICRO_HEAT_SHOCK[:5] + MICRO_GTPASES[:5],
            negative_ids=MICRO_RIBOSOMAL[:15],
            provenance_notes=(
                "Positives: heat shock proteins and GTPases — stress response "
                "and signaling for intracellular adaptation. "
                "Negatives: ribosomal structural proteins."
            ),
            tags=["survival", "microsporidium", "seed"],
        ),
    ),
]
