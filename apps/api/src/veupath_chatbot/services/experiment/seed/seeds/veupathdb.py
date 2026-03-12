"""Seed definitions for VEuPathDB Portal.

Cross-species comparative genomics covering three organisms from different
component databases:
  1. Plasmodium vivax Sal-1 (PlasmoDB)
  2. Neospora caninum Liverpool (ToxoDB)
  3. Trypanosoma cruzi CL Brener Esmeraldo-like (TriTrypDB)

All gene IDs verified against https://veupathdb.org/veupathdb/service
"""

import json

from veupath_chatbot.services.experiment.seed.types import ControlSetDef, SeedDef

# ---------------------------------------------------------------------------
# Organism constants
# ---------------------------------------------------------------------------

PV_ORG = "Plasmodium vivax Sal-1"
NC_ORG = "Neospora caninum Liverpool"
TC_ORG = "Trypanosoma cruzi CL Brener Esmeraldo-like"

# ---------------------------------------------------------------------------
# Gene ID lists — verified against live VEuPathDB API
# ---------------------------------------------------------------------------

# P. vivax Sal-1 — Invasion and Surface Proteins
PVIVAX_INVASION_SURFACE = [
    # Duffy Binding Protein — THE key invasion ligand
    "PVX_110810",  # Duffy receptor precursor
    # Reticulocyte Binding Proteins
    "PVX_098585",  # reticulocyte binding protein 1a
    "PVX_098582",  # reticulocyte binding protein 1b
    "PVX_121920",  # reticulocyte binding protein 2a
    "PVX_094255",  # reticulocyte binding protein 2b
    "PVX_090325",  # reticulocyte binding protein 2c
    "PVX_090330",  # reticulocyte binding protein 2 precursor
    "PVX_101585",  # reticulocyte-binding protein 2 precursor (pseudogene)
    "PVX_101590",  # reticulocyte-binding protein 2 (RBP2), like
    "PVX_101495",  # reticulocyte binding protein 3 (pseudogene)
    # Merozoite Surface Proteins
    "PVX_099980",  # merozoite surface protein 1
    "PVX_099975",  # merozoite surface protein 1 paralog
    "PVX_097670",  # merozoite surface protein 3
    "PVX_097675",  # merozoite surface protein 3
    "PVX_097680",  # merozoite surface protein 3
    "PVX_097685",  # merozoite surface protein 3
    "PVX_097690",  # merozoite surface protein 3
    "PVX_097695",  # merozoite surface protein 3
    "PVX_097700",  # merozoite surface protein 3
    "PVX_097705",  # merozoite surface protein 3
    "PVX_097710",  # merozoite surface protein 3
    "PVX_097720",  # merozoite surface protein 3
    "PVX_097725",  # merozoite surface protein 3
    "PVX_003775",  # merozoite surface protein 4
    "PVX_003770",  # merozoite surface protein 5
    "PVX_082645",  # merozoite surface protein 7 (MSP7)
    "PVX_082650",  # merozoite surface protein 7 (MSP7)
    "PVX_082655",  # merozoite surface protein 7 (MSP7)
    "PVX_082665",  # merozoite surface protein 7 (MSP7)
    "PVX_082670",  # merozoite surface protein 7 (MSP7)
    "PVX_082675",  # merozoite surface protein 7 (MSP7)
    "PVX_082680",  # merozoite surface protein 7 (MSP7)
    "PVX_082685",  # merozoite surface protein 7 (MSP7)
    "PVX_082690",  # merozoite surface protein 7 (MSP7)
    "PVX_082695",  # merozoite surface protein 7 (MSP7)
    "PVX_082700",  # merozoite surface protein 7 (MSP7)
    "PVX_097625",  # merozoite surface protein 8
    "PVX_124060",  # merozoite surface protein-9 precursor
    "PVX_114145",  # merozoite surface protein 10
    # Apical Membrane Antigen
    "PVX_092275",  # apical membrane antigen 1
    # Rhoptry proteins
    "PVX_001725",  # rhoptry neck protein 12
    "PVX_002790",  # rhoptry neck protein 6
    "PVX_080657",  # apical rhoptry neck protein
    "PVX_085930",  # rhoptry-associated protein 1
    "PVX_089530",  # rhoptry neck protein 5
    "PVX_089700",  # armadillo-domain containing rhoptry protein
    "PVX_091434",  # rhoptry neck protein 4
    "PVX_096245",  # rhoptry-associated leucine zipper-like protein 1
    "PVX_097590",  # rhoptry-associated protein 2
    "PVX_098712",  # high molecular weight rhoptry protein 3
    "PVX_099930",  # high molecular weight rhoptry protein 2
    "PVX_101485",  # rhoptry neck protein 3
    "PVX_113800",  # rhoptry protein ROP14
    "PVX_115280",  # rhoptry protein
    "PVX_117120",  # rhoptry protein
    "PVX_117880",  # rhoptry neck protein 2
    "PVX_087885",  # rhoptry-associated membrane antigen
    # Circumsporozoite and TRAP
    "PVX_119355",  # circumsporozoite (CS) protein
    "PVX_086150",  # circumsporozoite protein
    "PVX_091700",  # circumsporozoite-related antigen
    "PVX_095475",  # circumsporozoite- and TRAP-related protein
    "PVX_082735",  # thrombospondin-related anonymous protein
    "PVX_002900",  # secreted protein with altered thrombospondin repeat
    "PVX_123575",  # thrombospondin-related apical membrane protein
    # Sporozoite invasion
    "PVX_000815",  # sporozoite invasion-associated protein 1
    "PVX_088860",  # sporozoite invasion-associated protein 2
    # Other surface/secreted
    "PVX_000945",  # apical sushi protein
    "PVX_095435",  # microneme associated antigen
    "PVX_088910",  # GPI-anchored micronemal antigen
    "PVX_000810",  # perforin-like protein 1
    "PVX_000995",  # 6-cysteine protein
    "PVX_001015",  # 6-cysteine protein
    "PVX_001020",  # 6-cysteine protein
    "PVX_001025",  # 6-cysteine protein
    "PVX_000975",  # liver specific protein 2
]

