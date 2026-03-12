"""Seed definitions for HostDB.

Human innate immunity, pathogen defense, cytokine networks, autophagy, and
transcriptomic responses to parasitic infection (malaria, T. gondii, Leishmania,
Candida, Giardia). All gene IDs are real Ensembl ENSG identifiers verified
against HostDB (Homo sapiens REF), Mar 2026.
"""

from __future__ import annotations

import json

from veupath_chatbot.services.experiment.seed.types import ControlSetDef, SeedDef

# ---------------------------------------------------------------------------
# Organism constant
# ---------------------------------------------------------------------------

HS_ORG = "Homo sapiens REF"

# ---------------------------------------------------------------------------
# Gene ID lists — real Ensembl IDs from HostDB
# ---------------------------------------------------------------------------

# Toll-like receptors (TLR1-TLR10 + adaptor pseudogenes)
HOSTDB_TLRS = [
    "ENSG00000174125",  # TLR1
    "ENSG00000137462",  # TLR2
    "ENSG00000164342",  # TLR3
    "ENSG00000136869",  # TLR4
    "ENSG00000187554",  # TLR5
    "ENSG00000174130",  # TLR6
    "ENSG00000196664",  # TLR7
    "ENSG00000101916",  # TLR8
    "ENSG00000239732",  # TLR9
    "ENSG00000174123",  # TLR10
    "ENSG00000233338",  # TLR pseudogene
    "ENSG00000234512",  # TLR pseudogene
]

# NLR family: NLRP inflammasome sensors + NOD receptors
HOSTDB_NLRS = [
    "ENSG00000091592",  # NLRP1
    "ENSG00000162711",  # NLRP2
    "ENSG00000179709",  # NLRP3 (inflammasome)
    "ENSG00000160505",  # NLRP4
    "ENSG00000171487",  # NLRP5
    "ENSG00000174885",  # NLRP6
    "ENSG00000167634",  # NLRP7
    "ENSG00000179873",  # NLRP8
    "ENSG00000142405",  # NLRP9
    "ENSG00000022556",  # NLRP10
    "ENSG00000158077",  # NLRP11
    "ENSG00000182261",  # NLRP12
    "ENSG00000185792",  # NLRP13
    "ENSG00000173572",  # NLRP14
    "ENSG00000215174",  # NLRP pseudogene
    "ENSG00000256581",  # NLRP pseudogene
    "ENSG00000277883",  # NLRP pseudogene
    "ENSG00000167207",  # NOD1 (CARD4)
    "ENSG00000106100",  # NOD2 (CARD15)
    "ENSG00000156574",  # NODAL
]

# Complement system components (C1q, C3, C5, C8, C9, CFB)
HOSTDB_COMPLEMENT = [
    "ENSG00000173369",  # C1QA
    "ENSG00000173372",  # C1QB
    "ENSG00000159189",  # C1QC
    "ENSG00000144119",  # C1QL1
    "ENSG00000165985",  # C1QL2
    "ENSG00000108561",  # C1R
    "ENSG00000131094",  # C1S
    "ENSG00000000971",  # CFH (complement factor H)
    "ENSG00000243649",  # CFB (complement factor B)
    "ENSG00000125730",  # C3
    "ENSG00000106804",  # C5
    "ENSG00000021852",  # C8A
    "ENSG00000157131",  # C8B
    "ENSG00000176919",  # C8G
    "ENSG00000113600",  # C9
    "ENSG00000116785",  # CFHR1
    "ENSG00000080910",  # CFHR2
    "ENSG00000117322",  # CR1
    "ENSG00000134365",  # CFHR3
    "ENSG00000134389",  # CFHR4
    "ENSG00000134830",  # C5AR1
    "ENSG00000197405",  # C5AR2
    "ENSG00000126759",  # CFP (properdin)
    "ENSG00000182326",  # C1RL
    "ENSG00000244414",  # CFHR5
    "ENSG00000139178",  # C1GALT1
    "ENSG00000215353",  # complement-related
    "ENSG00000197766",  # CFD (complement factor D)
    "ENSG00000197721",  # CFI (complement factor I)
    "ENSG00000123838",  # C4BPA
    "ENSG00000123843",  # C4BPB
    "ENSG00000203710",  # CR1L
    "ENSG00000186897",  # C1GALT1C1
    "ENSG00000167798",  # CDH2 (linked complement)
    "ENSG00000171860",  # C3AR1
    "ENSG00000159403",  # C1R-like
    "ENSG00000166278",  # C2 (complement C2)
    "ENSG00000205403",  # CFI-related
    "ENSG00000213409",  # complement-related
    "ENSG00000260134",  # complement pseudogene
    "ENSG00000261245",  # complement pseudogene
    "ENSG00000244255",  # complement-related
    "ENSG00000244731",  # complement-related
    "ENSG00000273844",  # complement-related
    "ENSG00000276605",  # complement pseudogene
    "ENSG00000285986",  # complement pseudogene
    "ENSG00000224389",  # complement pseudogene
]

# Interferons (IFN-alpha/beta/gamma family + IRFs)
HOSTDB_INTERFERONS = [
    "ENSG00000111537",  # IFNG (interferon gamma)
    "ENSG00000147873",  # IFNA1 (interferon alpha 1)
    "ENSG00000147896",  # IFNA2
    "ENSG00000147885",  # IFNA4
    "ENSG00000159110",  # IFNA5
    "ENSG00000159128",  # IFNA6
    "ENSG00000182393",  # IFNA7
    "ENSG00000120235",  # IFNA8
    "ENSG00000137959",  # IFNA10
    "ENSG00000185885",  # IFNA13
    "ENSG00000137965",  # IFNA14
    "ENSG00000185745",  # IFNA16
    "ENSG00000171855",  # IFNA17
    "ENSG00000172183",  # IFNA21
    "ENSG00000186803",  # IFNB1 (interferon beta)
    "ENSG00000185436",  # IFNW1 (interferon omega)
    "ENSG00000177047",  # IFNE (interferon epsilon)
    "ENSG00000120242",  # IFNL1 (interferon lambda)
    "ENSG00000184584",  # IFNL2
    "ENSG00000197110",  # IFNL3
    "ENSG00000185201",  # IFNL4
    # IRF transcription factors (interferon regulatory factors)
    "ENSG00000125347",  # IRF1
    "ENSG00000168310",  # IRF2
    "ENSG00000126456",  # IRF3
    "ENSG00000185507",  # IRF4
    "ENSG00000128604",  # IRF5
    "ENSG00000168264",  # IRF6
    "ENSG00000137265",  # IRF7
    "ENSG00000140968",  # IRF8
    "ENSG00000213928",  # IRF9
    "ENSG00000117595",  # IRF2BP1
    "ENSG00000119669",  # IRF2BP2
    "ENSG00000170604",  # IRF2BPL
    "ENSG00000251347",  # IRF pseudogene
    "ENSG00000271646",  # IRF pseudogene
]

# Interleukins (IL-1 family, IL-6, IL-10, IL-12 + receptors)
HOSTDB_INTERLEUKINS = [
    "ENSG00000115008",  # IL1A
    "ENSG00000125538",  # IL1B
    "ENSG00000136689",  # IL1RN (IL-1 receptor antagonist)
    "ENSG00000115594",  # IL1R1
    "ENSG00000115590",  # IL1R2
    "ENSG00000112115",  # IL1RL1 (ST2)
    "ENSG00000112116",  # IL1RL2
    "ENSG00000096996",  # IL12A
    "ENSG00000113302",  # IL12B
    "ENSG00000081985",  # IL12RB1
    "ENSG00000168811",  # IL12RB2
    "ENSG00000110324",  # IL10
    "ENSG00000136634",  # IL10RA
    "ENSG00000115602",  # IL1RAP
    "ENSG00000115598",  # IL1RAPL1
    "ENSG00000115604",  # IL1RAPL2
    "ENSG00000115607",  # IL18RAP
    "ENSG00000056736",  # IL1F10
    "ENSG00000095752",  # IL11
    "ENSG00000110944",  # IL23A
    "ENSG00000113525",  # IL5
    "ENSG00000113520",  # IL4
    "ENSG00000134460",  # IL2
    "ENSG00000136244",  # IL6
    "ENSG00000136688",  # IL6ST
    "ENSG00000134352",  # IL6R
    "ENSG00000136694",  # IL17A
    "ENSG00000136695",  # IL17B
    "ENSG00000136696",  # IL17C
    "ENSG00000145839",  # IL2RA (CD25)
    "ENSG00000137496",  # IL18BP
    "ENSG00000142224",  # IL33
    "ENSG00000100385",  # IL2RB
    "ENSG00000164136",  # IL15
    "ENSG00000164509",  # IL21
    "ENSG00000163701",  # IL17F
]

