"""Seed definitions for FungiDB.

Organism: Aspergillus fumigatus Af293

Strategies model real research questions:
  1. Antifungal Drug Targets (10 nodes)
  2. Virulence Factors (8 nodes)
  3. Secondary Metabolite Biosynthesis (7 nodes)
  4. Cell Wall Machinery (8 nodes)
  5. Azole Resistance Network (6 nodes)
  6. Iron Acquisition & Oxidative Defense (9 nodes)

All gene IDs verified against live FungiDB API (March 2026).
"""

import json

from veupath_chatbot.services.experiment.seed.types import ControlSetDef, SeedDef

# ---------------------------------------------------------------------------
# Organism constants
# ---------------------------------------------------------------------------

ORGANISM = "Aspergillus fumigatus Af293"

# ---------------------------------------------------------------------------
# Gene data -- real IDs from FungiDB, A. fumigatus Af293 (March 2026)
# ---------------------------------------------------------------------------

# --- Cell wall biosynthesis ---
AFUM_CHITIN_SYNTHASES = [
    "Afu1g12600",
    "Afu2g01870",
    "Afu2g13430",
    "Afu2g13440",
    "Afu3g14420",
    "Afu4g04180",
    "Afu5g00760",
    "Afu8g05620",
    "Afu8g05630",
]

AFUM_GLUCAN_SYNTHASES = [
    "Afu1g15440",  # alpha-1,3-glucan synthase ags1
    "Afu2g11270",  # alpha-1,3-glucan synthase ags2
    "Afu3g00910",  # alpha-1,3-glucan synthase ags3
    "Afu5g05770",  # beta-1,3-glucan synthase catalytic
    "Afu6g12400",  # beta-1,3-glucan synthase FKS1
]

AFUM_GPI_ANCHORED = [
    "Afu1g03570",
    "Afu1g03630",
    "Afu1g05790",
    "Afu1g09510",
    "Afu1g09650",
    "Afu1g10590",
    "Afu1g14140",
    "Afu1g14870",
    "Afu1g15130",
    "Afu1g17560",
    "Afu2g01710",
    "Afu2g05040",
    "Afu2g05150",
    "Afu2g07800",
    "Afu2g14360",
    "Afu3g01150",
    "Afu3g01800",
    "Afu3g08990",
    "Afu3g09740",
    "Afu3g09860",
    "Afu3g13360",
    "Afu4g02720",
    "Afu4g03500",
    "Afu4g03600",
    "Afu4g03970",
    "Afu4g08200",
    "Afu4g08960",
    "Afu4g11280",
    "Afu5g01810",
    "Afu5g06050",
    "Afu5g06810",
    "Afu5g09960",
    "Afu5g10010",
    "Afu6g00620",
    "Afu6g02800",
    "Afu6g05260",
    "Afu6g07180",
    "Afu6g09020",
    "Afu6g10290",
    "Afu6g10580",
    "Afu6g11390",
    "Afu6g12760",
    "Afu6g14090",
    "Afu7g00450",
    "Afu7g00970",
    "Afu7g01300",
    "Afu7g05540",
    "Afu8g04370",
    "Afu8g04860",
    "Afu8g05410",
]

AFUM_MANNOSYLTRANSFERASES = [
    "Afu1g01380",
    "Afu1g06890",
    "Afu1g07690",
    "Afu1g14140",
    "Afu2g01450",
    "Afu2g14910",
    "Afu2g15910",
    "Afu3g06450",
    "Afu3g10400",
    "Afu4g09130",
    "Afu4g11280",
    "Afu4g12900",
    "Afu5g02740",
    "Afu5g06050",
    "Afu5g08580",
    "Afu5g10760",
    "Afu5g11990",
    "Afu5g12160",
    "Afu5g13210",
    "Afu6g04450",
    "Afu6g14040",
    "Afu6g14180",
    "Afu7g01300",
    "Afu8g02040",
    "Afu8g04500",
]

AFUM_CELL_WALL_GO = [
    "Afu1g02040",
    "Afu1g03600",
    "Afu1g04260",
    "Afu1g06390",
    "Afu1g07440",
    "Afu1g07480",
    "Afu1g10350",
    "Afu1g10630",
    "Afu1g11460",
    "Afu1g11640",
    "Afu1g12920",
    "Afu1g14100",
    "Afu1g16190",
    "Afu1g17250",
    "Afu1g17370",
    "Afu2g00710",
    "Afu2g01010",
    "Afu2g01170",
    "Afu2g02150",
    "Afu2g02480",
    "Afu2g03120",
    "Afu2g03290",
    "Afu2g03380",
    "Afu2g04060",
    "Afu2g09960",
    "Afu2g10440",
    "Afu2g11270",
    "Afu2g13460",
    "Afu2g13530",
    "Afu2g14661",
    "Afu3g02280",
    "Afu3g07050",
    "Afu3g07430",
    "Afu3g08380",
    "Afu3g09690",
    "Afu3g11690",
    "Afu3g12690",
    "Afu3g14590",
    "Afu4g03240",
    "Afu4g03970",
    "Afu4g04318",
    "Afu4g04600",
    "Afu4g06820",
    "Afu4g07360",
    "Afu4g07845",
    "Afu4g09030",
    "Afu4g09580",
    "Afu4g10130",
    "Afu4g10800",
    "Afu4g11150",
    "Afu4g11510",
    "Afu4g13670",
    "Afu4g14000",
    "Afu5g01970",
    "Afu5g03080",
    "Afu5g03280",
    "Afu5g03760",
    "Afu5g04170",
    "Afu5g04250",
    "Afu5g05450",
]