# P. vivax Sal-1 — Drug Targets and Metabolic Enzymes
PVIVAX_DRUG_TARGETS = [
    # DHFR — primary antimalarial target
    "PVX_089950",  # bifunctional dihydrofolate reductase-thymidylate synthase
    # Plasmepsin
    "PVX_086040",  # plasmepsin IV
    # Calcium-dependent protein kinases
    "PVX_002665",  # calcium-dependent protein kinase 1
    "PVX_002805",  # calcium-dependent protein kinase 4
    "PVX_000555",  # calcium-dependent protein kinase 4
    "PVX_087765",  # calcium-dependent protein kinase 3
    "PVX_085300",  # calcium-dependent protein kinase
    "PVX_082820",  # calcium-dependent protein kinase
    "PVX_091755",  # calcium-dependent protein kinase 6
    "PVX_091770",  # calcium-dependent protein kinase 7
    # cGMP-dependent protein kinase
    "PVX_084705",  # cGMP-dependent protein kinase
    # MAP kinases
    "PVX_084965",  # mitogen-activated protein kinase 1
    "PVX_091340",  # mitogen-activated protein kinase 2
    # Other kinases
    "PVX_086975",  # cAMP-dependent protein kinase catalytic subunit
    "PVX_089980",  # cdc2-related protein kinase 1
    "PVX_094935",  # cyclin dependent kinase 7 (cdk7)
    "PVX_091095",  # casein kinase 2 alpha subunit
    "PVX_092440",  # casein kinase 1
    "PVX_082785",  # CDK-related protein kinase 6
    # Phosphatases
    "PVX_085730",  # serine/threonine protein phosphatase PP1
    "PVX_082945",  # Ser/Thr protein phosphatase family protein
    "PVX_093605",  # serine/threonine protein phosphatase 2B catalytic subunit A
    # Heat shock proteins
    "PVX_087950",  # heat shock protein 86
    "PVX_089425",  # heat shock 70 kDa protein
    "PVX_091470",  # heat shock protein 101
    "PVX_091545",  # heat shock protein 90
    "PVX_092310",  # heat shock protein 70
    "PVX_095000",  # heat shock protein 60
    "PVX_083105",  # heat shock protein 110
    "PVX_087970",  # heat shock protein 110
    "PVX_081840",  # heat shock protein
    # Protease drug targets
    "PVX_085585",  # cysteine protease ATG4
    "PVX_092460",  # subtilisin-like protease 2
    "PVX_091350",  # rhomboid protease ROM1
    "PVX_083160",  # rhomboid protease ROM6
    "PVX_085890",  # rhomboid protease ROM8
    "PVX_080490",  # rhomboid protease ROM9
    "PVX_088955",  # rhomboid protease ROM3
    "PVX_085030",  # aspartyl protease
    "PVX_088125",  # aspartyl protease
    # Transport drug targets
    "PVX_087980",  # chloroquine resistance transporter
    "PVX_080100",  # multidrug resistance protein 1
    "PVX_118100",  # multidrug resistance protein 2
    "PVX_097025",  # multidrug resistance-associated protein 1
    "PVX_124085",  # multidrug resistance-associated protein 2
    # Metabolic enzymes
    "PVX_086340",  # choline kinase
    "PVX_091845",  # ethanolamine kinase
    "PVX_085450",  # pantothenate kinase
    "PVX_083470",  # glycerol kinase
    "PVX_080650",  # inositol-3-phosphate synthase
    "PVX_083185",  # isocitrate dehydrogenase [NADP], mitochondrial
]

# P. vivax Sal-1 — VIR Variant Surface and Exported Proteins
PVIVAX_VARIANT_SURFACE = [
    # VIR proteins
    "PVX_001635",  # VIR protein
    "PVX_001640",  # VIR protein
    "PVX_003490",  # VIR protein
    "PVX_003500",  # VIR protein
    "PVX_004495",  # VIR protein
    "PVX_004503",  # VIR protein
    "PVX_004530",  # VIR protein
    "PVX_004537",  # VIR protein
    "PVX_005055",  # VIR protein
    "PVX_005057",  # VIR protein
    "PVX_005058",  # VIR protein
    "PVX_005065",  # VIR protein
    "PVX_086845",  # VIR protein
    "PVX_086863",  # VIR protein
    "PVX_086865",  # VIR protein
    "PVX_086893",  # VIR protein
    "PVX_086895",  # VIR protein
    "PVX_088775",  # VIR protein
    "PVX_088795",  # VIR protein
    "PVX_088797",  # VIR protein
    "PVX_088798",  # VIR protein
    "PVX_090295",  # VIR protein
    "PVX_090310",  # VIR protein
    "PVX_093730",  # VIR protein
    "PVX_093735",  # VIR protein
    "PVX_094250",  # VIR protein
    "PVX_095990",  # VIR protein
    "PVX_096001",  # VIR protein
    "PVX_096003",  # VIR protein
    "PVX_096004",  # VIR protein
    "PVX_096965",  # VIR protein
    "PVX_096975",  # VIR protein
    "PVX_096987",  # VIR protein
    "PVX_097542",  # VIR protein
    "PVX_101503",  # VIR protein
    "PVX_101617",  # VIR protein
    "PVX_101630",  # VIR protein
    "PVX_105205",  # VIR protein
    "PVX_110822",  # VIR protein
    "PVX_113220",  # VIR protein
    "PVX_115490",  # VIR protein
    "PVX_119205",  # VIR protein
    "PVX_119215",  # VIR protein
    "PVX_121862",  # VIR protein
    "PVX_124708",  # VIR protein
    "PVX_124725",  # VIR protein
    # Tryptophan-rich antigens
    "PVX_002500",  # tryptophan-rich antigen (Pv-fam-a)
    "PVX_083550",  # tryptophan-rich antigen (Pv-fam-a)
    "PVX_088810",  # tryptophan-rich antigen (Pv-fam-a)
    "PVX_088820",  # tryptophan-rich antigen (Pv-fam-a)
    "PVX_088825",  # tryptophan-rich antigen (Pv-fam-a)
    "PVX_088850",  # tryptophan-rich antigen (Pv-fam-a)
    # Serine-repeat antigens (SERA)
    "PVX_003790",  # serine-repeat antigen (SERA)
    "PVX_003795",  # serine-repeat antigen (SERA)
    "PVX_003800",  # serine-repeat antigen (SERA)
    "PVX_003810",  # serine-repeat antigen 5 (SERA)
    "PVX_003820",  # serine-repeat antigen 4 (SERA)
    "PVX_003825",  # serine-repeat antigen 4 (SERA)
    "PVX_003830",  # serine-repeat antigen 5 (SERA)
    "PVX_003835",  # serine-repeat antigen 1 (SERA)
    "PVX_003840",  # serine-repeat antigen 3 (SERA)
    "PVX_003845",  # serine-repeat antigen 4 (SERA)
    "PVX_003850",  # serine-repeat antigen 2 (SERA)
    # Exported proteins
    "PVX_000745",  # erythrocyte vesicle protein 1
    "PVX_090150",  # erythrocyte membrane-associated antigen
    "PVX_118682",  # erythrocyte membrane protein 3
    "PVX_084420",  # 41K blood stage antigen precursor 41-3
    "PVX_000930",  # sexual stage antigen s16
    # PHIST proteins
    "PVX_001675",  # Phist protein (Pf-fam-b)
    "PVX_001680",  # Phist protein (Pf-fam-b)
    "PVX_001685",  # Phist protein (Pf-fam-b)
    "PVX_001690",  # Phist protein (Pf-fam-b)
    "PVX_001695",  # Phist protein (Pf-fam-b)
    "PVX_001700",  # Phist protein (Pf-fam-b)
    "PVX_001705",  # Phist protein (Pf-fam-b)
    "PVX_001710",  # Phist protein (Pf-fam-b)
    # Transporters
    "PVX_003665",  # hexose transporter
    "PVX_081595",  # nucleoside transporter 4
    "PVX_083260",  # nucleoside transporter 1
    "PVX_088920",  # folate transporter 1
    "PVX_003745",  # pantothenate transporter
    "PVX_082915",  # ABC transporter B family member 5
    "PVX_083495",  # ABC transporter B family member 6
    "PVX_084521",  # ABC transporter B family member 7
    "PVX_085205",  # ABC transporter G family member 2
    "PVX_001715",  # early transcribed membrane protein (ETRAMP)
]