# TNF superfamily members
HOSTDB_TNF = [
    "ENSG00000232810",  # TNF (tumor necrosis factor)
    "ENSG00000120337",  # TNFSF18 (GITRL)
    "ENSG00000125657",  # TNFSF14 (LIGHT)
    "ENSG00000120949",  # TNFRSF8 (CD30)
    "ENSG00000141655",  # TNFRSF11A (RANK)
    "ENSG00000157873",  # TNFRSF14 (HVEM)
    "ENSG00000048462",  # TNFRSF21 (DR6)
    "ENSG00000117586",  # TNFSF4 (OX40L)
    "ENSG00000067182",  # TNFRSF1A (TNF-R1)
    "ENSG00000028137",  # TNFRSF1B (TNF-R2)
    "ENSG00000049249",  # TNFRSF9 (4-1BB)
    "ENSG00000102524",  # TNFSF13B (BAFF)
    "ENSG00000104689",  # TNFRSF10A (TRAIL-R1)
    "ENSG00000106952",  # TNFSF8 (CD30L)
    "ENSG00000109079",  # TNFAIP1
    "ENSG00000118503",  # TNFAIP3 (A20)
    "ENSG00000120659",  # TNFSF11 (RANKL)
    "ENSG00000120889",  # TNFRSF10B (TRAIL-R2)
    "ENSG00000121858",  # TNFSF10 (TRAIL)
    "ENSG00000123610",  # TNFAIP6 (TSG-6)
    "ENSG00000125735",  # TNFSF12 (TWEAK)
    "ENSG00000127863",  # TNFRSF3 (LTBR)
    "ENSG00000145779",  # TNFAIP8
    "ENSG00000146072",  # TNFRSF21
    "ENSG00000159958",  # TNFRSF13C (BAFFR)
    "ENSG00000161955",  # TNFSF13 (APRIL)
    "ENSG00000163154",  # TNFAIP8L2
    "ENSG00000164761",  # TNFRSF12A (Fn14)
    "ENSG00000173530",  # TNFRSF6B (DcR3)
    "ENSG00000173535",  # TNFRSF10C (TRAIL-R3)
    "ENSG00000181634",  # TNFSF15 (TL1A)
    "ENSG00000183578",  # TNFAIP8L3
    "ENSG00000185215",  # TNFAIP2
    "ENSG00000185361",  # TNFAIP8L1
    "ENSG00000186827",  # TNFRSF4 (OX40)
    "ENSG00000186891",  # TNFRSF18 (GITR)
    "ENSG00000215788",  # TNF pseudogene
    "ENSG00000006327",  # TNFRSF25
    "ENSG00000238164",  # TNF pseudogene
    "ENSG00000239697",  # TNF pseudogene
    "ENSG00000240505",  # TNF pseudogene
    "ENSG00000243509",  # TNF pseudogene
    "ENSG00000248871",  # TNF pseudogene
    "ENSG00000253930",  # TNF pseudogene
]

# NF-kB signaling pathway core genes
HOSTDB_NFKB = [
    "ENSG00000109320",  # NFKB1 (p50)
    "ENSG00000077150",  # NFKB2 (p52)
    "ENSG00000100906",  # NFKBIA (IkB-alpha)
    "ENSG00000104825",  # NFKBIB (IkB-beta)
    "ENSG00000144802",  # NFKBIE (IkB-epsilon)
    "ENSG00000146232",  # NFKBIZ (IkB-zeta)
    "ENSG00000167604",  # NFKBID (IkB-NS)
    "ENSG00000204498",  # NFKBIL1
]

# JAK-STAT signaling pathway
HOSTDB_JAK_STAT = [
    "ENSG00000162434",  # JAK1
    "ENSG00000096968",  # JAK2
    "ENSG00000105639",  # JAK3
    "ENSG00000152969",  # TYK2 (JAK family)
    "ENSG00000115415",  # STAT1
    "ENSG00000170581",  # STAT2
    "ENSG00000168610",  # STAT3
    "ENSG00000138378",  # STAT4
    "ENSG00000126561",  # STAT5A
    "ENSG00000126549",  # STAT5B
    "ENSG00000166888",  # STAT6
    "ENSG00000173757",  # STAT pseudogene
    "ENSG00000176049",  # JAK2 pseudogene
    "ENSG00000188385",  # JAK3 pseudogene
    "ENSG00000280780",  # JAK pseudogene
]

# MAPK cascade (MAP3Ks + MAP2Ks + MAPKs)
HOSTDB_MAPK = [
    # MAP3Ks
    "ENSG00000006062",  # MAP3K14 (NIK)
    "ENSG00000006432",  # MAP3K9
    "ENSG00000073803",  # MAP3K13
    "ENSG00000085511",  # MAP3K4
    "ENSG00000091436",  # MAP3K11
    "ENSG00000095015",  # MAP3K1
    "ENSG00000107968",  # MAP3K8 (TPL2)
    "ENSG00000130758",  # MAP3K2
    "ENSG00000135341",  # MAP3K7 (TAK1)
    "ENSG00000139625",  # MAP3K12
    "ENSG00000142733",  # MAP3K6
    "ENSG00000143674",  # MAP3K5 (ASK1)
    "ENSG00000156265",  # MAP3K3
    "ENSG00000169967",  # MAP3K10
    "ENSG00000173327",  # MAP3K15
    # MAP2Ks
    "ENSG00000169032",  # MAP2K1 (MEK1)
    "ENSG00000126934",  # MAP2K2 (MEK2)
    "ENSG00000034152",  # MAP2K3
    "ENSG00000065559",  # MAP2K4 (MKK4)
    "ENSG00000137764",  # MAP2K5
    "ENSG00000108984",  # MAP2K6
    "ENSG00000076984",  # MAP2K7
    # MAPKs
    "ENSG00000102882",  # MAPK3 (ERK1)
    "ENSG00000100030",  # MAPK1 (ERK2)
    "ENSG00000112062",  # MAPK14 (p38-alpha)
    "ENSG00000185386",  # MAPK11 (p38-beta)
    "ENSG00000138795",  # MAPK12 (p38-gamma)
    "ENSG00000156711",  # MAPK13 (p38-delta)
    "ENSG00000107643",  # MAPK8 (JNK1)
    "ENSG00000050748",  # MAPK9 (JNK2)
    "ENSG00000109339",  # MAPK10 (JNK3)
    "ENSG00000141639",  # MAPK4 (ERK4)
    "ENSG00000197442",  # MAPK15 (ERK7)
]