# --- Secondary metabolites ---
AFUM_GLIOTOXIN_CLUSTER = [
    "Afu6g09630",  # gliZ - transcription factor
    "Afu6g09640",  # gliI - aminotransferase
    "Afu6g09650",  # gliJ - dipeptidase
    "Afu6g09660",  # gliP - NRPS (nonribosomal peptide synthetase)
    "Afu6g09670",  # gliC - cytochrome P450 monooxygenase
    "Afu6g09680",  # gliM - O-methyltransferase
    "Afu6g09690",  # gliG - glutathione S-transferase
    "Afu6g09700",  # gliK - unknown function
    "Afu6g09710",  # gliA - MFS transporter / efflux
    "Afu6g09720",  # gliN - N-methyltransferase
    "Afu6g09730",  # gliF - cytochrome P450
    "Afu6g09740",  # gliT - thioredoxin oxidoreductase
]

AFUM_MELANIN_CLUSTER = [
    "Afu2g17530",  # abr2 - laccase/multicopper oxidase
    "Afu2g17540",  # abr1 - multicopper oxidase
    "Afu2g17550",  # ayg1 - conidial pigment biosynthesis
    "Afu2g17560",  # arp2 - scytalone dehydratase
    "Afu2g17580",  # arp1 - conidial pigment biosynthesis
    "Afu2g17600",  # pksP/alb1 - polyketide synthase (conidial color)
]

AFUM_NRPS = [
    "Afu1g05180",
    "Afu1g09600",
    "Afu1g10380",
    "Afu1g12240",
    "Afu1g15280",
    "Afu1g17200",
    "Afu2g00330",
    "Afu2g03140",
    "Afu2g03900",
    "Afu2g04000",
    "Afu2g05530",
    "Afu2g09320",
    "Afu3g01270",
    "Afu3g02670",
    "Afu3g03350",
    "Afu3g03420",
    "Afu3g07210",
    "Afu3g09940",
    "Afu3g12920",
    "Afu3g13730",
    "Afu3g15270",
    "Afu4g02790",
    "Afu4g07590",
    "Afu4g09310",
    "Afu5g01630",
    "Afu5g03220",
    "Afu5g05800",
    "Afu5g08130",
    "Afu5g12730",
    "Afu6g03480",
    "Afu6g07840",
    "Afu6g08560",
    "Afu6g09610",
    "Afu6g09660",
    "Afu6g10430",
    "Afu6g12050",
    "Afu6g12080",
    "Afu6g12670",
    "Afu6g13450",
    "Afu7g01490",
    "Afu8g00170",
    "Afu8g01640",
    "Afu8g02550",
    "Afu8g05340",
]

AFUM_SM_REGULATION = [
    "Afu1g14660",
    "Afu1g16880",
    "Afu2g01290",
    "Afu3g02530",
    "Afu3g02570",
    "Afu3g02670",
    "Afu3g08070",
    "Afu3g12030",
    "Afu4g06780",
    "Afu4g09150",
    "Afu5g04220",
    "Afu5g06800",
    "Afu5g08150",
    "Afu5g10510",
    "Afu5g11190",
    "Afu6g08560",
    "Afu8g00770",
    "Afu8g01240",
    "Afu8g01640",
]

AFUM_FUMAGILLIN = [
    "Afu8g00370",
    "Afu8g00380",
    "Afu8g00390",
    "Afu8g00400",
    "Afu8g00510",
    "Afu8g00520",
]
AFUM_FUMITREMORGIN = ["Afu8g00240"]
AFUM_VERRUCULOGEN = ["Afu8g00230"]
AFUM_TERPENE = ["Afu6g13950", "Afu8g00520"]

# --- Antifungal resistance ---
AFUM_CYP51A = ["Afu4g06890"]  # cyp51A - sterol 14-alpha-demethylase
AFUM_LANOSTEROL = ["Afu4g12040", "Afu5g04080"]
AFUM_ERGOSTEROL = [
    "Afu2g11550",
    "Afu3g10490",
    "Afu4g11500",
    "Afu5g14260",
]

AFUM_CYP450 = [
    "Afu1g00510",
    "Afu1g02070",
    "Afu1g03950",
    "Afu1g04540",
    "Afu1g13480",
    "Afu1g15590",
    "Afu1g17725",
    "Afu2g03010",
    "Afu2g12260",
    "Afu2g13010",
    "Afu2g13110",
    "Afu2g14060",
    "Afu2g17620",
    "Afu2g17980",
    "Afu2g18010",
    "Afu3g03930",
    "Afu3g03980",
    "Afu3g06190",
    "Afu3g09220",
    "Afu3g09780",
    "Afu3g12630",
    "Afu3g12960",
    "Afu3g14440",
    "Afu3g14760",
    "Afu4g03120",
    "Afu4g04600",
    "Afu4g06790",
    "Afu4g06890",
    "Afu4g07120",
    "Afu4g07150",
    "Afu4g09110",
    "Afu4g09980",
    "Afu4g11390",
    "Afu4g14780",
    "Afu4g14790",
    "Afu4g14810",
    "Afu4g14830",
    "Afu5g00120",
    "Afu5g01710",
    "Afu5g02620",
    "Afu5g02750",
    "Afu5g04210",
    "Afu5g09680",
    "Afu5g10050",
    "Afu5g10560",
    "Afu5g10610",
    "Afu6g02210",
    "Afu6g07670",
    "Afu6g09670",
    "Afu6g09730",
    "Afu6g10990",
]