# N. caninum Liverpool — SRS Surface Proteins and Antigens
NCANINUM_SURFACE_SRS = [
    # SRS domain proteins — large family
    "NCLIV_002220",  # srs domain-containing protein
    "NCLIV_002230",  # srs domain-containing protein
    "NCLIV_002240",  # srs domain-containing protein
    "NCLIV_002250",  # srs domain-containing protein
    "NCLIV_002260",  # srs domain-containing protein
    "NCLIV_003360",  # srs domain-containing protein
    "NCLIV_004401",  # srs domain-containing protein
    "NCLIV_004410",  # srs domain-containing protein
    "NCLIV_004411",  # srs domain-containing protein
    "NCLIV_004420",  # srs domain-containing protein
    "NCLIV_004421",  # srs domain-containing protein
    "NCLIV_004430",  # srs domain-containing protein
    "NCLIV_004431",  # srs domain-containing protein
    "NCLIV_004432",  # srs domain-containing protein
    "NCLIV_004440",  # srs domain-containing protein
    "NCLIV_004441",  # srs domain-containing protein
    "NCLIV_004450",  # srs domain-containing protein
    "NCLIV_004460",  # srs domain-containing protein
    "NCLIV_004471",  # srs domain-containing protein
    "NCLIV_009900",  # srs domain-containing protein
    "NCLIV_009910",  # srs domain-containing protein
    "NCLIV_009920",  # srs domain-containing protein
    "NCLIV_009930",  # srs domain-containing protein
    "NCLIV_009940",  # srs domain-containing protein
    "NCLIV_009950",  # srs domain-containing protein
    "NCLIV_009960",  # srs domain-containing protein
    "NCLIV_009970",  # srs domain-containing protein
    "NCLIV_009980",  # srs domain-containing protein
    "NCLIV_009990",  # srs domain-containing protein
    "NCLIV_010000",  # srs domain-containing protein
    "NCLIV_010040",  # srs domain-containing protein
    "NCLIV_010050",  # srs domain-containing protein
    "NCLIV_010060",  # srs domain-containing protein
    "NCLIV_010070",  # srs domain-containing protein
    "NCLIV_010080",  # srs domain-containing protein
    "NCLIV_010710",  # srs domain-containing protein
    "NCLIV_010720",  # srs domain-containing protein
    "NCLIV_010730",  # srs domain-containing protein
    "NCLIV_011305",  # srs domain-containing protein
    "NCLIV_012675",  # SRS domain-containing protein
    "NCLIV_012701",  # SRS domain-containing protein
    "NCLIV_012710",  # SRS domain-containing protein
    "NCLIV_012711",  # SRS domain-containing protein
    "NCLIV_012712",  # SRS domain-containing protein
    "NCLIV_014520",  # SRS domain-containing protein
    "NCLIV_014530",  # SRS domain-containing protein
    "NCLIV_015870",  # SRS domain-containing protein
    "NCLIV_019570",  # SRS domain-containing protein
    "NCLIV_019580",  # SRS domain-containing protein
    "NCLIV_020080",  # SRS domain-containing protein
    "NCLIV_020090",  # SRS domain-containing protein
    "NCLIV_020091",  # SRS domain-containing protein
    "NCLIV_020092",  # SRS domain-containing protein
    "NCLIV_020093",  # SRS domain-containing protein
    "NCLIV_020100",  # SRS domain-containing protein
    "NCLIV_020110",  # SRS domain-containing protein
    "NCLIV_023620",  # SRS domain-containing protein
    "NCLIV_025181",  # SRS domain-containing protein
    "NCLIV_025185",  # SRS domain-containing protein
    "NCLIV_027260",  # SRS domain-containing protein
    "NCLIV_027670",  # SRS domain-containing protein
    "NCLIV_027680",  # SRS domain-containing protein
    "NCLIV_027690",  # SRS domain-containing protein
    "NCLIV_027700",  # SRS domain-containing protein
    "NCLIV_027960",  # SRS domain-containing protein
    "NCLIV_033230",  # SRS domain-containing protein
    "NCLIV_033250",  # SRS domain-containing protein
    "NCLIV_034380",  # SRS domain-containing protein
    "NCLIV_034381",  # SRS domain-containing protein
    "NCLIV_034390",  # SRS domain-containing protein
    "NCLIV_034391",  # SRS domain-containing protein
    "NCLIV_034400",  # SRS domain-containing protein
    "NCLIV_034410",  # SRS domain-containing protein
    "NCLIV_034411",  # SRS domain-containing protein
    "NCLIV_034420",  # SRS domain-containing protein
    "NCLIV_034430",  # SRS domain-containing protein
    "NCLIV_034431",  # SRS domain-containing protein
    "NCLIV_034440",  # SRS domain-containing protein
    "NCLIV_034730",  # SRS domain-containing protein
    "NCLIV_034731",  # SRS domain-containing protein
    "NCLIV_034750",  # SRS domain-containing protein
    "NCLIV_035180",  # SRS domain-containing protein
    "NCLIV_035375",  # SRS domain-containing protein
    "NCLIV_035760",  # SRS domain-containing protein
    "NCLIV_035770",  # SRS domain-containing protein
    # Bradyzoite-specific surface
    "NCLIV_010030",  # Bradyzoite surface protein BSR4
    "NCLIV_027470",  # putative bradyzoite antigen
    # Other surface/antigens
    "NCLIV_015930",  # putative cell surface glycoprotein
    "NCLIV_026560",  # Cell wall surface anchor family protein
    "NCLIV_041350",  # putative ATP-binding surface antigen
    "NCLIV_037730",  # putative 41-3 antigen
    "NCLIV_012480",  # putative 200 kDa antigen p200
    "NCLIV_023180",  # 200 kDa antigen p200, related
    "NCLIV_039670",  # putative 200 kDa antigen p200
    "NCLIV_030890",  # putative high molecular mass nuclear antigen
    "NCLIV_011660",  # putative C protein immunoglobulin-A-binding beta antigen
    "NCLIV_004020",  # tryptophan-rich antigen (Pv-fam-a), related
]