# MyD88 / IRAK / TRAF signaling adaptors
HOSTDB_SIGNALING_ADAPTORS = [
    "ENSG00000172936",  # MYD88
    "ENSG00000090376",  # IRAK1
    "ENSG00000134070",  # IRAK2
    "ENSG00000146243",  # IRAK3 (IRAK-M)
    "ENSG00000184216",  # IRAK4
    "ENSG00000198001",  # IRAK1BP1
    "ENSG00000056558",  # TRAF1
    "ENSG00000127191",  # TRAF2
    "ENSG00000131323",  # TRAF3
    "ENSG00000076604",  # TRAF4
    "ENSG00000082512",  # TRAF5
    "ENSG00000175104",  # TRAF6
    "ENSG00000009790",  # TRAF3IP1
    "ENSG00000056972",  # TRAF3IP2
    "ENSG00000131653",  # TRAF3IP3
    "ENSG00000135148",  # TRAFD1
    "ENSG00000204104",  # TRAF pseudogene
    "ENSG00000226557",  # TRAF pseudogene
    "ENSG00000231889",  # TRAF pseudogene
]

# Caspases (apoptosis/inflammation)
HOSTDB_CASPASES = [
    "ENSG00000137752",  # CASP1 (ICE, inflammasome)
    "ENSG00000106144",  # CASP2
    "ENSG00000164305",  # CASP3
    "ENSG00000196954",  # CASP4
    "ENSG00000137757",  # CASP5
    "ENSG00000138794",  # CASP6
    "ENSG00000165806",  # CASP7
    "ENSG00000064012",  # CASP8
    "ENSG00000132906",  # CASP9
    "ENSG00000003400",  # CASP10
    "ENSG00000118412",  # CASP14 (keratinocyte differentiation)
    "ENSG00000105141",  # CASP pseudogene
    "ENSG00000204403",  # CASP pseudogene
    "ENSG00000228146",  # CASP pseudogene
    "ENSG00000235505",  # CASP pseudogene
    "ENSG00000237033",  # CASP pseudogene
    "ENSG00000254750",  # CASP pseudogene
    "ENSG00000255430",  # CASP pseudogene
]

# Autophagy machinery (ATG genes + BECN1 + LAMP)
HOSTDB_AUTOPHAGY = [
    "ENSG00000101844",  # ATG2A
    "ENSG00000168010",  # ATG2B
    "ENSG00000066739",  # ATG3
    "ENSG00000175224",  # ATG4A
    "ENSG00000168397",  # ATG4B
    "ENSG00000057663",  # ATG4C
    "ENSG00000152348",  # ATG4D
    "ENSG00000085978",  # ATG5
    "ENSG00000123395",  # ATG7
    "ENSG00000144848",  # ATG9A
    "ENSG00000130734",  # ATG9B
    "ENSG00000152223",  # ATG10
    "ENSG00000110046",  # ATG12
    "ENSG00000125703",  # ATG13
    "ENSG00000145782",  # ATG14
    "ENSG00000126775",  # ATG16L1
    # Beclin/LAMP
    "ENSG00000126581",  # BECN1 (autophagy initiation)
    "ENSG00000196289",  # BECN2
    "ENSG00000005893",  # LAMP1 (lysosome marker)
    "ENSG00000078081",  # LAMP2
    "ENSG00000125869",  # LAMP3
    "ENSG00000185896",  # LAMP5
    # Other autophagy genes
    "ENSG00000083290",  # ULK1 (autophagy initiating kinase)
    "ENSG00000116299",  # KIAA1324 (autophagy)
    "ENSG00000149547",  # EI24 (autophagy)
    "ENSG00000177169",  # ULK1-related
    "ENSG00000156171",  # DRAM2 (damage-regulated autophagy modulator)
    "ENSG00000163820",  # FYCO1 (autophagosome transport)
    "ENSG00000164659",  # WIPI1 (WD-repeat PtdIns)
    "ENSG00000165507",  # WIPI2
    "ENSG00000136048",  # DRAM1 (damage-regulated autophagy modulator)
    "ENSG00000149639",  # SOGA1 (autophagy)
    "ENSG00000181652",  # ATG101 (autophagy)
    "ENSG00000188554",  # NBR1 (autophagy receptor)
    "ENSG00000197548",  # ATG4A-related
    "ENSG00000198925",  # ATG-related
    "ENSG00000102445",  # RUBCNL (autophagy)
    "ENSG00000110497",  # AMBRA1 (autophagy)
]

# Defensins (alpha and beta)
HOSTDB_DEFENSINS = [
    # Alpha-defensins
    "ENSG00000164816",  # DEFA1
    "ENSG00000164821",  # DEFA3
    "ENSG00000164822",  # DEFA4
    "ENSG00000206042",  # DEFA5
    "ENSG00000206047",  # DEFA6
    "ENSG00000223629",  # DEFA pseudogene
    "ENSG00000233238",  # DEFA pseudogene
    "ENSG00000233531",  # DEFA pseudogene
    "ENSG00000234178",  # DEFA pseudogene
    "ENSG00000239839",  # DEFA pseudogene
    "ENSG00000240247",  # DEFA pseudogene
    # Beta-defensins
    "ENSG00000088782",  # DEFB1
    "ENSG00000125788",  # DEFB4A
    "ENSG00000125903",  # DEFB103A
    "ENSG00000131068",  # DEFB104A
    "ENSG00000164825",  # DEFB105A
    "ENSG00000171711",  # DEFB106A
    "ENSG00000176782",  # DEFB107A
    "ENSG00000176797",  # DEFB108A
    "ENSG00000177023",  # DEFB110
    "ENSG00000177243",  # DEFB112
    "ENSG00000177257",  # DEFB113
    "ENSG00000177684",  # DEFB114
    "ENSG00000178591",  # DEFB115
    "ENSG00000180383",  # DEFB116
    "ENSG00000180424",  # DEFB118
    "ENSG00000180483",  # DEFB119
    "ENSG00000180872",  # DEFB121
    "ENSG00000184276",  # DEFB123
    "ENSG00000185982",  # DEFB124
    "ENSG00000186146",  # DEFB125
    "ENSG00000186458",  # DEFB126
    "ENSG00000186562",  # DEFB127
    "ENSG00000186572",  # DEFB128
    "ENSG00000186579",  # DEFB129
    "ENSG00000186599",  # DEFB130A
    "ENSG00000187082",  # DEFB131A
    "ENSG00000188438",  # DEFB132
    "ENSG00000198129",  # DEFB133
    "ENSG00000203970",  # DEFB134
    "ENSG00000204547",  # DEFB135
    "ENSG00000204548",  # DEFB136
    "ENSG00000205882",  # DEFB pseudogene
    "ENSG00000205883",  # DEFB pseudogene
    "ENSG00000205884",  # DEFB pseudogene
    "ENSG00000205989",  # DEFB pseudogene
    "ENSG00000206034",  # DEFB pseudogene
    "ENSG00000212717",  # DEFB pseudogene
    "ENSG00000214642",  # DEFB pseudogene
    "ENSG00000214643",  # DEFB pseudogene
    "ENSG00000215371",  # DEFB pseudogene
    "ENSG00000215545",  # DEFB pseudogene
    "ENSG00000215547",  # DEFB pseudogene
    "ENSG00000225805",  # DEFB pseudogene
    "ENSG00000229907",  # DEFB pseudogene
    "ENSG00000232773",  # DEFB pseudogene
    "ENSG00000232948",  # DEFB pseudogene
    "ENSG00000233050",  # DEFB pseudogene
    "ENSG00000237215",  # DEFB pseudogene
    "ENSG00000242296",  # DEFB pseudogene
    "ENSG00000244050",  # DEFB pseudogene
    "ENSG00000254507",  # DEFB pseudogene
    "ENSG00000254623",  # DEFB pseudogene
    "ENSG00000254700",  # DEFB pseudogene
    "ENSG00000254866",  # DEFB pseudogene
    "ENSG00000255157",  # DEFB pseudogene
    "ENSG00000255544",  # DEFB pseudogene
]