AFUM_ABC_TRANSPORTERS = [
    "Afu1g04780",
    "Afu2g14020",
    "Afu3g02760",
    "Afu4g14130",
    "Afu5g07020",
    "Afu6g03080",
    "Afu6g03470",
    "Afu6g04360",
    "Afu6g07280",
    "Afu6g08020",
    "Afu7g00480",
]

AFUM_EFFLUX = [
    "Afu1g05760",
    "Afu1g12620",
    "Afu3g15250",
    "Afu5g13170",
    "Afu5g15010",
    "Afu6g02220",
    "Afu6g09710",
    "Afu7g01790",
]

# --- Virulence and pathogenesis ---
AFUM_PATHOGENESIS_GO = [
    "Afu1g02040",
    "Afu1g02820",
    "Afu1g03450",
    "Afu1g03500",
    "Afu1g05720",
    "Afu1g06100",
    "Afu1g06400",
    "Afu1g06420",
    "Afu1g08850",
    "Afu1g08940",
    "Afu1g10570",
    "Afu1g11420",
    "Afu1g11460",
    "Afu1g11640",
    "Afu1g12040",
    "Afu1g12180",
    "Afu1g12760",
    "Afu1g12930",
    "Afu1g13330",
    "Afu1g14030",
    "Afu1g14890",
    "Afu1g14950",
    "Afu1g15520",
    "Afu1g15780",
    "Afu1g15960",
    "Afu1g16320",
    "Afu1g17200",
    "Afu2g01040",
    "Afu2g01590",
    "Afu2g02130",
    "Afu2g02690",
    "Afu2g03120",
    "Afu2g03290",
    "Afu2g03560",
    "Afu2g03790",
    "Afu2g03810",
    "Afu2g04680",
    "Afu2g05740",
    "Afu2g07420",
    "Afu2g07690",
    "Afu2g08360",
    "Afu2g08550",
    "Afu2g08590",
    "Afu2g10640",
    "Afu2g11330",
    "Afu2g12200",
    "Afu2g13240",
    "Afu2g17170",
    "Afu3g00650",
    "Afu3g01220",
]

AFUM_PROTEASES = [
    "Afu1g07160",
    "Afu1g15920",
    "Afu2g02680",
    "Afu2g03400",
    "Afu2g04720",
    "Afu2g05590",
    "Afu2g11740",
    "Afu2g14130",
    "Afu3g05510",
    "Afu3g05550",
    "Afu3g08730",
    "Afu3g08930",
    "Afu3g11700",
    "Afu4g03490",
    "Afu4g09400",
    "Afu4g11150",
    "Afu4g11530",
    "Afu4g11800",
    "Afu4g13560",
    "Afu5g03195",
    "Afu5g03250",
    "Afu5g09210",
    "Afu5g11750",
    "Afu5g11870",
    "Afu5g11950",
    "Afu5g13620",
    "Afu5g14040",
    "Afu6g02380",
    "Afu6g07860",
    "Afu6g10250",
    "Afu6g12270",
    "Afu6g12710",
    "Afu6g14420",
    "Afu7g04610",
    "Afu7g04930",
    "Afu7g06220",
    "Afu7g07170",
    "Afu7g08340",
]

AFUM_CATALASES = [
    "Afu2g00200",
    "Afu2g18030",
    "Afu3g02270",
    "Afu6g03890",
    "Afu8g01670",
]

AFUM_SOD = [
    "Afu1g11640",
    "Afu1g14550",
    "Afu2g09700",
    "Afu4g11580",
    "Afu5g09240",
    "Afu6g07210",
    "Afu6g13350",
]

AFUM_ALLERGENS = [
    "Afu1g01120",
    "Afu1g03060",
    "Afu1g14050",
    "Afu2g03830",
    "Afu2g09520",
    "Afu2g10100",
    "Afu2g11570",
    "Afu2g12630",
    "Afu3g00590",
    "Afu3g03060",
    "Afu4g06670",
    "Afu4g09580",
    "Afu5g02330",
    "Afu5g11320",
    "Afu6g02280",
    "Afu6g10300",
]

# --- Oxidative stress and iron acquisition ---
AFUM_OXIDATIVE_STRESS_GO = [
    "Afu1g01980",
    "Afu1g02820",
    "Afu1g03040",
    "Afu1g04540",
    "Afu1g04820",
    "Afu1g05240",
    "Afu1g05390",
    "Afu1g05930",
    "Afu1g06100",
    "Afu1g06400",
    "Afu1g07470",
    "Afu1g08790",
    "Afu1g08880",
    "Afu1g09090",
    "Afu1g10940",
    "Afu1g11640",
    "Afu1g12940",
    "Afu1g13060",
    "Afu1g13600",
    "Afu1g14180",
    "Afu1g14950",
    "Afu1g15390",
    "Afu1g15950",
    "Afu1g15960",
    "Afu1g16780",
    "Afu1g17200",
    "Afu1g17360",
    "Afu1g17370",
    "Afu2g00200",
    "Afu2g01040",
    "Afu2g01360",
    "Afu2g01520",
    "Afu2g01700",
    "Afu2g03140",
    "Afu2g03490",
    "Afu2g04680",
    "Afu2g07420",
    "Afu2g07680",
    "Afu2g09700",
    "Afu2g10150",
    "Afu2g10220",
    "Afu2g10660",
    "Afu2g11740",
    "Afu2g12030",
    "Afu2g13680",
    "Afu2g14960",
    "Afu2g15130",
    "Afu2g15650",
    "Afu2g16510",
    "Afu2g18030",
]