# N. caninum Liverpool — Invasion Machinery (subset for controls)
NCANINUM_INVASION = [
    "NCLIV_043270",  # putative microneme protein MIC1
    "NCLIV_010600",  # putative microneme protein MIC3
    "NCLIV_002940",  # putative microneme protein MIC4
    "NCLIV_038120",  # Microneme protein 5 (Precursor), related
    "NCLIV_061760",  # putative microneme protein MIC6
    "NCLIV_020720",  # putative microneme protein MIC11
    "NCLIV_028680",  # putative apical membrane antigen 1
    "NCLIV_005560",  # putative dense-granule antigen DG32
    "NCLIV_007770",  # putative Rhoptry kinase family protein
    "NCLIV_065640",  # putative Rhoptry kinase family protein
    "NCLIV_034870",  # MAC/Perforin domain containing protein
    "NCLIV_005250",  # putative subtilisin-like serine protease
    "NCLIV_010280",  # putative serine protease/subtilase
    "NCLIV_016510",  # putative subtilase family serine protease
    "NCLIV_020890",  # putative subtilase family serine protease
    "NCLIV_031420",  # putative subtilase family serine protease
    "NCLIV_038200",  # putative subtilase family serine protease
    "NCLIV_050140",  # putative subtilisin-like protease
    "NCLIV_050220",  # putative subtilase family serine protease
    "NCLIV_064430",  # putative subtilase family serine protease
]

# N. caninum Liverpool — Kinases and Signaling (subset for controls)
NCANINUM_KINASES = [
    "NCLIV_002090",  # putative CAM kinase, CDPK family
    "NCLIV_012150",  # putative CAM kinase, CDPK family
    "NCLIV_016600",  # putative CAM kinase, CDPK family
    "NCLIV_036330",  # putative CAM kinase, CDPK family
    "NCLIV_017560",  # Calcium-dependent protein kinase 2
    "NCLIV_011980",  # calmodulin-like domain protein kinase
    "NCLIV_025300",  # putative CAM kinase
    "NCLIV_028350",  # putative CAM kinase
    "NCLIV_002760",  # putative CMGC kinase, MAPK family
    "NCLIV_032840",  # Mitogen-activated protein kinase 2
    "NCLIV_005080",  # putative CMGC kinase, MAPK family
    "NCLIV_014140",  # putative AGC kinase
    "NCLIV_020150",  # putative AGC kinase
    "NCLIV_029900",  # AGC family protein kinase
    "NCLIV_033400",  # putative AGC kinase
    "NCLIV_035070",  # putative AGC kinase
    "NCLIV_026680",  # Protein kinase AKT
    "NCLIV_000010",  # putative heat shock protein 90
    "NCLIV_033950",  # Heat shock protein 70
    "NCLIV_032780",  # putative small heat shock protein 20
]

# T. cruzi CL Brener — Trans-Sialidase Superfamily
TCRUZI_TRANSSIALIDASE = [
    # Active trans-sialidases
    "TcCLB.398265.9",  # trans-sialidase
    "TcCLB.402919.10",  # trans-sialidase
    "TcCLB.418185.70",  # trans-sialidase, Group II
    "TcCLB.422867.10",  # trans-sialidase, Group II
    "TcCLB.426675.9",  # trans-sialidase
    "TcCLB.432995.9",  # trans-sialidase
    "TcCLB.433733.10",  # trans-sialidase
    "TcCLB.434545.10",  # trans-sialidase
    "TcCLB.447899.10",  # trans-sialidase
    "TcCLB.452475.10",  # trans-sialidase, Group V
    "TcCLB.463279.20",  # trans-sialidase, Group II
    "TcCLB.463323.10",  # trans-sialidase, Group II
    # Non-Esmeraldo-like haplotype
    "TcCLB.398477.10",  # trans-sialidase, Group II
    "TcCLB.404431.10",  # trans-sialidase
    "TcCLB.410199.30",  # trans-sialidase, Group VI
    "TcCLB.432997.10",  # trans-sialidase
    "TcCLB.435665.10",  # trans-sialidase
    "TcCLB.448329.10",  # trans-sialidase
    "TcCLB.459061.10",  # trans-sialidase
    # Pseudogenes
    "TcCLB.398009.20",  # trans-sialidase (pseudogene)
    "TcCLB.406725.10",  # trans-sialidase (pseudogene)
    "TcCLB.410241.20",  # trans-sialidase (pseudogene)
    "TcCLB.410275.18",  # trans-sialidase (pseudogene)
    "TcCLB.424171.10",  # trans-sialidase (pseudogene)
    "TcCLB.425597.10",  # trans-sialidase (pseudogene)
    "TcCLB.450965.10",  # trans-sialidase (pseudogene)
    "TcCLB.453767.20",  # trans-sialidase (pseudogene)
    "TcCLB.454391.10",  # trans-sialidase (pseudogene)
    "TcCLB.454403.10",  # trans-sialidase (pseudogene)
    "TcCLB.458369.10",  # trans-sialidase (pseudogene)
    "TcCLB.460625.9",  # trans-sialidase (pseudogene)
    "TcCLB.402449.10",  # trans-sialidase (pseudogene)
    "TcCLB.404845.10",  # trans-sialidase (pseudogene)
    "TcCLB.409407.10",  # trans-sialidase (pseudogene)
    "TcCLB.410337.10",  # trans-sialidase (pseudogene)
    "TcCLB.410923.40",  # trans-sialidase (pseudogene)
    "TcCLB.413893.10",  # trans-sialidase (pseudogene)
    "TcCLB.432629.10",  # trans-sialidase (pseudogene)
    "TcCLB.439991.10",  # trans-sialidase (pseudogene)
    "TcCLB.469113.10",  # trans-sialidase (pseudogene)
    "TcCLB.477471.10",  # trans-sialidase (pseudogene)
    "TcCLB.478071.10",  # trans-sialidase (pseudogene)
    # Fragments
    "TcCLB.399173.10",  # trans-sialidase (fragment)
    "TcCLB.399685.10",  # trans-sialidase (fragment)
    "TcCLB.401183.10",  # trans-sialidase (fragment)
    "TcCLB.401961.10",  # trans-sialidase (fragment)
    "TcCLB.403031.10",  # trans-sialidase (fragment)
    "TcCLB.403481.10",  # trans-sialidase (fragment)
    "TcCLB.403869.10",  # trans-sialidase (fragment)
    "TcCLB.404455.10",  # trans-sialidase (fragment)
    "TcCLB.406115.10",  # trans-sialidase (fragment)
    "TcCLB.406929.10",  # trans-sialidase (fragment)
    "TcCLB.408445.10",  # trans-sialidase (fragment)
    "TcCLB.409625.10",  # trans-sialidase (fragment)
    "TcCLB.410269.10",  # trans-sialidase (fragment)
    "TcCLB.410339.10",  # trans-sialidase (fragment)
    "TcCLB.413293.9",  # trans-sialidase (fragment)
    "TcCLB.413409.10",  # trans-sialidase (fragment)
    "TcCLB.416619.10",  # trans-sialidase (fragment)
    "TcCLB.421951.10",  # trans-sialidase (fragment)
    "TcCLB.427013.10",  # trans-sialidase (fragment)
    "TcCLB.430567.10",  # trans-sialidase (fragment)
    "TcCLB.435051.10",  # trans-sialidase (fragment)
    "TcCLB.440083.10",  # trans-sialidase (fragment)
    "TcCLB.440219.10",  # trans-sialidase (fragment)
    "TcCLB.440379.10",  # trans-sialidase (fragment)
    "TcCLB.443899.10",  # trans-sialidase (fragment)
    "TcCLB.446785.10",  # trans-sialidase (fragment)
    "TcCLB.448653.10",  # trans-sialidase (fragment)
    "TcCLB.450963.10",  # trans-sialidase (fragment)
    "TcCLB.451951.10",  # trans-sialidase (fragment)
    "TcCLB.457113.10",  # trans-sialidase (fragment)
    "TcCLB.457449.10",  # trans-sialidase (fragment)
    "TcCLB.457977.10",  # trans-sialidase (fragment)
]