# C-type lectin receptors (CLECs) -- pattern recognition
HOSTDB_CLECS = [
    "ENSG00000038532",  # CLEC4A
    "ENSG00000069493",  # CLEC2D
    "ENSG00000104938",  # CLEC4M (DC-SIGN related)
    "ENSG00000105472",  # CLEC14A
    "ENSG00000110852",  # CLEC2B
    "ENSG00000111729",  # CLEC7A (Dectin-1)
    "ENSG00000132514",  # CLEC10A (MGL)
    "ENSG00000140839",  # CLEC12B
    "ENSG00000150048",  # CLEC1A
    "ENSG00000152672",  # CLEC4G
    "ENSG00000157322",  # CLEC6A (Dectin-2)
    "ENSG00000157335",  # CLEC12A (Mincle-related)
    "ENSG00000163815",  # CLEC3B (tetranectin)
    "ENSG00000165682",  # CLEC1B
    "ENSG00000166509",  # CLEC3A
    "ENSG00000166523",  # CLEC4E (Mincle)
    "ENSG00000166527",  # CLEC4D (MCL)
    "ENSG00000172243",  # CLEC11A
    "ENSG00000172322",  # CLEC16A
    "ENSG00000176435",  # CLEC4C (BDCA-2)
    "ENSG00000182566",  # CLEC9A (DNGR-1)
    "ENSG00000184293",  # CLEC17A
    "ENSG00000187912",  # CLEC5A (MDL-1)
    "ENSG00000188393",  # CLEC2L
    "ENSG00000188585",  # CLEC18A
    "ENSG00000197992",  # CLEC4F
    "ENSG00000198178",  # CLEC4A
    "ENSG00000205846",  # CLEC18B
    "ENSG00000231560",  # CLEC pseudogene
    "ENSG00000236279",  # CLEC pseudogene
    "ENSG00000256660",  # CLEC pseudogene
    "ENSG00000258227",  # CLEC18C
    "ENSG00000261210",  # CLEC pseudogene
    "ENSG00000267453",  # CLEC pseudogene
    "ENSG00000268297",  # CLEC pseudogene
]

# Phagocytosis / Fc receptors / scavenger receptors
HOSTDB_PHAGOCYTOSIS = [
    "ENSG00000132185",  # FCRLA
    "ENSG00000132704",  # FCRLB
    "ENSG00000143297",  # FCGR2A (CD32)
    "ENSG00000160856",  # FCRL3
    "ENSG00000162746",  # FCRLB
    "ENSG00000163518",  # FCRL4
    "ENSG00000163534",  # FCRL5
    "ENSG00000181036",  # FCRL6
    "ENSG00000169896",  # ITGAM (CD11b, CR3)
    "ENSG00000177575",  # CD163 (scavenger receptor)
    "ENSG00000260314",  # MRC1 (mannose receptor, CD206)
    "ENSG00000170458",  # CD14 (LPS co-receptor)
    "ENSG00000010610",  # CD4 (T-cell co-receptor)
]

# Heat shock proteins
HOSTDB_HSP = [
    "ENSG00000204388",  # HSPA1A (HSP70)
    "ENSG00000204389",  # HSPA1B (HSP70)
    "ENSG00000204390",  # HSPA1L (HSP70)
    "ENSG00000120694",  # HSPH1 (HSP105)
    "ENSG00000126803",  # HSPA2
    "ENSG00000132622",  # HSPA12B
    "ENSG00000133265",  # HSPBP1
    "ENSG00000142798",  # HSPG2 (perlecan)
    "ENSG00000144381",  # HSPD1 (HSP60)
    "ENSG00000080824",  # HSP90AA1
    "ENSG00000096384",  # HSP90AB1
    "ENSG00000166598",  # HSP90B1 (GRP94)
    "ENSG00000155304",  # HSPA9 (mortalin)
    "ENSG00000113013",  # HSPA4 (APG-2)
    "ENSG00000115541",  # HSPE1 (HSP10)
    "ENSG00000152137",  # HSPB8
    "ENSG00000164070",  # HSPA4L
    "ENSG00000169087",  # HSPBAP1
    "ENSG00000109971",  # HSPA8 (HSC70, constitutive)
    "ENSG00000106211",  # HSPB1 (HSP27)
]


# ---------------------------------------------------------------------------
# Parameter helpers
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


def _text_search_params(
    organism: str, expression: str, fields: list[str] | None = None
) -> dict[str, str]:
    """Build GenesByText parameters."""
    if fields is None:
        fields = ["product"]
    return {
        "text_search_organism": _org([organism]),
        "text_expression": expression,
        "document_type": "gene",
        "text_fields": json.dumps(fields),
    }


def _text_name_search(organism: str, pattern: str) -> dict[str, str]:
    """Build GenesByText parameters searching gene name/symbol."""
    return _text_search_params(organism, pattern, ["name"])


def _rnaseq_fc_params(
    *,
    dataset_url: str,
    profileset: str,
    direction: str,
    ref_samples: list[str],
    comp_samples: list[str],
    fold_change: str = "2",
    hard_floor: str,
    protein_coding: str = "yes",
    ref_op: str = "average1",
    comp_op: str = "average1",
) -> dict[str, str]:
    """Build RNA-Seq fold-change search parameters."""
    return {
        "dataset_url": dataset_url,
        "profileset_generic": profileset,
        "regulated_dir": direction,
        "samples_fc_ref_generic": json.dumps(ref_samples),
        "min_max_avg_ref": ref_op,
        "samples_fc_comp_generic": json.dumps(comp_samples),
        "min_max_avg_comp": comp_op,
        "fold_change": fold_change,
        "hard_floor": hard_floor,
        "protein_coding_only": protein_coding,
    }


def _tm_domain_params(
    organism: str, min_tm: str = "1", max_tm: str = "99"
) -> dict[str, str]:
    """Build GenesByTransmembraneDomains parameters."""
    return {
        "organism": _org([organism]),
        "min_tm": min_tm,
        "max_tm": max_tm,
    }


def _signal_peptide_params(organism: str) -> dict[str, str]:
    """Build GenesWithSignalPeptide parameters."""
    return {"organism": _org([organism])}


def _mw_params(organism: str, min_mw: str, max_mw: str) -> dict[str, str]:
    """Build GenesByMolecularWeight parameters."""
    return {
        "organism": _org([organism]),
        "min_molecular_weight": min_mw,
        "max_molecular_weight": max_mw,
    }


def _gene_type_params(
    organism: str, gene_type: str = "protein coding"
) -> dict[str, str]:
    """Build GenesByGeneType parameters."""
    return {
        "organism": _org([organism]),
        "geneType": json.dumps([gene_type]),
        "includePseudogenes": "No",
    }


# ---------------------------------------------------------------------------
# Strategy Definitions (6 strategies)
# ---------------------------------------------------------------------------