AFUM_SIDEROPHORES = [
    "Afu2g05730",  # siderophore biosynthesis
    "Afu3g03390",  # sidD - siderophore NRPS
    "Afu3g03400",  # sidF - siderophore biosynthesis
    "Afu3g03440",  # siderophore biosynthesis
    "Afu3g03640",  # sidG - siderophore transacetylase
    "Afu3g03660",  # siderophore biosynthesis
    "Afu7g04730",  # siderophore biosynthesis
    "Afu7g06060",  # siderophore biosynthesis
    "Afu8g01310",  # siderophore biosynthesis
]

AFUM_IRON_GENES = [
    "Afu2g07680",  # sidA - L-ornithine N5-monooxygenase
    "Afu5g03920",  # hapX - bZIP transcription factor
    "Afu5g11260",  # sreA - GATA transcription factor
]

AFUM_GLUTATHIONE = [
    "Afu1g01370",
    "Afu1g06100",
    "Afu1g09090",
    "Afu1g11980",
    "Afu1g15960",
    "Afu1g16880",
    "Afu1g17010",
    "Afu2g00590",
    "Afu2g08370",
    "Afu2g14960",
    "Afu2g15770",
    "Afu2g17300",
    "Afu3g07930",
    "Afu3g08560",
    "Afu3g10830",
    "Afu3g12270",
    "Afu3g13900",
    "Afu4g01440",
    "Afu4g05950",
    "Afu4g14100",
    "Afu4g14530",
    "Afu5g06610",
    "Afu5g07970",
    "Afu6g00760",
    "Afu6g03390",
    "Afu6g09690",
    "Afu7g05500",
    "Afu8g00580",
    "Afu8g02500",
]

AFUM_THIOREDOXIN = [
    "Afu1g10820",
    "Afu3g14970",
    "Afu4g12990",
    "Afu5g01440",
    "Afu6g09740",
    "Afu8g01090",
    "Afu8g07130",
]

# --- Conidial surface and thermotolerance ---
AFUM_HYDROPHOBINS = [
    "Afu1g17250",
    "Afu5g01490",
    "Afu5g03280",
    "Afu5g09580",
    "Afu8g05890",
    "Afu8g07060",
]

AFUM_HEAT_SHOCK = [
    "Afu1g11180",
    "Afu1g17370",
    "Afu2g16020",
    "Afu3g14540",
    "Afu4g10010",
    "Afu5g01900",
    "Afu5g04170",
    "Afu6g06470",
    "Afu6g12450",
    "Afu7g01860",
]

# --- Signaling pathways ---
AFUM_CALCINEURIN = [
    "Afu2g13060",  # calcineurin-related
    "Afu5g09360",  # cnaA - calcineurin catalytic subunit
    "Afu6g04540",  # cnaB - calcineurin regulatory subunit
]

AFUM_RAS = [
    "Afu1g02190",
    "Afu2g07770",
    "Afu2g16240",
    "Afu5g05480",
    "Afu5g11230",
]

AFUM_PROTEIN_KINASES = [
    "Afu1g05800",
    "Afu1g06400",
    "Afu1g07070",
    "Afu1g11930",
    "Afu1g11950",
    "Afu1g12940",
    "Afu1g13600",
    "Afu1g15950",
    "Afu1g16000",
    "Afu2g00670",
    "Afu2g01700",
    "Afu2g03490",
    "Afu2g09710",
    "Afu2g10270",
    "Afu2g11730",
    "Afu2g12200",
    "Afu2g12390",
    "Afu2g13140",
    "Afu2g13640",
    "Afu2g13680",
    "Afu2g14200",
    "Afu2g14650",
    "Afu2g15010",
    "Afu3g01190",
    "Afu3g02460",
    "Afu3g02500",
    "Afu3g02740",
    "Afu3g03740",
    "Afu3g08710",
    "Afu3g09550",
    "Afu3g10000",
    "Afu3g10040",
    "Afu3g11080",
    "Afu3g12550",
    "Afu3g12670",
    "Afu3g13210",
    "Afu3g13990",
    "Afu4g08920",
    "Afu4g09050",
    "Afu4g13720",
    "Afu4g14735",
    "Afu4g14740",
    "Afu5g03000",
    "Afu5g03160",
    "Afu5g03950",
    "Afu5g04130",
    "Afu5g05510",
    "Afu5g05750",
    "Afu5g05960",
    "Afu5g05980",
    "Afu5g06470",
    "Afu5g06730",
    "Afu5g06750",
    "Afu5g08570",
    "Afu5g09100",
    "Afu5g11730",
    "Afu5g11970",
    "Afu5g12990",
    "Afu5g13420",
    "Afu5g15080",
]

AFUM_EC_KINASES = [
    "Afu1g01720",
    "Afu1g11080",
    "Afu1g14810",
    "Afu2g01700",
    "Afu2g04680",
    "Afu2g07550",
    "Afu2g10270",
    "Afu2g14090",
    "Afu3g14290",
    "Afu4g04760",
    "Afu4g09050",
    "Afu4g14740",
    "Afu5g02570",
    "Afu5g05900",
    "Afu5g06750",
    "Afu5g11730",
    "Afu5g12660",
    "Afu6g02300",
    "Afu6g05120",
    "Afu7g03930",
]

# --- Membrane and transport ---
AFUM_PHOSPHOLIPASES = [
    "Afu1g13250",
    "Afu1g17590",
    "Afu2g00990",
    "Afu2g11970",
    "Afu2g16520",
    "Afu3g01530",
    "Afu3g05630",
    "Afu3g07940",
    "Afu4g08720",
    "Afu4g12000",
    "Afu5g01340",
    "Afu7g05580",
]