# T. cruzi CL Brener — Mucins, MASP, GP63, Amastin Surface Proteins
TCRUZI_MUCIN_MASP_SURFACE = [
    # Mucins
    "TcCLB.413133.10",  # mucin TcMUCII (pseudogene)
    "TcCLB.415273.5",  # mucin-like glycoprotein (pseudogene)
    "TcCLB.415273.9",  # mucin TcMUCII (pseudogene)
    "TcCLB.416605.20",  # mucin TcMUCII (pseudogene)
    "TcCLB.445557.10",  # mucin TcMUCII
    "TcCLB.448661.20",  # mucin TcMUCII
    "TcCLB.430603.20",  # mucin TcMUCII
    "TcCLB.442801.10",  # mucin TcMUCII
    "TcCLB.463955.10",  # mucin TcMUCII
    "TcCLB.503417.30",  # mucin TcMUCII
    "TcCLB.413859.10",  # mucin TcMUC (fragment)
    # MASP
    "TcCLB.397923.10",  # MASP (fragment)
    "TcCLB.410275.9",  # MASP (fragment)
    "TcCLB.416605.10",  # MASP, subgroup S104
    "TcCLB.416605.30",  # MASP (fragment)
    "TcCLB.421555.9",  # MASP (fragment)
    "TcCLB.421621.50",  # MASP
    "TcCLB.424499.10",  # MASP
    "TcCLB.429251.10",  # MASP
    "TcCLB.432443.10",  # MASP
    "TcCLB.448661.10",  # MASP (fragment)
    "TcCLB.453767.50",  # MASP
    "TcCLB.412419.10",  # MASP (pseudogene)
    "TcCLB.408825.5",  # MASP (fragment)
    "TcCLB.430603.10",  # MASP (pseudogene)
    "TcCLB.433237.20",  # MASP (pseudogene)
    "TcCLB.442801.5",  # MASP (pseudogene)
    "TcCLB.445783.10",  # MASP (pseudogene)
    "TcCLB.457979.10",  # MASP, subgroup S043
    "TcCLB.463955.20",  # MASP (fragment)
    # GP63 surface protease
    "TcCLB.447135.10",  # surface protease GP63
    "TcCLB.421057.20",  # surface protease GP63 (fragment)
    "TcCLB.503633.30",  # surface protease GP63
    "TcCLB.504397.20",  # surface protease GP63
    "TcCLB.504669.30",  # surface protease GP63
    "TcCLB.504755.10",  # surface protease GP63
    "TcCLB.504801.20",  # surface protease GP63
    "TcCLB.505567.20",  # surface protease GP63
    "TcCLB.505615.10",  # surface protease GP63
    "TcCLB.506015.20",  # surface protease GP63
    "TcCLB.507357.10",  # surface protease GP63
    "TcCLB.508071.50",  # surface protease GP63
    # Amastin
    "TcCLB.507485.10",  # Amastin surface glycoprotein
    "TcCLB.507485.20",  # Amastin surface glycoprotein
    "TcCLB.507485.30",  # Amastin surface glycoprotein
    "TcCLB.507485.40",  # Amastin surface glycoprotein
    "TcCLB.507485.45",  # Amastin surface glycoprotein
    "TcCLB.507485.130",  # amastin
    "TcCLB.507485.150",  # amastin
    "TcCLB.507673.50",  # Amastin surface glycoprotein
    "TcCLB.507673.60",  # Amastin surface glycoprotein
    "TcCLB.507673.70",  # Amastin surface glycoprotein
    "TcCLB.507739.120",  # amastin
    "TcCLB.509965.390",  # amastin
    "TcCLB.509965.394",  # amastin
    "TcCLB.511071.40",  # amastin
]

# T. cruzi CL Brener — Drug Targets and Essential Enzymes
TCRUZI_DRUG_TARGETS = [
    # Cruzipain
    "TcCLB.507603.270",  # cruzipain precursor
    # Trypanothione pathway
    "TcCLB.484299.10",  # trypanothione reductase
    "TcCLB.504507.5",  # trypanothione reductase (fragment)
    "TcCLB.504427.10",  # trypanothione synthetase
    "TcCLB.509099.50",  # trypanothione synthetase
    "TcCLB.504147.280",  # trypanothione synthetase-like protein
    "TcCLB.503899.119",  # trypanothione/tryparedoxin dependent peroxidase 2
    # Sterol biosynthesis
    "TcCLB.505683.10",  # sterol 24-c-methyltransferase
    "TcCLB.507129.30",  # C-14 sterol reductase
    "TcCLB.507709.90",  # sterol C-24 reductase
    # Heat shock proteins
    "TcCLB.503811.10",  # heat shock protein 90
    "TcCLB.506591.4",  # heat shock protein 90
    "TcCLB.503899.10",  # heat shock 70 kDa protein
    "TcCLB.506941.280",  # heat shock 70 kDa protein, mitochondrial
    "TcCLB.507713.30",  # heat shock protein 85
    "TcCLB.507831.60",  # heat shock protein 110
    "TcCLB.504153.310",  # heat shock protein
    "TcCLB.506925.470",  # heat shock protein DNAJ
    "TcCLB.507641.280",  # chaperonin HSP60, mitochondrial
    "TcCLB.507641.290",  # heat shock protein 60
]

