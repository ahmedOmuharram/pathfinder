"""Organism constants and curated gene ID lists for seed strategies.

All gene IDs are real VEuPathDB identifiers used as positive/negative controls
in seeded experiments.
"""

from __future__ import annotations

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