AFUM_LIPASES = [
    "Afu1g04970",
    "Afu1g09110",
    "Afu1g15430",
    "Afu2g08920",
    "Afu3g03390",
    "Afu3g04240",
    "Afu4g03210",
    "Afu4g04530",
    "Afu4g14120",
    "Afu5g02040",
    "Afu5g14150",
    "Afu6g02710",
    "Afu6g06510",
    "Afu7g00110",
    "Afu7g02040",
    "Afu7g04950",
    "Afu8g01050",
    "Afu8g02530",
]

# --- Ribosomal proteins (negative controls) ---
AFUM_RIBOSOMAL = [
    "Afu1g03390",
    "Afu1g04320",
    "Afu1g04660",
    "Afu1g05080",
    "Afu1g05340",
    "Afu1g05500",
    "Afu1g05630",
    "Afu1g05990",
    "Afu1g06340",
    "Afu1g06770",
    "Afu1g06830",
    "Afu1g09100",
    "Afu1g09440",
    "Afu1g10510",
    "Afu1g11130",
    "Afu1g11710",
    "Afu1g12890",
    "Afu1g14410",
    "Afu1g14750",
    "Afu1g15020",
    "Afu1g15730",
    "Afu2g01830",
    "Afu2g02150",
    "Afu2g03040",
    "Afu2g03590",
    "Afu2g04130",
    "Afu2g07380",
    "Afu2g07970",
    "Afu2g08130",
    "Afu2g09200",
    "Afu2g09210",
    "Afu2g10090",
    "Afu2g10300",
    "Afu2g10500",
    "Afu2g11140",
    "Afu2g16370",
    "Afu2g16880",
    "Afu3g05600",
    "Afu3g06760",
    "Afu3g06960",
    "Afu3g06970",
    "Afu3g08460",
    "Afu3g10730",
    "Afu3g12300",
    "Afu3g13320",
    "Afu4g03880",
    "Afu4g04460",
    "Afu4g07250",
    "Afu4g07435",
    "Afu4g07730",
    "Afu4g10800",
    "Afu5g03020",
    "Afu5g05450",
    "Afu5g05630",
    "Afu5g06360",
    "Afu6g02440",
    "Afu6g03830",
    "Afu6g05200",
    "Afu6g11260",
    "Afu6g12660",
]

AFUM_CELLULASES = [
    "Afu2g14540",
    "Afu3g01160",
    "Afu3g03610",
    "Afu6g07480",
    "Afu7g06150",
    "Afu7g06740",
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
        "go_term_evidence": "Computed",
        "go_term_slim": "No",
        "go_typeahead": go_id,
        "go_term": go_id,
    }


def _text_search_params(
    organism: str, text: str, fields: str = '["product"]'
) -> dict[str, str]:
    """Build GenesByText parameters."""
    return {
        "text_search_organism": _org([organism]),
        "text_expression": text,
        "document_type": "gene",
        "text_fields": fields,
    }


def _ec_search_params(organism: str, ec_number: str) -> dict[str, str]:
    """Build GenesByEcNumber parameters."""
    return {
        "organism": _org([organism]),
        "ec_source": json.dumps(["KEGG_Enzyme"]),
        "ec_number_pattern": ec_number,
        "ec_wildcard": ec_number,
    }


def _signal_peptide_params(organism: str) -> dict[str, str]:
    """Build GenesWithSignalPeptide parameters."""
    return {"organism": _org([organism])}


def _tm_domain_params(organism: str, min_tm: str, max_tm: str) -> dict[str, str]:
    """Build GenesByTransmembraneDomains parameters."""
    return {
        "organism": _org([organism]),
        "min_tm": min_tm,
        "max_tm": max_tm,
    }


def _mw_params(organism: str, min_mw: str, max_mw: str) -> dict[str, str]:
    """Build GenesByMolecularWeight parameters."""
    return {
        "organism": _org([organism]),
        "min_molecular_weight": min_mw,
        "max_molecular_weight": max_mw,
    }


# ---------------------------------------------------------------------------
# Seeds
# ---------------------------------------------------------------------------