# T. cruzi CL Brener — Flagellar (subset for controls)
TCRUZI_FLAGELLAR = [
    "TcCLB.411235.9",  # alpha tubulin
    "TcCLB.506563.40",  # beta tubulin
    "TcCLB.503969.10",  # tubulin delta chain
    "TcCLB.509967.160",  # epsilon tubulin
    "TcCLB.511423.90",  # zeta tubulin
    "TcCLB.511867.190",  # tubulin gamma chain
    "TcCLB.511215.119",  # Paraflagellar rod protein 2
    "TcCLB.506755.20",  # paraflagellar rod component
    "TcCLB.507711.20",  # paraflagellar rod component
    "TcCLB.509099.30",  # paraflagellar rod protein 5
    "TcCLB.510353.30",  # paraflagellar rod component par4
    "TcCLB.508387.90",  # paraflagellar rod protein
    "TcCLB.506221.70",  # Paraflagellar Rod Proteome Component 9
    "TcCLB.509537.50",  # Flagellar Member 1
    "TcCLB.508837.80",  # Flagellar Member 3
    "TcCLB.510773.100",  # Flagellar Member 4
    "TcCLB.510749.50",  # Flagellar Member 5
    "TcCLB.503643.20",  # Flagellar Member 6
    "TcCLB.509067.60",  # Flagellar Member 7
    "TcCLB.504075.3",  # calmodulin
]


# ---------------------------------------------------------------------------
# Parameter helpers
# ---------------------------------------------------------------------------


def _org(names: list[str]) -> str:
    """Encode organism list as WDK JSON-array string."""
    return json.dumps(names)


def _text_search_params(organism: str, expression: str) -> dict[str, str]:
    """Build GenesByText parameters searching product field."""
    return {
        "text_expression": expression,
        "text_fields": "product",
        "text_search_organism": organism,
        "document_type": "gene",
    }


# ---------------------------------------------------------------------------
# Strategy Definitions (6 strategies, converted from flat step format)
# ---------------------------------------------------------------------------