SEEDS: list[SeedDef] = [
    # ===================================================================
    # 1) Hs Innate Immunity Signaling Network (12 nodes)
    # ===================================================================
    SeedDef(
        name="Hs Innate Immunity Signaling Network",
        description=(
            "Comprehensive innate immune signaling: TLR/NLR/NOD pattern recognition "
            "receptors INTERSECTED with downstream signaling adaptors (MYD88, IRAK, "
            "TRAF, NF-kB, IRF), UNIONED with JAK-STAT pathway and inflammasome caspases. "
            "Models the complete signaling cascade from pathogen recognition to "
            "transcriptional response."
        ),
        site_id="hostdb",
        step_tree={
            "id": "root_union",
            "displayName": "Innate Immunity Network",
            "operator": "UNION",
            "primaryInput": {
                "id": "prr_intersect_signaling",
                "displayName": "PRR-Signaling Crosstalk",
                "operator": "INTERSECT",
                "primaryInput": {
                    "id": "all_prrs",
                    "displayName": "All PRRs (TLR+NLR+NOD)",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "leaf_tlr",
                        "displayName": "Toll-like Receptors (TLR*)",
                        "searchName": "GenesByText",
                        "parameters": _text_name_search(HS_ORG, "TLR*"),
                    },
                    "secondaryInput": {
                        "id": "nlr_nod_union",
                        "displayName": "NLR + NOD receptors",
                        "operator": "UNION",
                        "primaryInput": {
                            "id": "leaf_nlrp",
                            "displayName": "NLRP Family",
                            "searchName": "GenesByText",
                            "parameters": _text_name_search(HS_ORG, "NLRP*"),
                        },
                        "secondaryInput": {
                            "id": "leaf_nod",
                            "displayName": "NOD Receptors",
                            "searchName": "GenesByText",
                            "parameters": _text_name_search(HS_ORG, "NOD*"),
                        },
                    },
                },
                "secondaryInput": {
                    "id": "all_signaling",
                    "displayName": "Signaling Cascades",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "leaf_adaptors",
                        "displayName": "MYD88/IRAK/TRAF Adaptors",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            HS_ORG, "MYD88 OR IRAK OR TRAF", ["name"]
                        ),
                    },
                    "secondaryInput": {
                        "id": "tf_union",
                        "displayName": "Transcription Factors",
                        "operator": "UNION",
                        "primaryInput": {
                            "id": "leaf_nfkb",
                            "displayName": "NF-kB Subunits",
                            "searchName": "GenesByText",
                            "parameters": _text_name_search(HS_ORG, "NFKB*"),
                        },
                        "secondaryInput": {
                            "id": "leaf_irf",
                            "displayName": "IRF Factors",
                            "searchName": "GenesByText",
                            "parameters": _text_name_search(HS_ORG, "IRF*"),
                        },
                    },
                },
            },
            "secondaryInput": {
                "id": "jakstat_casp_union",
                "displayName": "JAK-STAT + Inflammasome",
                "operator": "UNION",
                "primaryInput": {
                    "id": "leaf_jakstat",
                    "displayName": "JAK-STAT Pathway",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(HS_ORG, "JAK OR STAT", ["name"]),
                },
                "secondaryInput": {
                    "id": "leaf_caspases",
                    "displayName": "Inflammasome Caspases",
                    "searchName": "GenesByText",
                    "parameters": _text_name_search(HS_ORG, "CASP*"),
                },
            },
        },
        control_set=ControlSetDef(
            name="Innate Immunity Panel (curated)",
            positive_ids=(
                HOSTDB_TLRS[:8]
                + HOSTDB_NLRS[:6]
                + HOSTDB_SIGNALING_ADAPTORS[:6]
                + HOSTDB_NFKB[:4]
                + HOSTDB_JAK_STAT[:6]
                + HOSTDB_CASPASES[:5]
            ),
            negative_ids=HOSTDB_HSP[:20],
            provenance_notes=(
                "Positives: TLRs, NLRPs, MYD88/IRAK/TRAF adaptors, NF-kB subunits, "
                "JAK-STAT, and inflammasome caspases — all innate immunity signaling. "
                "Negatives: heat shock proteins — housekeeping chaperones with no "
                "direct innate immune signaling role."
            ),
            tags=["innate-immunity", "signaling", "hostdb", "seed"],
        ),
    ),
    # ===================================================================
    # 2) Hs Pathogen Defense Arsenal (11 nodes)
    # ===================================================================
    SeedDef(
        name="Hs Pathogen Defense Arsenal",
        description=(
            "Multi-layered pathogen defense: secreted antimicrobial peptides "
            "(defensins + cathelicidins with signal peptides), complement system "
            "components, phagocytic receptors (Fc receptors, CR3), and surface "
            "C-type lectin receptors. Models effector mechanisms that directly "
            "kill or engulf pathogens."
        ),
        site_id="hostdb",
        step_tree={
            "id": "root_defense",
            "displayName": "Pathogen Defense Arsenal",
            "operator": "UNION",
            "primaryInput": {
                "id": "secreted_amps",
                "displayName": "Secreted Antimicrobials",
                "operator": "INTERSECT",
                "primaryInput": {
                    "id": "amp_union",
                    "displayName": "Antimicrobial Peptides",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "leaf_defensins",
                        "displayName": "Defensins",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(HS_ORG, "defensin"),
                    },
                    "secondaryInput": {
                        "id": "leaf_cathelicidin",
                        "displayName": "Cathelicidins",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(HS_ORG, "cathelicidin"),
                    },
                },
                "secondaryInput": {
                    "id": "leaf_signal_pep",
                    "displayName": "Signal Peptide (Secreted)",
                    "searchName": "GenesWithSignalPeptide",
                    "parameters": _signal_peptide_params(HS_ORG),
                },
            },
            "secondaryInput": {
                "id": "complement_phago",
                "displayName": "Complement + Phagocytosis",
                "operator": "UNION",
                "primaryInput": {
                    "id": "complement_filtered",
                    "displayName": "Complement System",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "leaf_complement_all",
                        "displayName": "Complement Genes",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(HS_ORG, "complement"),
                    },
                    "secondaryInput": {
                        "id": "complement_minus_large",
                        "displayName": "Complement - Large MW",
                        "operator": "MINUS",
                        "primaryInput": {
                            "id": "leaf_complement_dup",
                            "displayName": "All Complement",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(HS_ORG, "complement"),
                        },
                        "secondaryInput": {
                            "id": "leaf_large_mw",
                            "displayName": "Very Large Proteins (>500kDa)",
                            "searchName": "GenesByMolecularWeight",
                            "parameters": _mw_params(HS_ORG, "500000", "99999999"),
                        },
                    },
                },
                "secondaryInput": {
                    "id": "phago_lectin_union",
                    "displayName": "Phagocytic + Lectin Receptors",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "leaf_phago_receptors",
                        "displayName": "Phagocytic Receptors",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            HS_ORG, "Fc receptor OR phagocyt*"
                        ),
                    },
                    "secondaryInput": {
                        "id": "clec_surface",
                        "displayName": "Surface C-type Lectins",
                        "operator": "INTERSECT",
                        "primaryInput": {
                            "id": "leaf_clec",
                            "displayName": "C-type Lectin Receptors",
                            "searchName": "GenesByText",
                            "parameters": _text_name_search(HS_ORG, "CLEC*"),
                        },
                        "secondaryInput": {
                            "id": "leaf_tm_domains",
                            "displayName": "Transmembrane (>=1 domain)",
                            "searchName": "GenesByTransmembraneDomains",
                            "parameters": _tm_domain_params(HS_ORG, "1", "99"),
                        },
                    },
                },
            },
        },
        control_set=ControlSetDef(
            name="Pathogen Defense Panel (curated)",
            positive_ids=(
                HOSTDB_DEFENSINS[:15]
                + HOSTDB_COMPLEMENT[:15]
                + HOSTDB_CLECS[:8]
                + HOSTDB_PHAGOCYTOSIS[:6]
            ),
            negative_ids=HOSTDB_AUTOPHAGY[:10] + HOSTDB_MAPK[:10],
            provenance_notes=(
                "Positives: defensins, complement factors, C-type lectins, Fc/phagocytic "
                "receptors — direct pathogen killing and engulfment. "
                "Negatives: autophagy machinery and MAPK cascade — intracellular "
                "processes without direct antimicrobial effector function."
            ),
            tags=["defense", "antimicrobial", "hostdb", "seed"],
        ),
    ),
    # ===================================================================
    # 3) Hs Cytokine Network (10 nodes)
    # ===================================================================
    SeedDef(
        name="Hs Cytokine Network",
        description=(
            "Complete cytokine signaling network: interferons (alpha/beta/gamma/lambda) "
            "filtered to protein-coding, secreted interleukins (IL-1/IL-6/IL-10/IL-12 "
            "families), TNF superfamily members (minus ribosomal noise), and secreted "
            "chemokines. Captures the full communication network of immune cells."
        ),
        site_id="hostdb",
        step_tree={
            "id": "root_cytokine",
            "displayName": "Cytokine Network",
            "operator": "UNION",
            "primaryInput": {
                "id": "ifn_il_union",
                "displayName": "Interferons + Interleukins",
                "operator": "UNION",
                "primaryInput": {
                    "id": "ifn_coding",
                    "displayName": "Protein-Coding Interferons",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "leaf_ifn",
                        "displayName": "Interferons",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(HS_ORG, "interferon"),
                    },
                    "secondaryInput": {
                        "id": "leaf_protein_coding",
                        "displayName": "Protein Coding Genes",
                        "searchName": "GenesByGeneType",
                        "parameters": _gene_type_params(HS_ORG),
                    },
                },
                "secondaryInput": {
                    "id": "il_secreted",
                    "displayName": "Secreted Interleukins",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "leaf_il",
                        "displayName": "Interleukins",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(HS_ORG, "interleukin"),
                    },
                    "secondaryInput": {
                        "id": "leaf_il_signal",
                        "displayName": "Signal Peptide",
                        "searchName": "GenesWithSignalPeptide",
                        "parameters": _signal_peptide_params(HS_ORG),
                    },
                },
            },
            "secondaryInput": {
                "id": "tnf_chemo_union",
                "displayName": "TNF + Chemokines",
                "operator": "UNION",
                "primaryInput": {
                    "id": "tnf_clean",
                    "displayName": "TNF Superfamily (clean)",
                    "operator": "MINUS",
                    "primaryInput": {
                        "id": "leaf_tnf",
                        "displayName": "TNF Superfamily",
                        "searchName": "GenesByText",
                        "parameters": _text_name_search(HS_ORG, "TNF*"),
                    },
                    "secondaryInput": {
                        "id": "leaf_ribosomal",
                        "displayName": "Ribosomal (noise filter)",
                        "searchName": "GenesByGoTerm",
                        "parameters": _go_search_params(HS_ORG, "GO:0003735"),
                    },
                },
                "secondaryInput": {
                    "id": "chemokine_secreted",
                    "displayName": "Secreted Chemokines",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "leaf_chemokine",
                        "displayName": "Chemokines",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(HS_ORG, "chemokine"),
                    },
                    "secondaryInput": {
                        "id": "leaf_chemo_signal",
                        "displayName": "Signal Peptide",
                        "searchName": "GenesWithSignalPeptide",
                        "parameters": _signal_peptide_params(HS_ORG),
                    },
                },
            },
        },
        control_set=ControlSetDef(
            name="Cytokine Panel (curated)",
            positive_ids=(
                HOSTDB_INTERFERONS[:15] + HOSTDB_INTERLEUKINS[:15] + HOSTDB_TNF[:15]
            ),
            negative_ids=HOSTDB_HSP[:10] + HOSTDB_DEFENSINS[:10],
            provenance_notes=(
                "Positives: interferons, interleukins, TNF superfamily — secreted "
                "immune signaling molecules. "
                "Negatives: HSPs (chaperones) and defensins (antimicrobial peptides) — "
                "not cytokine signaling."
            ),
            tags=["cytokine", "interferon", "interleukin", "hostdb", "seed"],
        ),
    ),
    # ===================================================================
    # 4) Hs Autophagy & Xenophagy Machinery (8 nodes)
    # ===================================================================
    SeedDef(
        name="Hs Autophagy & Xenophagy Machinery",
        description=(
            "Autophagy pathway for intracellular pathogen defense (xenophagy): "
            "ATG core genes (ATG2-ATG16), beclin complex, ubiquitin-autophagy "
            "crosstalk (ubiquitin genes with GO:autophagy annotation), all "
            "filtered to protein-coding. Critical for clearing intracellular "
            "Toxoplasma, Mycobacteria, and Salmonella."
        ),
        site_id="hostdb",
        step_tree={
            "id": "root_autophagy",
            "displayName": "Autophagy Machinery",
            "operator": "UNION",
            "primaryInput": {
                "id": "autophagy_coding",
                "displayName": "Autophagy Protein-Coding",
                "operator": "INTERSECT",
                "primaryInput": {
                    "id": "leaf_autophagy_text",
                    "displayName": "Autophagy Genes",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(HS_ORG, "autophagy"),
                },
                "secondaryInput": {
                    "id": "leaf_coding_auto",
                    "displayName": "Protein Coding",
                    "searchName": "GenesByGeneType",
                    "parameters": _gene_type_params(HS_ORG),
                },
            },
            "secondaryInput": {
                "id": "ub_atg_union",
                "displayName": "Ubiquitin-Autophagy + Core ATGs",
                "operator": "UNION",
                "primaryInput": {
                    "id": "ub_autophagy_intersect",
                    "displayName": "Ubiquitin x Autophagy",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "leaf_ubiquitin",
                        "displayName": "Ubiquitin System",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(HS_ORG, "ubiquitin"),
                    },
                    "secondaryInput": {
                        "id": "leaf_go_autophagy",
                        "displayName": "GO: Autophagy",
                        "searchName": "GenesByGoTerm",
                        "parameters": _go_search_params(HS_ORG, "GO:0006914"),
                    },
                },
                "secondaryInput": {
                    "id": "atg_becn_union",
                    "displayName": "ATG + Beclin",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "leaf_atg_core",
                        "displayName": "ATG Gene Family",
                        "searchName": "GenesByText",
                        "parameters": _text_name_search(HS_ORG, "ATG*"),
                    },
                    "secondaryInput": {
                        "id": "leaf_beclin",
                        "displayName": "Beclin Complex",
                        "searchName": "GenesByText",
                        "parameters": _text_name_search(HS_ORG, "BECN*"),
                    },
                },
            },
        },
        control_set=ControlSetDef(
            name="Autophagy Panel (curated)",
            positive_ids=HOSTDB_AUTOPHAGY[:25],
            negative_ids=HOSTDB_COMPLEMENT[:15] + HOSTDB_INTERLEUKINS[:10],
            provenance_notes=(
                "Positives: ATG core genes, beclin, LAMP, ULK1, WIPI, DRAM — "
                "autophagy/xenophagy machinery. "
                "Negatives: complement factors and interleukins — extracellular "
                "immune effectors, not autophagy."
            ),
            tags=["autophagy", "xenophagy", "hostdb", "seed"],
        ),
    ),
    # ===================================================================
    # 5) Hs Malaria Host Response (13 nodes)
    # ===================================================================
    SeedDef(
        name="Hs Malaria Host Response",
        description=(
            "Human host response to Plasmodium infection combining RNA-Seq data "
            "from malaria-infected Gambian children (upregulated genes 2-fold) "
            "INTERSECTED with GO immune/defense response, UNIONED with hemozoin-"
            "stimulated interferon pathway genes. Also includes complement + TLR "
            "genes MINUS those downregulated during malaria. Models the complete "
            "human transcriptomic response to malaria infection."
        ),
        site_id="hostdb",
        step_tree={
            "id": "root_malaria",
            "displayName": "Malaria Host Response",
            "operator": "UNION",
            "primaryInput": {
                "id": "malaria_up_immune",
                "displayName": "Malaria Upregulated Immune",
                "operator": "INTERSECT",
                "primaryInput": {
                    "id": "leaf_malaria_up",
                    "displayName": "Malaria Upregulated (2x)",
                    "searchName": "GenesByRNASeqhsapREF_Lee_Gambian_ebi_rnaSeq_RSRC",
                    "parameters": _rnaseq_fc_params(
                        dataset_url="https://HostDB.org/a/app/record/dataset/DS_8b52ce9c69",
                        profileset="Transcriptome analysis of blood from Gambian children with malaria. -   - Sense",
                        direction="up-regulated",
                        ref_samples=["UM_301", "UM_302", "UM_309", "UM_314", "UM_326"],
                        comp_samples=["CM_149", "CM_207", "CM_497", "CM_503", "CM_88"],
                        fold_change="2",
                        hard_floor="341.56301580548894009348229757942445722",
                    ),
                },
                "secondaryInput": {
                    "id": "immune_defense_union",
                    "displayName": "Immune + Defense Response",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "leaf_go_immune",
                        "displayName": "GO: Immune Response",
                        "searchName": "GenesByGoTerm",
                        "parameters": _go_search_params(HS_ORG, "GO:0006955"),
                    },
                    "secondaryInput": {
                        "id": "leaf_go_defense",
                        "displayName": "GO: Defense Response",
                        "searchName": "GenesByGoTerm",
                        "parameters": _go_search_params(HS_ORG, "GO:0006952"),
                    },
                },
            },
            "secondaryInput": {
                "id": "hemozoin_complement_union",
                "displayName": "Hemozoin + Complement/TLR",
                "operator": "UNION",
                "primaryInput": {
                    "id": "hemozoin_ifn",
                    "displayName": "Hemozoin-IFN Crosstalk",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "leaf_hemozoin_up",
                        "displayName": "Hemozoin Upregulated",
                        "searchName": "GenesByRNASeqhsapREF_hsap_hemazoin_shah_RNASeq_ebi_rnaSeq_RSRC",
                        "parameters": _rnaseq_fc_params(
                            dataset_url="https://HostDB.org/a/app/record/dataset/DS_f1c4acdfd2",
                            profileset="Transcriptome of lung epithelial cells stimulated by hemozoin -   - Sense",
                            direction="up-regulated",
                            ref_samples=["no hemazoin"],
                            comp_samples=["200 ug_ml hemazoin"],
                            fold_change="2",
                            hard_floor="272.147788084374446425317223213838784148",
                        ),
                    },
                    "secondaryInput": {
                        "id": "leaf_ifn_text",
                        "displayName": "Interferon Pathway",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(HS_ORG, "interferon"),
                    },
                },
                "secondaryInput": {
                    "id": "complement_tlr_clean",
                    "displayName": "Complement+TLR Active in Malaria",
                    "operator": "MINUS",
                    "primaryInput": {
                        "id": "complement_tlr_union",
                        "displayName": "Complement + TLR",
                        "operator": "UNION",
                        "primaryInput": {
                            "id": "leaf_complement_mal",
                            "displayName": "Complement System",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(HS_ORG, "complement"),
                        },
                        "secondaryInput": {
                            "id": "leaf_tlr_mal",
                            "displayName": "Toll-like Receptors",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                HS_ORG, "toll-like receptor"
                            ),
                        },
                    },
                    "secondaryInput": {
                        "id": "leaf_malaria_down",
                        "displayName": "Malaria Downregulated",
                        "searchName": "GenesByRNASeqhsapREF_Lee_Gambian_ebi_rnaSeq_RSRC",
                        "parameters": _rnaseq_fc_params(
                            dataset_url="https://HostDB.org/a/app/record/dataset/DS_8b52ce9c69",
                            profileset="Transcriptome analysis of blood from Gambian children with malaria. -   - Sense",
                            direction="down-regulated",
                            ref_samples=[
                                "UM_301",
                                "UM_302",
                                "UM_309",
                                "UM_314",
                                "UM_326",
                            ],
                            comp_samples=[
                                "CM_149",
                                "CM_207",
                                "CM_497",
                                "CM_503",
                                "CM_88",
                            ],
                            fold_change="2",
                            hard_floor="341.56301580548894009348229757942445722",
                        ),
                    },
                },
            },
        },
        control_set=ControlSetDef(
            name="Malaria Host Response Panel (curated)",
            positive_ids=(
                HOSTDB_TLRS[:6]
                + HOSTDB_INTERFERONS[:10]
                + HOSTDB_COMPLEMENT[:10]
                + HOSTDB_INTERLEUKINS[:8]
                + HOSTDB_NFKB[:4]
            ),
            negative_ids=HOSTDB_HSP[:10] + HOSTDB_DEFENSINS[:10],
            provenance_notes=(
                "Positives: TLRs, interferons, complement, interleukins, NF-kB — "
                "genes known to be activated during malaria infection. "
                "Negatives: HSPs and defensins — not specifically malaria-responsive."
            ),
            tags=["malaria", "transcriptomic", "hostdb", "seed"],
        ),
    ),
    # ===================================================================
    # 6) Hs Multi-Pathogen Transcriptomic Response (15 nodes)
    # ===================================================================
    SeedDef(
        name="Hs Multi-Pathogen Transcriptomic Response",
        description=(
            "Cross-pathogen comparison of human transcriptomic responses: "
            "core shared response (T. gondii AND T. cruzi upregulated), "
            "Candida-specific response (MINUS shared protozoan response), "
            "innate immune genes upregulated by any protozoan, NF-kB pathway "
            "in Candida, and apoptosis genes in T. gondii + Candida. "
            "15-node strategy covering 3 major pathogen classes: apicomplexa, "
            "kinetoplastid, and fungal."
        ),
        site_id="hostdb",
        step_tree={
            "id": "root_multi",
            "displayName": "Multi-Pathogen Response",
            "operator": "UNION",
            "primaryInput": {
                "id": "shared_protozoan",
                "displayName": "Shared Protozoan Response",
                "operator": "INTERSECT",
                "primaryInput": {
                    "id": "leaf_tgondii_up",
                    "displayName": "T. gondii Upregulated",
                    "searchName": "GenesByRNASeqhsapREF_hsapREF_RNASeq_Greally_RSRC_ebi_rnaSeq_RSRC",
                    "parameters": _rnaseq_fc_params(
                        dataset_url="https://HostDB.org/a/app/record/dataset/DS_65d43ce7fa",
                        profileset="T gondii infected human host cells vs control -   - Sense",
                        direction="up-regulated",
                        ref_samples=["uninfected"],
                        comp_samples=["Tgondii infected"],
                        fold_change="2",
                        hard_floor="2314.203852657671445273494538137698139906",
                    ),
                },
                "secondaryInput": {
                    "id": "leaf_tcruzi_up",
                    "displayName": "T. cruzi Upregulated (72h)",
                    "searchName": "GenesByRNASeqhsapREF_Li_Transcriptome_Remodeling_ebi_rnaSeq_RSRC",
                    "parameters": _rnaseq_fc_params(
                        dataset_url="https://HostDB.org/a/app/record/dataset/DS_d8246ca26a",
                        profileset="Transcriptome Remodeling during Intracellular Infection -   unstranded",
                        direction="up-regulated",
                        ref_samples=["uninf 72hpi"],
                        comp_samples=["amas 72hpi"],
                        fold_change="2",
                        hard_floor="226.109700380694103271368368225039972615",
                    ),
                },
            },
            "secondaryInput": {
                "id": "candida_innate_union",
                "displayName": "Candida-Specific + Innate Immune",
                "operator": "UNION",
                "primaryInput": {
                    "id": "candida_specific",
                    "displayName": "Candida-Specific Response",
                    "operator": "MINUS",
                    "primaryInput": {
                        "id": "leaf_candida_up",
                        "displayName": "Candida Upregulated (24h)",
                        "searchName": "GenesByRNASeqhsapREF_Bruno_Immune_Response_ebi_rnaSeq_RSRC",
                        "parameters": _rnaseq_fc_params(
                            dataset_url="https://HostDB.org/a/app/record/dataset/DS_410d99350c",
                            profileset="Host immune response against Candida auris -   - Sense",
                            direction="up-regulated",
                            ref_samples=["RPMI_24hr"],
                            comp_samples=["calb_live_24hr"],
                            fold_change="2",
                            hard_floor="3728.599876329304064755953644508884817863",
                        ),
                    },
                    "secondaryInput": {
                        "id": "shared_protozoan_dup",
                        "displayName": "Shared Protozoan (filter)",
                        "operator": "INTERSECT",
                        "primaryInput": {
                            "id": "leaf_tgondii_up2",
                            "displayName": "T. gondii Up (dup)",
                            "searchName": "GenesByRNASeqhsapREF_hsapREF_RNASeq_Greally_RSRC_ebi_rnaSeq_RSRC",
                            "parameters": _rnaseq_fc_params(
                                dataset_url="https://HostDB.org/a/app/record/dataset/DS_65d43ce7fa",
                                profileset="T gondii infected human host cells vs control -   - Sense",
                                direction="up-regulated",
                                ref_samples=["uninfected"],
                                comp_samples=["Tgondii infected"],
                                fold_change="2",
                                hard_floor="2314.203852657671445273494538137698139906",
                            ),
                        },
                        "secondaryInput": {
                            "id": "leaf_tcruzi_up2",
                            "displayName": "T. cruzi Up (dup)",
                            "searchName": "GenesByRNASeqhsapREF_Li_Transcriptome_Remodeling_ebi_rnaSeq_RSRC",
                            "parameters": _rnaseq_fc_params(
                                dataset_url="https://HostDB.org/a/app/record/dataset/DS_d8246ca26a",
                                profileset="Transcriptome Remodeling during Intracellular Infection -   unstranded",
                                direction="up-regulated",
                                ref_samples=["uninf 72hpi"],
                                comp_samples=["amas 72hpi"],
                                fold_change="2",
                                hard_floor="226.109700380694103271368368225039972615",
                            ),
                        },
                    },
                },
                "secondaryInput": {
                    "id": "innate_apoptosis_union",
                    "displayName": "Innate Immune + Apoptosis",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "protozoan_innate",
                        "displayName": "Protozoan-Innate Crosstalk",
                        "operator": "INTERSECT",
                        "primaryInput": {
                            "id": "any_protozoan_up",
                            "displayName": "Any Protozoan Upregulated",
                            "operator": "UNION",
                            "primaryInput": {
                                "id": "leaf_tg_up3",
                                "displayName": "T. gondii Up",
                                "searchName": "GenesByRNASeqhsapREF_hsapREF_RNASeq_Greally_RSRC_ebi_rnaSeq_RSRC",
                                "parameters": _rnaseq_fc_params(
                                    dataset_url="https://HostDB.org/a/app/record/dataset/DS_65d43ce7fa",
                                    profileset="T gondii infected human host cells vs control -   - Sense",
                                    direction="up-regulated",
                                    ref_samples=["uninfected"],
                                    comp_samples=["Tgondii infected"],
                                    fold_change="2",
                                    hard_floor="2314.203852657671445273494538137698139906",
                                ),
                            },
                            "secondaryInput": {
                                "id": "leaf_tc_up3",
                                "displayName": "T. cruzi Up",
                                "searchName": "GenesByRNASeqhsapREF_Li_Transcriptome_Remodeling_ebi_rnaSeq_RSRC",
                                "parameters": _rnaseq_fc_params(
                                    dataset_url="https://HostDB.org/a/app/record/dataset/DS_d8246ca26a",
                                    profileset="Transcriptome Remodeling during Intracellular Infection -   unstranded",
                                    direction="up-regulated",
                                    ref_samples=["uninf 72hpi"],
                                    comp_samples=["amas 72hpi"],
                                    fold_change="2",
                                    hard_floor="226.109700380694103271368368225039972615",
                                ),
                            },
                        },
                        "secondaryInput": {
                            "id": "leaf_go_innate",
                            "displayName": "GO: Innate Immune Response",
                            "searchName": "GenesByGoTerm",
                            "parameters": _go_search_params(HS_ORG, "GO:0045087"),
                        },
                    },
                    "secondaryInput": {
                        "id": "nfkb_apoptosis_union",
                        "displayName": "NF-kB + Apoptosis",
                        "operator": "UNION",
                        "primaryInput": {
                            "id": "candida_nfkb",
                            "displayName": "Candida NF-kB Response",
                            "operator": "INTERSECT",
                            "primaryInput": {
                                "id": "leaf_candida_up2",
                                "displayName": "Candida Upregulated",
                                "searchName": "GenesByRNASeqhsapREF_Bruno_Immune_Response_ebi_rnaSeq_RSRC",
                                "parameters": _rnaseq_fc_params(
                                    dataset_url="https://HostDB.org/a/app/record/dataset/DS_410d99350c",
                                    profileset="Host immune response against Candida auris -   - Sense",
                                    direction="up-regulated",
                                    ref_samples=["RPMI_24hr"],
                                    comp_samples=["calb_live_24hr"],
                                    fold_change="2",
                                    hard_floor="3728.599876329304064755953644508884817863",
                                ),
                            },
                            "secondaryInput": {
                                "id": "leaf_nfkb_text",
                                "displayName": "NF-kB Pathway",
                                "searchName": "GenesByText",
                                "parameters": _text_search_params(HS_ORG, "NF-kappa"),
                            },
                        },
                        "secondaryInput": {
                            "id": "tg_candida_apoptosis",
                            "displayName": "Apoptosis in T.gondii+Candida",
                            "operator": "INTERSECT",
                            "primaryInput": {
                                "id": "tg_candida_union",
                                "displayName": "T.gondii OR Candida Up",
                                "operator": "UNION",
                                "primaryInput": {
                                    "id": "leaf_tg_up4",
                                    "displayName": "T. gondii Up",
                                    "searchName": "GenesByRNASeqhsapREF_hsapREF_RNASeq_Greally_RSRC_ebi_rnaSeq_RSRC",
                                    "parameters": _rnaseq_fc_params(
                                        dataset_url="https://HostDB.org/a/app/record/dataset/DS_65d43ce7fa",
                                        profileset="T gondii infected human host cells vs control -   - Sense",
                                        direction="up-regulated",
                                        ref_samples=["uninfected"],
                                        comp_samples=["Tgondii infected"],
                                        fold_change="2",
                                        hard_floor="2314.203852657671445273494538137698139906",
                                    ),
                                },
                                "secondaryInput": {
                                    "id": "leaf_calb_up3",
                                    "displayName": "Candida Up",
                                    "searchName": "GenesByRNASeqhsapREF_Bruno_Immune_Response_ebi_rnaSeq_RSRC",
                                    "parameters": _rnaseq_fc_params(
                                        dataset_url="https://HostDB.org/a/app/record/dataset/DS_410d99350c",
                                        profileset="Host immune response against Candida auris -   - Sense",
                                        direction="up-regulated",
                                        ref_samples=["RPMI_24hr"],
                                        comp_samples=["calb_live_24hr"],
                                        fold_change="2",
                                        hard_floor="3728.599876329304064755953644508884817863",
                                    ),
                                },
                            },
                            "secondaryInput": {
                                "id": "leaf_go_apoptosis",
                                "displayName": "GO: Apoptotic Process",
                                "searchName": "GenesByGoTerm",
                                "parameters": _go_search_params(HS_ORG, "GO:0006915"),
                            },
                        },
                    },
                },
            },
        },
        control_set=ControlSetDef(
            name="Multi-Pathogen Response Panel (curated)",
            positive_ids=(
                HOSTDB_INTERFERONS[:8]
                + HOSTDB_NFKB[:4]
                + HOSTDB_CASPASES[:6]
                + HOSTDB_TLRS[:6]
                + HOSTDB_JAK_STAT[:6]
                + HOSTDB_SIGNALING_ADAPTORS[:5]
                + HOSTDB_TNF[:8]
                + HOSTDB_INTERLEUKINS[:8]
            ),
            negative_ids=HOSTDB_HSP[:15] + HOSTDB_DEFENSINS[:10],
            provenance_notes=(
                "Positives: interferons, NF-kB, caspases, TLRs, JAK-STAT, "
                "MYD88/IRAK/TRAF, TNF, interleukins — genes activated across "
                "multiple pathogen infections (T. gondii, T. cruzi, Candida). "
                "Negatives: HSPs and defensins — not transcriptomically responsive "
                "to these pathogens."
            ),
            tags=["multi-pathogen", "transcriptomic", "hostdb", "seed"],
        ),
    ),
]