SEEDS: list[SeedDef] = [
    # ===================================================================
    # 1) Antifungal Drug Targets (10 nodes)
    # ===================================================================
    SeedDef(
        name="AfAf293 Antifungal Targets",
        description=(
            "Multi-step strategy to identify potential antifungal drug targets in "
            "A. fumigatus Af293. Combines cell wall enzymes (chitin/glucan synthases), "
            "ergosterol pathway genes (CYP51A), secreted proteins, and membrane-bound "
            "targets, excluding ribosomal housekeeping genes."
        ),
        site_id="fungidb",
        step_tree={
            "id": "root_minus_ribosomal",
            "displayName": "Drug Targets minus Housekeeping",
            "operator": "MINUS",
            "primaryInput": {
                "id": "secreted_targets",
                "displayName": "Secreted Drug Targets",
                "operator": "UNION",
                "primaryInput": {
                    "id": "secreted_cell_wall",
                    "displayName": "Secreted Cell Wall Enzymes",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "cell_wall_all",
                        "displayName": "All Cell Wall Enzymes",
                        "operator": "UNION",
                        "primaryInput": {
                            "id": "chitin_glucan",
                            "displayName": "Chitin + Glucan Synthases",
                            "operator": "UNION",
                            "primaryInput": {
                                "id": "leaf_chitin",
                                "displayName": "Chitin Synthases",
                                "searchName": "GenesByText",
                                "parameters": _text_search_params(
                                    ORGANISM, '"chitin synthase"'
                                ),
                            },
                            "secondaryInput": {
                                "id": "leaf_glucan",
                                "displayName": "Glucan Synthases",
                                "searchName": "GenesByText",
                                "parameters": _text_search_params(
                                    ORGANISM, '"glucan synthase"'
                                ),
                            },
                        },
                        "secondaryInput": {
                            "id": "leaf_gpi",
                            "displayName": "GPI-anchored Proteins",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(ORGANISM, "GPI-anchored"),
                        },
                    },
                    "secondaryInput": {
                        "id": "leaf_signal_1",
                        "displayName": "Signal Peptide",
                        "searchName": "GenesWithSignalPeptide",
                        "parameters": _signal_peptide_params(ORGANISM),
                    },
                },
                "secondaryInput": {
                    "id": "membrane_targets",
                    "displayName": "Membrane CYP450 Targets",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "leaf_cyp450",
                        "displayName": "Cytochrome P450s",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            ORGANISM, '"cytochrome P450"'
                        ),
                    },
                    "secondaryInput": {
                        "id": "leaf_tm",
                        "displayName": "Transmembrane Proteins (>=1 TM)",
                        "searchName": "GenesByTransmembraneDomains",
                        "parameters": _tm_domain_params(ORGANISM, "1", "20"),
                    },
                },
            },
            "secondaryInput": {
                "id": "leaf_ribosomal",
                "displayName": "Ribosomal Proteins (excluded)",
                "searchName": "GenesByText",
                "parameters": _text_search_params(ORGANISM, '"ribosomal protein"'),
            },
        },
        control_set=ControlSetDef(
            name="A. fumigatus Antifungal Targets (curated)",
            positive_ids=(
                AFUM_CHITIN_SYNTHASES[:6]
                + AFUM_GLUCAN_SYNTHASES[:3]
                + AFUM_CYP51A
                + AFUM_GPI_ANCHORED[:5]
            ),
            negative_ids=AFUM_RIBOSOMAL[:15],
            provenance_notes=(
                "Positives: chitin/glucan synthases, CYP51A azole target, and "
                "GPI-anchored cell wall proteins — validated antifungal targets. "
                "Negatives: ribosomal structural proteins — conserved housekeeping "
                "genes not suitable as drug targets."
            ),
            tags=["drug-target", "aspergillus", "seed"],
        ),
    ),
    # ===================================================================
    # 2) Virulence Factors (8 nodes)
    # ===================================================================
    SeedDef(
        name="AfAf293 Virulence Factors",
        description=(
            "Strategy identifying virulence determinants in A. fumigatus Af293. "
            "Combines pathogenesis-annotated genes (GO:0009405), secreted proteases, "
            "oxidative stress response (GO:0006979), and allergens to capture the "
            "molecular arsenal enabling invasive aspergillosis."
        ),
        site_id="fungidb",
        step_tree={
            "id": "root_virulence",
            "displayName": "All Virulence Factors",
            "operator": "UNION",
            "primaryInput": {
                "id": "pathogen_secreted",
                "displayName": "Pathogenesis + Secreted Proteases",
                "operator": "UNION",
                "primaryInput": {
                    "id": "leaf_pathogenesis",
                    "displayName": "GO: Pathogenesis",
                    "searchName": "GenesByGoTerm",
                    "parameters": _go_search_params(ORGANISM, "GO:0009405"),
                },
                "secondaryInput": {
                    "id": "secreted_proteases",
                    "displayName": "Secreted Proteases",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "leaf_proteases",
                        "displayName": "Proteases",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(ORGANISM, "protease"),
                    },
                    "secondaryInput": {
                        "id": "leaf_signal_2",
                        "displayName": "Signal Peptide",
                        "searchName": "GenesWithSignalPeptide",
                        "parameters": _signal_peptide_params(ORGANISM),
                    },
                },
            },
            "secondaryInput": {
                "id": "stress_allergen",
                "displayName": "Stress + Thermotolerance",
                "operator": "UNION",
                "primaryInput": {
                    "id": "leaf_oxidative",
                    "displayName": "GO: Oxidative Stress Response",
                    "searchName": "GenesByGoTerm",
                    "parameters": _go_search_params(ORGANISM, "GO:0006979"),
                },
                "secondaryInput": {
                    "id": "leaf_heat_shock",
                    "displayName": "Heat Shock Proteins",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(ORGANISM, '"heat shock"'),
                },
            },
        },
        control_set=ControlSetDef(
            name="A. fumigatus Virulence Factors (curated)",
            positive_ids=(
                AFUM_PROTEASES[:8]
                + AFUM_CATALASES[:3]
                + AFUM_SOD[:3]
                + AFUM_ALLERGENS[:4]
                + AFUM_HEAT_SHOCK[:4]
            ),
            negative_ids=AFUM_RIBOSOMAL[:20],
            provenance_notes=(
                "Positives: secreted proteases, catalases, SODs, allergens, and "
                "heat shock proteins — known virulence determinants in invasive "
                "aspergillosis. "
                "Negatives: ribosomal structural proteins — housekeeping genes."
            ),
            tags=["virulence", "aspergillus", "seed"],
        ),
    ),
    # ===================================================================
    # 3) Secondary Metabolite Biosynthesis (7 nodes)
    # ===================================================================
    SeedDef(
        name="AfAf293 Secondary Metabolites",
        description=(
            "Comprehensive secondary metabolite gene strategy for A. fumigatus Af293. "
            "UNION of NRPS, polyketide synthase, and terpene synthase gene families, "
            "plus CYP450 tailoring enzymes, MINUS ribosomal genes."
        ),
        site_id="fungidb",
        step_tree={
            "id": "root_sm_clean",
            "displayName": "Secondary Metabolites (clean)",
            "operator": "MINUS",
            "primaryInput": {
                "id": "sm_backbone_regulated",
                "displayName": "SM Backbone + Tailoring Enzymes",
                "operator": "UNION",
                "primaryInput": {
                    "id": "all_backbone",
                    "displayName": "All SM Backbone Enzymes",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "nrps_pks",
                        "displayName": "NRPS + PKS",
                        "operator": "UNION",
                        "primaryInput": {
                            "id": "leaf_nrps",
                            "displayName": "Nonribosomal Peptide Synthetases",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                ORGANISM, '"nonribosomal peptide"'
                            ),
                        },
                        "secondaryInput": {
                            "id": "leaf_pks",
                            "displayName": "Polyketide Synthases",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                ORGANISM, '"polyketide synthase"'
                            ),
                        },
                    },
                    "secondaryInput": {
                        "id": "leaf_terpene",
                        "displayName": "Terpene Synthases",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(ORGANISM, "terpene"),
                    },
                },
                "secondaryInput": {
                    "id": "leaf_cyp450_sm",
                    "displayName": "Cytochrome P450s (tailoring)",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(ORGANISM, '"cytochrome P450"'),
                },
            },
            "secondaryInput": {
                "id": "leaf_ribosomal_2",
                "displayName": "Ribosomal Proteins (excluded)",
                "searchName": "GenesByText",
                "parameters": _text_search_params(ORGANISM, '"ribosomal protein"'),
            },
        },
        control_set=ControlSetDef(
            name="A. fumigatus Secondary Metabolites (curated)",
            positive_ids=(
                AFUM_GLIOTOXIN_CLUSTER[:6]
                + AFUM_MELANIN_CLUSTER[:4]
                + AFUM_NRPS[:6]
                + AFUM_FUMAGILLIN[:3]
            ),
            negative_ids=AFUM_RIBOSOMAL[:18],
            provenance_notes=(
                "Positives: gliotoxin cluster genes, melanin biosynthesis, NRPS "
                "enzymes, and fumagillin cluster — confirmed secondary metabolite "
                "pathway components. "
                "Negatives: ribosomal structural proteins."
            ),
            tags=["secondary-metabolite", "aspergillus", "seed"],
        ),
    ),
    # ===================================================================
    # 4) Cell Wall Machinery (8 nodes)
    # ===================================================================
    SeedDef(
        name="AfAf293 Cell Wall Machinery",
        description=(
            "Complete cell wall biosynthetic machinery in A. fumigatus Af293. "
            "Combines GO:0005618 (cell wall localization) with text-based searches "
            "for chitin/glucan synthases, GPI-anchored proteins, and "
            "mannosyltransferases, all filtered by signal peptide."
        ),
        site_id="fungidb",
        step_tree={
            "id": "root_cw_secreted",
            "displayName": "Secreted Cell Wall Machinery",
            "operator": "INTERSECT",
            "primaryInput": {
                "id": "all_cw_genes",
                "displayName": "All Cell Wall Genes",
                "operator": "UNION",
                "primaryInput": {
                    "id": "core_cw",
                    "displayName": "Core Synthases + GO",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "leaf_cw_go",
                        "displayName": "GO: Cell Wall",
                        "searchName": "GenesByGoTerm",
                        "parameters": _go_search_params(ORGANISM, "GO:0005618"),
                    },
                    "secondaryInput": {
                        "id": "synthases",
                        "displayName": "Chitin + Glucan Synthases",
                        "operator": "UNION",
                        "primaryInput": {
                            "id": "leaf_chitin_2",
                            "displayName": "Chitin Synthases",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                ORGANISM, '"chitin synthase"'
                            ),
                        },
                        "secondaryInput": {
                            "id": "leaf_glucan_2",
                            "displayName": "Glucan Synthases",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                ORGANISM, '"glucan synthase"'
                            ),
                        },
                    },
                },
                "secondaryInput": {
                    "id": "modification_enzymes",
                    "displayName": "GPI + Mannosyltransferases",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "leaf_gpi_2",
                        "displayName": "GPI-anchored Proteins",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(ORGANISM, "GPI-anchored"),
                    },
                    "secondaryInput": {
                        "id": "leaf_mannosyl",
                        "displayName": "Mannosyltransferases",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            ORGANISM, "mannosyltransferase"
                        ),
                    },
                },
            },
            "secondaryInput": {
                "id": "leaf_signal_3",
                "displayName": "Signal Peptide",
                "searchName": "GenesWithSignalPeptide",
                "parameters": _signal_peptide_params(ORGANISM),
            },
        },
        control_set=ControlSetDef(
            name="A. fumigatus Cell Wall Machinery (curated)",
            positive_ids=(
                AFUM_CHITIN_SYNTHASES[:5]
                + AFUM_GLUCAN_SYNTHASES[:3]
                + AFUM_GPI_ANCHORED[:6]
                + AFUM_MANNOSYLTRANSFERASES[:4]
            ),
            negative_ids=AFUM_RIBOSOMAL[:18],
            provenance_notes=(
                "Positives: chitin/glucan synthases, GPI-anchored proteins, and "
                "mannosyltransferases — core cell wall biosynthetic machinery. "
                "Negatives: ribosomal structural proteins."
            ),
            tags=["cell-wall", "aspergillus", "seed"],
        ),
    ),
    # ===================================================================
    # 5) Azole Resistance Network (6 nodes)
    # ===================================================================
    SeedDef(
        name="AfAf293 Azole Resistance Network",
        description=(
            "Azole resistance mechanisms in A. fumigatus Af293. "
            "UNION of ergosterol pathway, ABC/MFS efflux transporters, and "
            "CYP450 enzymes, INTERSECT with membrane proteins (>=1 TM domain). "
            "Captures CYP51A, efflux pumps, and sterol biosynthesis enzymes."
        ),
        site_id="fungidb",
        step_tree={
            "id": "root_azole",
            "displayName": "Membrane Azole Resistance Genes",
            "operator": "INTERSECT",
            "primaryInput": {
                "id": "azole_genes",
                "displayName": "Azole-related Genes",
                "operator": "UNION",
                "primaryInput": {
                    "id": "erg_cyp",
                    "displayName": "Ergosterol + CYP450",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "leaf_ergosterol",
                        "displayName": "Ergosterol Biosynthesis",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            ORGANISM, "ergosterol", '["product","GOTerms"]'
                        ),
                    },
                    "secondaryInput": {
                        "id": "leaf_cyp450_azole",
                        "displayName": "Cytochrome P450s",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            ORGANISM, '"cytochrome P450"'
                        ),
                    },
                },
                "secondaryInput": {
                    "id": "all_transporters",
                    "displayName": "ABC + Efflux Transporters",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "leaf_abc",
                        "displayName": "ABC Transporters",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            ORGANISM, '"ABC transporter"'
                        ),
                    },
                    "secondaryInput": {
                        "id": "leaf_efflux",
                        "displayName": "Efflux Pumps",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(ORGANISM, "efflux"),
                    },
                },
            },
            "secondaryInput": {
                "id": "leaf_tm_azole",
                "displayName": "Transmembrane Proteins",
                "searchName": "GenesByTransmembraneDomains",
                "parameters": _tm_domain_params(ORGANISM, "1", "20"),
            },
        },
        control_set=ControlSetDef(
            name="A. fumigatus Azole Resistance (curated)",
            positive_ids=(
                AFUM_CYP51A
                + AFUM_ERGOSTEROL[:3]
                + AFUM_ABC_TRANSPORTERS[:5]
                + AFUM_EFFLUX[:4]
                + AFUM_LANOSTEROL
            ),
            negative_ids=AFUM_RIBOSOMAL[:15],
            provenance_notes=(
                "Positives: CYP51A azole target, ergosterol pathway enzymes, "
                "ABC transporters, efflux pumps, and lanosterol biosynthesis — "
                "known azole resistance mechanisms. "
                "Negatives: ribosomal structural proteins."
            ),
            tags=["azole-resistance", "aspergillus", "seed"],
        ),
    ),
    # ===================================================================
    # 6) Iron Acquisition & Oxidative Defense (9 nodes)
    # ===================================================================
    SeedDef(
        name="AfAf293 Iron and Redox Defense",
        description=(
            "Iron acquisition and oxidative stress defense in A. fumigatus Af293. "
            "UNION of siderophore biosynthesis, iron metabolism, catalases, SODs, "
            "and glutathione/thioredoxin defense systems. INTERSECT with pathogenesis "
            "(GO:0009405) to identify virulence-relevant redox defense."
        ),
        site_id="fungidb",
        step_tree={
            "id": "root_iron_redox",
            "displayName": "Pathogenic Iron & Redox Genes",
            "operator": "INTERSECT",
            "primaryInput": {
                "id": "all_iron_redox",
                "displayName": "Iron + Redox Defense",
                "operator": "UNION",
                "primaryInput": {
                    "id": "iron_system",
                    "displayName": "Iron Acquisition",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "leaf_siderophore",
                        "displayName": "Siderophore Biosynthesis",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(ORGANISM, "siderophore"),
                    },
                    "secondaryInput": {
                        "id": "leaf_iron",
                        "displayName": "Iron Metabolism",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(ORGANISM, "iron"),
                    },
                },
                "secondaryInput": {
                    "id": "redox_defense",
                    "displayName": "Redox Defense Systems",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "cat_sod",
                        "displayName": "Catalases + SODs",
                        "operator": "UNION",
                        "primaryInput": {
                            "id": "leaf_catalase",
                            "displayName": "Catalases",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(ORGANISM, "catalase"),
                        },
                        "secondaryInput": {
                            "id": "leaf_sod",
                            "displayName": "Superoxide Dismutases",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                ORGANISM, '"superoxide dismutase"'
                            ),
                        },
                    },
                    "secondaryInput": {
                        "id": "leaf_oxidative_stress",
                        "displayName": "GO: Oxidative Stress",
                        "searchName": "GenesByGoTerm",
                        "parameters": _go_search_params(ORGANISM, "GO:0006979"),
                    },
                },
            },
            "secondaryInput": {
                "id": "leaf_pathogenesis_2",
                "displayName": "GO: Pathogenesis",
                "searchName": "GenesByGoTerm",
                "parameters": _go_search_params(ORGANISM, "GO:0009405"),
            },
        },
        control_set=ControlSetDef(
            name="A. fumigatus Iron & Redox Defense (curated)",
            positive_ids=(
                AFUM_CATALASES[:3]
                + AFUM_SOD[:3]
                + AFUM_SIDEROPHORES[:4]
                + AFUM_IRON_GENES
                + AFUM_GLUTATHIONE[:3]
            ),
            negative_ids=AFUM_RIBOSOMAL[:16],
            provenance_notes=(
                "Positives: catalases, SODs, siderophore biosynthesis genes, "
                "iron homeostasis regulators (sidA, hapX, sreA), and glutathione "
                "system — virulence-relevant oxidative defense. "
                "Negatives: ribosomal structural proteins."
            ),
            tags=["iron", "redox", "virulence", "aspergillus", "seed"],
        ),
    ),
]