SEEDS: list[SeedDef] = [
    # ===================================================================
    # 1) PvSal1 Reticulocyte Invasion Drug Targets (9 nodes)
    # ===================================================================
    SeedDef(
        name="PvSal1 Reticulocyte Invasion Drug Targets",
        description=(
            "Identifies vivax-specific drug targets at the invasion-host "
            "interface. Starts from reticulocyte/Duffy binding proteins, "
            "intersects with kinase regulators, unions with rhoptry/microneme "
            "and drug resistance genes, subtracts housekeeping."
        ),
        site_id="veupathdb",
        step_tree={
            "id": "step_9",
            "displayName": "PvSal1 Invasion-Specific Drug Targets",
            "operator": "MINUS",
            "primaryInput": {
                "id": "step_7",
                "displayName": "Invasion + Resistance Genes",
                "operator": "UNION",
                "primaryInput": {
                    "id": "step_5",
                    "displayName": "Invasion + Secretory",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "step_3",
                        "displayName": "All Invasion Machinery",
                        "operator": "UNION",
                        "primaryInput": {
                            "id": "step_1",
                            "displayName": "Invasion Ligands (DBP, RBP, MSP, AMA1)",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                PV_ORG,
                                '"reticulocyte binding" OR "Duffy" OR "merozoite surface" OR "apical membrane"',
                            ),
                        },
                        "secondaryInput": {
                            "id": "step_2",
                            "displayName": "Invasion Regulators (CDPKs, PKG, ROMs)",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                PV_ORG,
                                '"calcium-dependent protein kinase" OR "cGMP-dependent protein kinase" OR "rhomboid protease"',
                            ),
                        },
                    },
                    "secondaryInput": {
                        "id": "step_4",
                        "displayName": "Secretory Organelle Proteins",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            PV_ORG, "rhoptry OR microneme"
                        ),
                    },
                },
                "secondaryInput": {
                    "id": "step_6",
                    "displayName": "Drug Resistance Markers",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(
                        PV_ORG,
                        '"chloroquine resistance" OR "multidrug resistance" OR "dihydrofolate reductase"',
                    ),
                },
            },
            "secondaryInput": {
                "id": "step_8",
                "displayName": "Housekeeping Genes (to subtract)",
                "searchName": "GenesByText",
                "parameters": _text_search_params(
                    PV_ORG,
                    'ribosomal OR "tRNA ligase" OR "ATP synthase" OR histone',
                ),
            },
        },
        control_set=ControlSetDef(
            name="P. vivax Invasion vs Variant Surface",
            positive_ids=PVIVAX_INVASION_SURFACE[:30],
            negative_ids=PVIVAX_VARIANT_SURFACE[:30],
            provenance_notes=(
                "Positives: merozoite surface proteins, reticulocyte binding "
                "proteins, rhoptry/microneme proteins — invasion machinery. "
                "Negatives: VIR variant surface proteins — immune evasion, "
                "not invasion drug targets."
            ),
            tags=["invasion", "drug-target", "pvivax", "veupathdb", "seed"],
        ),
    ),
    # ===================================================================
    # 2) NcLiv Host Cell Invasion Toolkit (10 nodes)
    # ===================================================================
    SeedDef(
        name="NcLiv Host Cell Invasion Toolkit",
        description=(
            "Comprehensive N. caninum invasion gene set: micronemes, "
            "rhoptry kinases, SRS surface receptors, subtilisin proteases, "
            "calcium signaling, and bradyzoite overlap."
        ),
        site_id="veupathdb",
        step_tree={
            "id": "step_10",
            "displayName": "NcLiv Complete Invasion Toolkit",
            "operator": "UNION",
            "primaryInput": {
                "id": "step_7",
                "displayName": "Invasion Machinery + Signaling",
                "operator": "UNION",
                "primaryInput": {
                    "id": "step_5",
                    "displayName": "All Surface/Secretory/Processing",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "step_3",
                        "displayName": "Surface + Secretory Proteins",
                        "operator": "UNION",
                        "primaryInput": {
                            "id": "step_1",
                            "displayName": "Microneme + AMA1 + Dense Granule",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                NC_ORG,
                                'microneme OR "apical membrane antigen" OR "dense granule" OR perforin',
                            ),
                        },
                        "secondaryInput": {
                            "id": "step_2",
                            "displayName": "SRS Surface Protein Family",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                NC_ORG,
                                '"srs domain" OR "surface antigen"',
                            ),
                        },
                    },
                    "secondaryInput": {
                        "id": "step_4",
                        "displayName": "Invasion Ligand Processing Proteases",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            NC_ORG,
                            "subtilase OR subtilisin OR rhomboid",
                        ),
                    },
                },
                "secondaryInput": {
                    "id": "step_6",
                    "displayName": "Calcium Signaling (Invasion Triggers)",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(
                        NC_ORG,
                        '"CAM kinase" OR CDPK OR "calcium-dependent protein kinase" OR "cAMP-dependent"',
                    ),
                },
            },
            "secondaryInput": {
                "id": "step_9",
                "displayName": "Bradyzoite Invasion Overlap",
                "operator": "INTERSECT",
                "primaryInput": {
                    "id": "step_7_dup",
                    "displayName": "Invasion Machinery + Signaling",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "step_5_dup",
                        "displayName": "All Surface/Secretory/Processing",
                        "operator": "UNION",
                        "primaryInput": {
                            "id": "step_3_dup",
                            "displayName": "Surface + Secretory Proteins",
                            "operator": "UNION",
                            "primaryInput": {
                                "id": "step_1_dup",
                                "displayName": "Microneme + AMA1 + Dense Granule",
                                "searchName": "GenesByText",
                                "parameters": _text_search_params(
                                    NC_ORG,
                                    'microneme OR "apical membrane antigen" OR "dense granule" OR perforin',
                                ),
                            },
                            "secondaryInput": {
                                "id": "step_2_dup",
                                "displayName": "SRS Surface Protein Family",
                                "searchName": "GenesByText",
                                "parameters": _text_search_params(
                                    NC_ORG,
                                    '"srs domain" OR "surface antigen"',
                                ),
                            },
                        },
                        "secondaryInput": {
                            "id": "step_4_dup",
                            "displayName": "Invasion Ligand Processing Proteases",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                NC_ORG,
                                "subtilase OR subtilisin OR rhomboid",
                            ),
                        },
                    },
                    "secondaryInput": {
                        "id": "step_6_dup",
                        "displayName": "Calcium Signaling (Invasion Triggers)",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            NC_ORG,
                            '"CAM kinase" OR CDPK OR "calcium-dependent protein kinase" OR "cAMP-dependent"',
                        ),
                    },
                },
                "secondaryInput": {
                    "id": "step_8",
                    "displayName": "Bradyzoite-Specific Genes",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(NC_ORG, "bradyzoite OR BSR4"),
                },
            },
        },
        control_set=ControlSetDef(
            name="N. caninum Invasion vs Kinases",
            positive_ids=NCANINUM_INVASION[:15],
            negative_ids=NCANINUM_KINASES[:15],
            provenance_notes=(
                "Positives: microneme, rhoptry, AMA1, dense granule, subtilisin "
                "proteases — secretory organelle invasion machinery. "
                "Negatives: CDPK, MAPK, AGC kinases, HSPs — signaling and "
                "chaperone proteins, not invasion-specific."
            ),
            tags=["invasion", "ncaninum", "veupathdb", "seed"],
        ),
    ),
    # ===================================================================
    # 3) TcCLB Trans-Sialidase Immune Evasion Network (9 nodes)
    # ===================================================================
    SeedDef(
        name="TcCLB Trans-Sialidase Immune Evasion Network",
        description=(
            "Maps T. cruzi immune evasion: trans-sialidases + mucins + "
            "MASP + GP63 + amastin stage-specific proteins."
        ),
        site_id="veupathdb",
        step_tree={
            "id": "step_9",
            "displayName": "TcCLB Surface + Stage-Specific Proteins",
            "operator": "UNION",
            "primaryInput": {
                "id": "step_7",
                "displayName": "Complete Surface Coat",
                "operator": "UNION",
                "primaryInput": {
                    "id": "step_5",
                    "displayName": "TS + Mucins + MASP",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "step_3",
                        "displayName": "TS + Mucins",
                        "operator": "UNION",
                        "primaryInput": {
                            "id": "step_1",
                            "displayName": "Trans-Sialidase Superfamily",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                TC_ORG, "trans-sialidase"
                            ),
                        },
                        "secondaryInput": {
                            "id": "step_2",
                            "displayName": "Mucin Family (Sialic Acid Acceptors)",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(TC_ORG, "mucin OR TcMUC"),
                        },
                    },
                    "secondaryInput": {
                        "id": "step_4",
                        "displayName": "MASP Family",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            TC_ORG,
                            '"mucin-associated surface protein" OR MASP',
                        ),
                    },
                },
                "secondaryInput": {
                    "id": "step_6",
                    "displayName": "GP63 Surface Metalloproteases",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(
                        TC_ORG, '"surface protease GP63"'
                    ),
                },
            },
            "secondaryInput": {
                "id": "step_8",
                "displayName": "Amastin (Intracellular Stage)",
                "searchName": "GenesByText",
                "parameters": _text_search_params(TC_ORG, "amastin"),
            },
        },
        control_set=ControlSetDef(
            name="T. cruzi Surface vs Drug Targets",
            positive_ids=TCRUZI_TRANSSIALIDASE[:15] + TCRUZI_MUCIN_MASP_SURFACE[:15],
            negative_ids=TCRUZI_DRUG_TARGETS[:15],
            provenance_notes=(
                "Positives: trans-sialidases, mucins, MASP, GP63, amastin — "
                "surface coat proteins for immune evasion. "
                "Negatives: cruzipain, trypanothione, HSPs — intracellular "
                "drug targets, not surface immune evasion."
            ),
            tags=["immune-evasion", "surface", "tcruzi", "veupathdb", "seed"],
        ),
    ),
    # ===================================================================
    # 4) Cross-Species Apicomplexan Invasion Conserved (7 nodes)
    # ===================================================================
    SeedDef(
        name="Cross-Species Apicomplexan Invasion Conserved",
        description=(
            "Portal-level cross-species strategy identifying conserved "
            "invasion genes across P. vivax and N. caninum for comparative "
            "genomics."
        ),
        site_id="veupathdb",
        step_tree={
            "id": "step_7",
            "displayName": "Cross-Species Invasion Comparison",
            "operator": "UNION",
            "primaryInput": {
                "id": "step_3",
                "displayName": "P. vivax Invasion + Signaling",
                "operator": "UNION",
                "primaryInput": {
                    "id": "step_1",
                    "displayName": "P. vivax Invasion Organelle Proteins",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(
                        PV_ORG,
                        '"apical membrane antigen" OR rhoptry OR microneme',
                    ),
                },
                "secondaryInput": {
                    "id": "step_2",
                    "displayName": "P. vivax Kinases + Chaperones",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(
                        PV_ORG,
                        '"calcium-dependent protein kinase" OR "heat shock protein"',
                    ),
                },
            },
            "secondaryInput": {
                "id": "step_6",
                "displayName": "N. caninum Invasion + Signaling",
                "operator": "UNION",
                "primaryInput": {
                    "id": "step_4",
                    "displayName": "N. caninum Invasion Organelle Proteins",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(
                        NC_ORG,
                        '"apical membrane antigen" OR rhoptry OR microneme OR "dense granule"',
                    ),
                },
                "secondaryInput": {
                    "id": "step_5",
                    "displayName": "N. caninum Kinases + Chaperones",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(
                        NC_ORG,
                        '"CAM kinase" OR CDPK OR "heat shock"',
                    ),
                },
            },
        },
        control_set=ControlSetDef(
            name="Cross-Species Invasion Panel",
            positive_ids=PVIVAX_INVASION_SURFACE[:15] + NCANINUM_INVASION[:15],
            negative_ids=PVIVAX_VARIANT_SURFACE[:15] + NCANINUM_SURFACE_SRS[:15],
            provenance_notes=(
                "Positives: P. vivax + N. caninum invasion organelle proteins "
                "(rhoptry, microneme, AMA1, CDPKs). "
                "Negatives: VIR variant surface + SRS domain proteins — "
                "surface-exposed but not conserved invasion machinery."
            ),
            tags=["cross-species", "invasion", "veupathdb", "seed"],
        ),
    ),
    # ===================================================================
    # 5) Portal-Wide Essential Drug Targets (7 nodes)
    # ===================================================================
    SeedDef(
        name="Portal-Wide Essential Drug Targets",
        description=(
            "Cross-organism drug target discovery across P. vivax, "
            "N. caninum, and T. cruzi — conserved targets for pan-parasitic "
            "drug development."
        ),
        site_id="veupathdb",
        step_tree={
            "id": "step_7",
            "displayName": "Complete Drug Target Collection",
            "operator": "UNION",
            "primaryInput": {
                "id": "step_5",
                "displayName": "Portal-Wide Drug Target Candidates",
                "operator": "UNION",
                "primaryInput": {
                    "id": "step_3",
                    "displayName": "Pv + Nc Drug Targets",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "step_1",
                        "displayName": "P. vivax Validated Drug Targets",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            PV_ORG,
                            '"dihydrofolate reductase" OR plasmepsin OR "heat shock protein 90" OR "heat shock protein 70" OR "chloroquine resistance"',
                        ),
                    },
                    "secondaryInput": {
                        "id": "step_2",
                        "displayName": "N. caninum Drug Targets",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            NC_ORG,
                            '"heat shock protein 90" OR "heat shock protein 70" OR cyclophilin OR "aspartyl protease" OR "ABC transporter"',
                        ),
                    },
                },
                "secondaryInput": {
                    "id": "step_4",
                    "displayName": "T. cruzi Chagas Drug Targets",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(
                        TC_ORG,
                        'cruzipain OR "trypanothione reductase" OR "sterol 24-c-methyltransferase" OR "heat shock protein 90" OR "heat shock protein 70"',
                    ),
                },
            },
            "secondaryInput": {
                "id": "step_6",
                "displayName": "Conserved Transporter Targets",
                "searchName": "GenesByText",
                "parameters": _text_search_params(
                    PV_ORG,
                    '"ABC transporter" OR "folate transporter" OR "nucleoside transporter"',
                ),
            },
        },
        control_set=ControlSetDef(
            name="Cross-Species Drug Targets Panel",
            positive_ids=(
                PVIVAX_DRUG_TARGETS[:10]
                + NCANINUM_KINASES[:10]
                + TCRUZI_DRUG_TARGETS[:10]
            ),
            negative_ids=(PVIVAX_VARIANT_SURFACE[:10] + TCRUZI_FLAGELLAR[:10]),
            provenance_notes=(
                "Positives: validated drug targets across P. vivax (DHFR, CDPKs), "
                "N. caninum (kinases, HSPs), and T. cruzi (cruzipain, trypanothione). "
                "Negatives: VIR surface proteins and flagellar structural proteins — "
                "not drug targets."
            ),
            tags=["drug-target", "cross-species", "veupathdb", "seed"],
        ),
    ),
    # ===================================================================
    # 6) TcCLB Chagas Vaccine Candidate Pipeline (7 nodes)
    # ===================================================================
    SeedDef(
        name="TcCLB Chagas Vaccine Candidate Pipeline",
        description=(
            "Vaccine candidates for Chagas disease: trans-sialidases, "
            "amastin, cruzipain, flagellar antigens, and conserved "
            "immunogenic proteins (HSP70/90, trypanothione reductase)."
        ),
        site_id="veupathdb",
        step_tree={
            "id": "step_7",
            "displayName": "TcCLB Vaccine + Immunogenic Candidates",
            "operator": "UNION",
            "primaryInput": {
                "id": "step_5",
                "displayName": "All Vaccine Candidates",
                "operator": "UNION",
                "primaryInput": {
                    "id": "step_3",
                    "displayName": "Major Antigen Families",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "step_1",
                        "displayName": "Trans-Sialidase Family",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(TC_ORG, "trans-sialidase"),
                    },
                    "secondaryInput": {
                        "id": "step_2",
                        "displayName": "Amastin + Cruzipain (Stage Antigens)",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            TC_ORG, "amastin OR cruzipain"
                        ),
                    },
                },
                "secondaryInput": {
                    "id": "step_4",
                    "displayName": "Flagellar Surface Antigens",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(
                        TC_ORG,
                        '"paraflagellar rod" OR "flagellar calcium" OR "flagellar attachment"',
                    ),
                },
            },
            "secondaryInput": {
                "id": "step_6",
                "displayName": "Conserved Immunogenic Proteins",
                "searchName": "GenesByText",
                "parameters": _text_search_params(
                    TC_ORG,
                    '"heat shock protein 70" OR "heat shock protein 90" OR "trypanothione reductase"',
                ),
            },
        },
        control_set=ControlSetDef(
            name="T. cruzi Vaccine vs Flagellar Panel",
            positive_ids=TCRUZI_TRANSSIALIDASE[:15] + TCRUZI_MUCIN_MASP_SURFACE[:10],
            negative_ids=TCRUZI_FLAGELLAR[:15],
            provenance_notes=(
                "Positives: trans-sialidases, mucins, MASP — major immunogenic "
                "surface antigens and vaccine candidates. "
                "Negatives: tubulin, paraflagellar rod, calmodulin — structural "
                "proteins, not primary vaccine targets."
            ),
            tags=["vaccine", "chagas", "tcruzi", "veupathdb", "seed"],
        ),
    ),
]
