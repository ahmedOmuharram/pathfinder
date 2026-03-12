"""Seed definitions for GiardiaDB.

Covers Giardia Assemblage A isolate WB with real gene IDs from GiardiaDB,
biologically meaningful search configurations targeting:
  - Antigenic variation (VSPs, HCMPs, cysteine-rich surface proteins)
  - Encystation pathway (cyst wall proteins, encystation-specific genes)
  - Drug targets (PFOR, nitroreductases, metabolic enzymes, kinases)
  - Cytoskeleton & attachment (giardins, tubulins, dynein, kinesins)
  - Kinase signaling (NEK kinases, ~179 members)
  - Secreted virulence factors (cathepsins, proteases)
"""

import json
from typing import Any

from veupath_chatbot.services.experiment.seed.types import ControlSetDef, SeedDef

# ---------------------------------------------------------------------------
# Organism constants
# ---------------------------------------------------------------------------

GL_ORG = "Giardia Assemblage A isolate WB"
GL_EC_SOURCES = [
    "KEGG_Enzyme",
    "GenBank",
    "computationally inferred from Orthology",
    "Uniprot",
]

# ---------------------------------------------------------------------------
# Gene ID lists (all real VEuPathDB IDs, verified Mar 2026)
# ---------------------------------------------------------------------------

# Variant Surface Proteins (VSPs) — massive gene family for antigenic variation
GIARDIA_VSP = [
    "GL50803_101010",
    "GL50803_101074",
    "GL50803_101380",
    "GL50803_101410",
    "GL50803_101496",
    "GL50803_101765",
    "GL50803_102178",
    "GL50803_102230",
    "GL50803_102540",
    "GL50803_102662",
    "GL50803_103001",
    "GL50803_103142",
    "GL50803_103916",
    "GL50803_103992",
    "GL50803_104087",
    "GL50803_10562",
    "GL50803_105759",
    "GL50803_105983",
    "GL50803_111732",
    "GL50803_111873",
    "GL50803_111874",
    "GL50803_111903",
    "GL50803_111933",
    "GL50803_111936",
    "GL50803_112009",
    "GL50803_112048",
    "GL50803_112113",
    "GL50803_112135",
    "GL50803_112178",
    "GL50803_112207",
    "GL50803_112208",
    "GL50803_112305",
    "GL50803_112314",
    "GL50803_112331",
    "GL50803_112584",
    "GL50803_112647",
    "GL50803_112673",
    "GL50803_112678",
    "GL50803_112693",
    "GL50803_112801",
    "GL50803_112867",
    "GL50803_113024",
    "GL50803_113093",
    "GL50803_113163",
    "GL50803_113211",
    "GL50803_113242",
    "GL50803_113269",
    "GL50803_113297",
    "GL50803_113304",
    "GL50803_113357",
    "GL50803_113439",
    "GL50803_113450",
    "GL50803_113491",
    "GL50803_113797",
    "GL50803_113801",
    "GL50803_113954",
    "GL50803_114065",
    "GL50803_114121",
    "GL50803_114122",
    "GL50803_114162",
    "GL50803_114277",
    "GL50803_114286",
    "GL50803_114653",
    "GL50803_114654",
    "GL50803_114672",
    "GL50803_11470",
    "GL50803_114813",
    "GL50803_114852",
    "GL50803_115047",
    "GL50803_115066",
    "GL50803_115085",
    "GL50803_115202",
    "GL50803_11521",
    "GL50803_115474",
    "GL50803_115475",
    "GL50803_115742",
    "GL50803_115796",
    "GL50803_115797",
    "GL50803_115830",
    "GL50803_115831",
    "GL50803_116477",
    "GL50803_11692",
    "GL50803_117203",
    "GL50803_117204",
    "GL50803_117472",
    "GL50803_117473",
    "GL50803_118132",
    "GL50803_118133",
    "GL50803_118180",
    "GL50803_118181",
    "GL50803_118786",
    "GL50803_118900",
    "GL50803_119706",
    "GL50803_119707",
    "GL50803_121069",
    "GL50803_121070",
    "GL50803_122564",
    "GL50803_122565",
    "GL50803_122566",
    "GL50803_124980",
    "GL50803_12993",
    "GL50803_13194",
    "GL50803_13390",
    "GL50803_13402",
    "GL50803_134710",
    "GL50803_134711",
    "GL50803_13520",
    "GL50803_135831",
    "GL50803_135832",
    "GL50803_135881",
    "GL50803_135882",
    "GL50803_135918",
    "GL50803_135919",
    "GL50803_136001",
    "GL50803_136002",
    "GL50803_136003",
    "GL50803_136004",
    "GL50803_13727",
    "GL50803_137604",
    "GL50803_137605",
    "GL50803_137606",
    "GL50803_137607",
    "GL50803_137608",
    "GL50803_137610",
    "GL50803_137611",
    "GL50803_137612",
    "GL50803_137613",
    "GL50803_137614",
    "GL50803_137617",
    "GL50803_137618",
    "GL50803_137620",
    "GL50803_137672",
    "GL50803_137681",
    "GL50803_137691",
    "GL50803_137697",
    "GL50803_137707",
    "GL50803_137708",
    "GL50803_137710",
    "GL50803_137714",
    "GL50803_137717",
    "GL50803_137721",
    "GL50803_137722",
    "GL50803_137723",
    "GL50803_137729",
    "GL50803_137740",
    "GL50803_137744",
    "GL50803_137752",
    "GL50803_137761",
    "GL50803_14043",
    "GL50803_14297",
    "GL50803_14307",
    "GL50803_14331",
    "GL50803_14586",
    "GL50803_15123",
    "GL50803_15206",
    "GL50803_15237",
    "GL50803_15400",
    "GL50803_16158",
    "GL50803_16472",
    "GL50803_16501",
    "GL50803_25892",
    "GL50803_26590",
    "GL50803_26894",
    "GL50803_28626",
    "GL50803_29744",
    "GL50803_32890",
    "GL50803_32916",
    "GL50803_32933",
    "GL50803_33279",
    "GL50803_33783",
    "GL50803_34196",
    "GL50803_34357",
    "GL50803_34442",
    "GL50803_35454",
    "GL50803_36493",
    "GL50803_37093",
    "GL50803_38901",
    "GL50803_38910",
    "GL50803_40571",
    "GL50803_40591",
    "GL50803_40592",
    "GL50803_40621",
    "GL50803_40630",
    "GL50803_41227",
    "GL50803_41349",
    "GL50803_41401",
    "GL50803_41472",
    "GL50803_41476",
    "GL50803_41539",
    "GL50803_41626",
    "GL50803_4313",
    "GL50803_5812",
    "GL50803_7748",
    "GL50803_8338",
    "GL50803_8595",
    "GL50803_87628",
    "GL50803_89315",
    "GL50803_90215",
    "GL50803_92835",
    "GL50803_96055",
]

# High Cysteine Membrane Proteins (HCMPs) — cysteine-rich surface family
GIARDIA_HCMP = [
    "GL50803_101589",
    "GL50803_101805",
    "GL50803_101832",
    "GL50803_102180",
    "GL50803_103454",
    "GL50803_103943",
    "GL50803_10659",
    "GL50803_111877",
    "GL50803_112126",
    "GL50803_112135",
    "GL50803_112305",
    "GL50803_112432",
    "GL50803_112584",
    "GL50803_112604",
    "GL50803_112633",
    "GL50803_112673",
    "GL50803_112828",
    "GL50803_11309",
    "GL50803_113213",
    "GL50803_113297",
    "GL50803_113319",
    "GL50803_113416",
    "GL50803_113512",
    "GL50803_113531",
    "GL50803_113801",
    "GL50803_113836",
    "GL50803_113987",
    "GL50803_114042",
    "GL50803_114089",
    "GL50803_114161",
    "GL50803_114180",
    "GL50803_114470",
    "GL50803_114617",
    "GL50803_114626",
    "GL50803_114852",
    "GL50803_114888",
    "GL50803_114891",
    "GL50803_114930",
    "GL50803_114991",
    "GL50803_115066",
    "GL50803_115158",
    "GL50803_137672",
    "GL50803_137715",
    "GL50803_137727",
    "GL50803_137732",
    "GL50803_14017",
    "GL50803_14324",
    "GL50803_14783",
    "GL50803_14791",
    "GL50803_15008",
    "GL50803_15250",
    "GL50803_15317",
    "GL50803_15475",
    "GL50803_15521",
    "GL50803_16318",
    "GL50803_16374",
    "GL50803_16716",
    "GL50803_16721",
    "GL50803_16842",
    "GL50803_16936",
    "GL50803_17212",
    "GL50803_17328",
    "GL50803_17380",
    "GL50803_21321",
    "GL50803_22547",
    "GL50803_24880",
    "GL50803_25013",
    "GL50803_25238",
    "GL50803_25816",
    "GL50803_27717",
    "GL50803_28057",
    "GL50803_32607",
    "GL50803_32701",
    "GL50803_34777",
    "GL50803_35985",
    "GL50803_39904",
    "GL50803_40376",
    "GL50803_41942",
    "GL50803_6372",
    "GL50803_7715",
    "GL50803_87706",
    "GL50803_9003",
    "GL50803_91099",
    "GL50803_91707",
    "GL50803_94003",
    "GL50803_9620",
    "GL50803_98126",
]

# Cyst wall proteins and encystation-specific genes
GIARDIA_CYST_WALL = [
    "GL50803_5638",  # Cyst wall protein 1 (CWP1)
    "GL50803_5435",  # Cyst wall protein 2 (CWP2)
    "GL50803_2421",  # Cyst wall protein 3 (CWP3)
    "GL50803_40376",  # High cysteine non-variant cyst protein
]

GIARDIA_ENCYSTATION = [
    "GL50803_22553",  # Encystation-specific protease
    "GL50803_7243",  # Encystation-specific secretory granule protein-1
]

# Giardins — ventral disc structural proteins (unique to Giardia)
GIARDIA_GIARDINS = [
    "GL50803_11654",  # Alpha-1 giardin
    "GL50803_7796",  # Alpha-2 giardin
    "GL50803_11683",  # Alpha-3 giardin
    "GL50803_7799",  # Alpha-4 giardin
    "GL50803_7797",  # Alpha-5 giardin
    "GL50803_14551",  # Alpha-6 giardin
    "GL50803_103373",  # Alpha-7.1 giardin
    "GL50803_114119",  # Alpha-7.2 giardin
    "GL50803_114787",  # Alpha-7.3 giardin
    "GL50803_11649",  # Alpha-8 giardin
    "GL50803_103437",  # Alpha-9 giardin
    "GL50803_5649",  # Alpha-10 giardin
    "GL50803_17153",  # Alpha-11 giardin
    "GL50803_10073",  # Alpha-12 giardin
    "GL50803_1076",  # Alpha-13 giardin
    "GL50803_15097",  # Alpha-14 giardin
    "GL50803_13996",  # Alpha-15 giardin
    "GL50803_10036",  # Alpha-16 giardin
    "GL50803_15101",  # Alpha-17 giardin
    "GL50803_10038",  # Alpha-18 giardin
    "GL50803_4026",  # Alpha-19 giardin
    "GL50803_4812",  # Beta-giardin
    "GL50803_17230",  # Gamma giardin
    "GL50803_86676",  # Delta giardin
]

# Tubulin genes — cytoskeletal structural proteins
GIARDIA_TUBULIN = [
    "GL50803_103676",  # Alpha-tubulin
    "GL50803_112079",  # Alpha-tubulin
    "GL50803_101291",  # Beta tubulin
    "GL50803_136020",  # Beta tubulin
    "GL50803_136021",  # Beta tubulin
    "GL50803_114218",  # Gamma tubulin
    "GL50803_5462",  # Delta tubulin
    "GL50803_6336",  # Epsilon tubulin
    "GL50803_12057",  # Gamma tubulin ring complex
    "GL50803_17429",  # Small gamma tubulin complex gcp2
    "GL50803_10145",  # Tubulin specific chaperone D
    "GL50803_15906",  # Tubulin specific chaperone D
    "GL50803_16535",  # Tubulin specific chaperone E
    "GL50803_5374",  # Tubulin specific chaperone B
    "GL50803_10382",  # Tubulin tyrosine ligase
    "GL50803_10801",  # Tubulin tyrosine ligase
    "GL50803_14498",  # Tubulin tyrosine ligase
    "GL50803_8456",  # Tubulin tyrosine ligase
    "GL50803_8592",  # Tubulin tyrosine ligase
    "GL50803_9272",  # Tubulin tyrosine ligase
    "GL50803_95661",  # Tubulin tyrosine ligase
]

# Dynein motor proteins — flagellar motility
GIARDIA_DYNEIN = [
    "GL50803_100906",
    "GL50803_101138",
    "GL50803_10254",
    "GL50803_103059",
    "GL50803_10538",
    "GL50803_10613",
    "GL50803_111950",
    "GL50803_13273",
    "GL50803_13575",
    "GL50803_14270",
    "GL50803_15124",
    "GL50803_15460",
    "GL50803_15549",
    "GL50803_15606",
    "GL50803_16540",
    "GL50803_16804",
    "GL50803_17243",
    "GL50803_17265",
    "GL50803_17371",
    "GL50803_17478",
    "GL50803_27308",
    "GL50803_29256",
    "GL50803_33218",
    "GL50803_37985",
    "GL50803_40496",
    "GL50803_42285",
    "GL50803_4236",
    "GL50803_4463",
    "GL50803_6939",
    "GL50803_7578",
    "GL50803_8172",
    "GL50803_93736",
    "GL50803_94440",
    "GL50803_9481",
    "GL50803_9848",
]

# Kinesin motor proteins
GIARDIA_KINESIN = [
    "GL50803_11177",  # Kinesin-like protein
    "GL50803_112729",  # Kinesin like protein
    "GL50803_11442",  # Kinesin-related protein
    "GL50803_114885",  # Kinesin-associated protein
    "GL50803_14070",  # Kinesin-like protein
    "GL50803_16224",  # Kinesin-related protein
    "GL50803_17264",  # Kinesin like protein
]

# Intraflagellar transport
GIARDIA_IFT = [
    "GL50803_16660",  # IFT88
    "GL50803_9750",  # IFT74/72
]

# Median body and basal body proteins (cytoskeletal organelles)
GIARDIA_CYTOSKELETAL_ORGANELLE = [
    "GL50803_16343",  # Median body protein
    "GL50803_8146",  # Basal body protein
    "GL50803_8508",  # Basal body protein
]

# Actin and actin-related
GIARDIA_ACTIN = [
    "GL50803_15113",  # Actin
    "GL50803_11039",  # Actin related protein
    "GL50803_16172",  # Actin related protein
    "GL50803_40817",  # Actin related protein
    "GL50803_8726",  # Actin related protein
]

# GASP-180 axoneme-associated proteins
GIARDIA_AXONEME = [
    "GL50803_13475",  # Axoneme-associated protein GASP-180
    "GL50803_137716",  # Axoneme-associated protein GASP-180
    "GL50803_16745",  # Axoneme-associated protein GASP-180
    "GL50803_23235",  # Axoneme-associated protein GASP-180
    "GL50803_41512",  # Flagella associated protein
]

# NEK kinases — massively expanded family in Giardia (~179 members)
GIARDIA_NEK_KINASES = [
    "GL50803_101307",
    "GL50803_101534",
    "GL50803_101866",
    "GL50803_102034",
    "GL50803_102542",
    "GL50803_103944",
    "GL50803_10744",
    "GL50803_10893",
    "GL50803_11040",
    "GL50803_111938",
    "GL50803_112518",
    "GL50803_112553",
    "GL50803_113030",
    "GL50803_113094",
    "GL50803_11311",
    "GL50803_11355",
    "GL50803_113553",
    "GL50803_11390",
    "GL50803_114120",
    "GL50803_114192",
    "GL50803_114307",
    "GL50803_114495",
    "GL50803_114535",
    "GL50803_114937",
    "GL50803_11554",
    "GL50803_11775",
    "GL50803_119989",
    "GL50803_12095",
    "GL50803_12148",
    "GL50803_12152",
    "GL50803_12240",
    "GL50803_13215",
    "GL50803_13479",
    "GL50803_137676",
    "GL50803_137696",
    "GL50803_137701",
    "GL50803_137706",
    "GL50803_137719",
    "GL50803_137728",
    "GL50803_137733",
    "GL50803_137735",
    "GL50803_137737",
    "GL50803_137742",
    "GL50803_137743",
    "GL50803_13921",
    "GL50803_13963",
    "GL50803_13964",
    "GL50803_13981",
    "GL50803_14044",
    "GL50803_14216",
    "GL50803_14223",
    "GL50803_14648",
    "GL50803_14742",
    "GL50803_14786",
    "GL50803_14835",
    "GL50803_14897",
    "GL50803_14916",
    "GL50803_14934",
    "GL50803_15035",
    "GL50803_15049",
    "GL50803_15064",
    "GL50803_15338",
    "GL50803_15409",
    "GL50803_15411",
    "GL50803_15479",
    "GL50803_15953",
    "GL50803_16049",
    "GL50803_16122",
    "GL50803_16167",
    "GL50803_16205",
    "GL50803_16251",
    "GL50803_16272",
    "GL50803_16279",
    "GL50803_16460",
    "GL50803_16479",
    "GL50803_16508",
    "GL50803_16733",
    "GL50803_16765",
    "GL50803_16792",
    "GL50803_16824",
    "GL50803_16826",
    "GL50803_16839",
    "GL50803_16862",
    "GL50803_16879",
    "GL50803_16889",
    "GL50803_16943",
    "GL50803_16952",
    "GL50803_16967",
    "GL50803_16988",
    "GL50803_17069",
    "GL50803_17084",
    "GL50803_17188",
    "GL50803_17216",
    "GL50803_17231",
    "GL50803_17299",
    "GL50803_17318",
    "GL50803_17510",
    "GL50803_17560",
    "GL50803_17578",
    "GL50803_17622",
]

# Proteases — cathepsins, cysteine proteases, serine proteases
GIARDIA_PROTEASES = [
    "GL50803_10843",  # Thymus-specific serine protease precursor
    "GL50803_112831",  # Cysteine protease
    "GL50803_113656",  # Cysteine protease
    "GL50803_114773",  # Cysteine protease
    "GL50803_114915",  # Cysteine protease
    "GL50803_137680",  # Cathepsin L-like protease
    "GL50803_13896",  # Cgi67 serine protease precursor-like
    "GL50803_16438",  # Sentrin specific protease
    "GL50803_16817",  # Transglutaminase/protease
    "GL50803_17106",  # 26S protease regulatory subunit 8
    "GL50803_21331",  # 26S protease regulatory subunit 7
    "GL50803_22553",  # Encystation-specific protease
    "GL50803_2556",  # ATP-dependent Clp protease ClpB
    "GL50803_2897",  # Furin precursor serine protease
    "GL50803_3099",  # Cathepsin L-like protease
    "GL50803_4365",  # 26S protease regulatory subunit 6A
    "GL50803_7950",  # 26S protease regulatory subunit 6B
    "GL50803_86683",  # 26S protease regulatory subunit 7
]

# Cathepsin proteases specifically (virulence/pathogenesis)
GIARDIA_CATHEPSINS = [
    "GL50803_10217",  # Cathepsin B precursor
    "GL50803_11209",  # Cathepsin L precursor
    "GL50803_114165",  # Cathepsin B-like cysteine proteinase 3
    "GL50803_137680",  # Cathepsin L-like protease
    "GL50803_14019",  # Cathepsin B precursor
    "GL50803_14983",  # Cathepsin L precursor
    "GL50803_15564",  # Cathepsin B precursor
    "GL50803_16160",  # Cathepsin B precursor
    "GL50803_16380",  # Cathepsin L precursor
    "GL50803_16468",  # Cathepsin B precursor
    "GL50803_3099",  # Cathepsin L-like protease
]

# Drug target enzymes — PFOR, nitroreductases, ferredoxins, metabolic
GIARDIA_DRUG_TARGETS = [
    "GL50803_114609",  # Pyruvate-flavodoxin oxidoreductase (PFOR-1)
    "GL50803_17063",  # Pyruvate-flavodoxin oxidoreductase (PFOR-2)
    "GL50803_15307",  # Nitroreductase family protein
    "GL50803_22677",  # Nitroreductase Fd-NR2
    "GL50803_6175",  # Nitroreductase Fd-NR1 (fused to ferredoxin)
    "GL50803_10329",  # Ferredoxin Fd3
    "GL50803_27266",  # [2Fe-2S] ferredoxin
    "GL50803_9662",  # Ferredoxin Fd1, Fd2
    "GL50803_9827",  # Thioredoxin reductase
    "GL50803_10358",  # A-type flavoprotein (lateral transfer)
]

# Metabolic enzymes — glycolysis, arginine dihydrolase pathway
GIARDIA_METABOLIC = [
    "GL50803_11118",  # Enolase
    "GL50803_17043",  # Glyceraldehyde 3-phosphate dehydrogenase
    "GL50803_6687",  # Glyceraldehyde 3-phosphate dehydrogenase
    "GL50803_11043",  # Fructose-bisphosphate aldolase
    "GL50803_14993",  # Pyrophosphate-fructose 6-phosphate 1-phosphotransferase
    "GL50803_8826",  # Glucokinase
    "GL50803_3206",  # Pyruvate kinase
    "GL50803_17143",  # Pyruvate kinase
    "GL50803_112103",  # Arginine deiminase (ADI pathway)
    "GL50803_16453",  # Carbamate kinase (ADI pathway)
    "GL50803_13608",  # Acetyl-CoA synthetase
    "GL50803_3287",  # Acetyl-CoA acetyltransferase
    "GL50803_13962",  # Hydroxymethylglutaryl-CoA synthase
    "GL50803_7573",  # HMG-CoA reductase
    "GL50803_3331",  # Malate dehydrogenase
    "GL50803_21942",  # NADP-specific glutamate dehydrogenase
    "GL50803_16125",  # Glycerol-3-phosphate dehydrogenase
    "GL50803_14759",  # 6-phosphogluconate dehydrogenase
    "GL50803_13350",  # Alcohol dehydrogenase (lateral transfer)
    "GL50803_3593",  # Alcohol dehydrogenase (lateral transfer)
    "GL50803_3861",  # Alcohol dehydrogenase 3 (lateral transfer)
    "GL50803_9909",  # Pyruvate phosphate dikinase
    "GL50803_9368",  # Pyruvate-formate lyase-activating enzyme
]

# Transporters — ABC transporters, amino acid/hexose transporters
GIARDIA_TRANSPORTERS = [
    "GL50803_102051",
    "GL50803_11299",
    "GL50803_113876",
    "GL50803_11540",
    "GL50803_12820",
    "GL50803_13204",
    "GL50803_137726",
    "GL50803_14168",
    "GL50803_16283",
    "GL50803_16575",
    "GL50803_16592",
    "GL50803_16605",
    "GL50803_17132",
    "GL50803_17165",
    "GL50803_17214",
    "GL50803_17315",
    "GL50803_21327",
    "GL50803_21411",
    "GL50803_221689",
    "GL50803_3470",
    "GL50803_42048",
    "GL50803_6000",
    "GL50803_6427",
    "GL50803_6664",
    "GL50803_7909",
    "GL50803_8523",
    "GL50803_87446",
    "GL50803_9133",
    "GL50803_91712",
    "GL50803_92223",
    "GL50803_95904",
    "GL50803_9741",
]

# Heat shock proteins — stress response
GIARDIA_HEAT_SHOCK = [
    "GL50803_13864",  # HSP90-alpha
    "GL50803_16412",  # Heat-shock protein putative
    "GL50803_17432",  # HSP70
    "GL50803_9594",  # HSP70 binding protein
    "GL50803_98054",  # HSP90-alpha
]

# Ribosomal proteins (housekeeping — used as negative controls)
GIARDIA_RIBOSOMAL = [
    "GL50803_10091",
    "GL50803_10367",
    "GL50803_10428",
    "GL50803_10780",
    "GL50803_10919",
    "GL50803_11247",
    "GL50803_11287",
    "GL50803_11359",
    "GL50803_11950",
    "GL50803_12981",
    "GL50803_13412",
    "GL50803_1345",
    "GL50803_14049",
    "GL50803_14091",
    "GL50803_14171",
    "GL50803_14321",
    "GL50803_14329",
    "GL50803_14620",
    "GL50803_14622",
    "GL50803_14699",
    "GL50803_14827",
    "GL50803_14869",
    "GL50803_14938",
    "GL50803_15046",
    "GL50803_15228",
    "GL50803_15260",
    "GL50803_15520",
    "GL50803_15551",
    "GL50803_16086",
    "GL50803_16114",
    "GL50803_16265",
    "GL50803_16310",
    "GL50803_16368",
    "GL50803_16387",
    "GL50803_16431",
    "GL50803_16525",
    "GL50803_16652",
    "GL50803_17054",
    "GL50803_17056",
    "GL50803_17244",
    "GL50803_17337",
    "GL50803_17364",
    "GL50803_17395",
    "GL50803_17547",
    "GL50803_19003",
    "GL50803_19436",
    "GL50803_2825",
    "GL50803_33862",
    "GL50803_3570",
    "GL50803_36069",
    "GL50803_39483",
    "GL50803_4547",
    "GL50803_4652",
    "GL50803_5517",
    "GL50803_5593",
    "GL50803_5665",
    "GL50803_5845",
    "GL50803_5947",
    "GL50803_6022",
    "GL50803_6133",
    "GL50803_6135",
    "GL50803_7082",
    "GL50803_7766",
    "GL50803_7870",
    "GL50803_7878",
    "GL50803_7999",
    "GL50803_8001",
    "GL50803_8118",
    "GL50803_8462",
    "GL50803_98056",
    "GL50803_9810",
]

# Histone genes (chromatin/nuclear — negative controls for surface strategies)
GIARDIA_HISTONES = [
    "GL50803_10666",  # Histone acetyltransferase GCN5
    "GL50803_10707",  # NAD-dependent histone deacetylase Sir2
    "GL50803_121045",  # Histone H2B
    "GL50803_121046",  # Histone H2B
    "GL50803_135001",  # Histone H4
    "GL50803_135002",  # Histone H4
    "GL50803_135003",  # Histone H4
    "GL50803_135231",  # Histone H3
    "GL50803_14212",  # Histone H3
    "GL50803_14256",  # Histone H2A
]

# Tenascin-like proteins (extracellular matrix)
GIARDIA_TENASCIN = [
    "GL50803_10330",  # Tenascin precursor
    "GL50803_114815",  # Tenascin precursor
    "GL50803_14047",  # Tenascin-X
    "GL50803_14360",  # Tenascin-X
    "GL50803_14573",  # Tenascin-X
    "GL50803_16833",  # Tenascin-like
    "GL50803_8687",  # Tenascin precursor
    "GL50803_94510",  # Tenascin-X precursor
    "GL50803_95162",  # Tenascin
]

# Multidrug resistance ABC transporters (drug resistance)
GIARDIA_MDR = [
    "GL50803_17315",  # MDR ABC transporter
    "GL50803_17132",  # MRP-like ABC transporter
    "GL50803_115052",  # Multidrug resistance-associated protein 1
    "GL50803_28379",  # Multidrug resistance-associated protein 1
    "GL50803_28906",  # Multidrug resistance-associated protein Mrp2
    "GL50803_41118",  # Multidrug resistance-associated protein 1
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
        "go_term": "N/A",
    }


def _ec_kinase_params(organism: str, ec_sources: list[str]) -> dict[str, str]:
    return {
        "organism": _org([organism]),
        "ec_source": json.dumps(ec_sources),
        "ec_number_pattern": "2.7.11.1",
        "ec_wildcard": "N/A",
    }


def _text_search_params(
    organism: str,
    text: str,
    *,
    whole_words: str = "yes",
) -> dict[str, str]:
    return {
        "text_expression": text,
        "text_fields": json.dumps(["product"]),
        "text_search_organism": json.dumps([organism]),
        "document_type": "gene",
        "whole_words": whole_words,
    }


def _tm_domain_params(
    organism: str,
    min_tm: str = "1",
    max_tm: str = "99",
) -> dict[str, str]:
    return {
        "organism": _org([organism]),
        "min_tm": min_tm,
        "max_tm": max_tm,
    }


def _signal_peptide_params(organism: str) -> dict[str, str]:
    return {"organism": _org([organism])}


def _paralog_count_params(
    organism: str,
    min_p: str = "5",
    max_p: str = "500",
) -> dict[str, str]:
    return {
        "organism": _org([organism]),
        "num_paralogs": json.dumps({"min": min_p, "max": max_p}),
    }


def _mol_weight_params(
    organism: str,
    min_w: str = "10000",
    max_w: str = "50000",
) -> dict[str, str]:
    return {
        "organism": _org([organism]),
        "min_molecular_weight": min_w,
        "max_molecular_weight": max_w,
    }


def _gene_type_params(
    organism: str,
    gene_type: str = "protein coding",
) -> dict[str, str]:
    return {
        "organism": _org([organism]),
        "geneType": json.dumps([gene_type]),
        "includePseudogenes": "No",
    }


# ---------------------------------------------------------------------------
# Strategy 1: GlWB Antigenic Variation (12 nodes)
# VSPs + HCMPs + surface features — the immune evasion repertoire
# ---------------------------------------------------------------------------

_s1_vsp_text: dict[str, Any] = {
    "id": "s1_vsp_text",
    "displayName": "VSP genes (text)",
    "searchName": "GenesByText",
    "parameters": _text_search_params(GL_ORG, "VSP"),
}

_s1_hcmp_text: dict[str, Any] = {
    "id": "s1_hcmp_text",
    "displayName": "High cysteine membrane proteins (text)",
    "searchName": "GenesByText",
    "parameters": _text_search_params(GL_ORG, "high cysteine", whole_words="no"),
}

_s1_surface_union: dict[str, Any] = {
    "id": "s1_surface_union",
    "displayName": "VSP U HCMP",
    "operator": "UNION",
    "primaryInput": _s1_vsp_text,
    "secondaryInput": _s1_hcmp_text,
}

_s1_tm_domains: dict[str, Any] = {
    "id": "s1_tm_domains",
    "displayName": ">=3 TM domains",
    "searchName": "GenesByTransmembraneDomains",
    "parameters": _tm_domain_params(GL_ORG, "3", "99"),
}

_s1_surface_with_tm: dict[str, Any] = {
    "id": "s1_surface_tm",
    "displayName": "(VSP U HCMP) intersect TM domains",
    "operator": "INTERSECT",
    "primaryInput": _s1_surface_union,
    "secondaryInput": _s1_tm_domains,
}

_s1_paralogs: dict[str, Any] = {
    "id": "s1_paralogs",
    "displayName": "Expanded families (>=50 paralogs)",
    "searchName": "GenesByParalogCount",
    "parameters": _paralog_count_params(GL_ORG, "50", "500"),
}

_s1_membrane_go: dict[str, Any] = {
    "id": "s1_membrane_go",
    "displayName": "GO: membrane",
    "searchName": "GenesByGoTerm",
    "parameters": _go_search_params(GL_ORG, "GO:0016020"),
}

_s1_paralog_membrane: dict[str, Any] = {
    "id": "s1_paralog_membrane",
    "displayName": "Expanded families intersect membrane",
    "operator": "INTERSECT",
    "primaryInput": _s1_paralogs,
    "secondaryInput": _s1_membrane_go,
}

_s1_broad_union: dict[str, Any] = {
    "id": "s1_broad_union",
    "displayName": "Surface proteins U expanded membrane",
    "operator": "UNION",
    "primaryInput": _s1_surface_with_tm,
    "secondaryInput": _s1_paralog_membrane,
}

_s1_ribosomal: dict[str, Any] = {
    "id": "s1_ribosomal",
    "displayName": "Ribosomal (GO:0003735)",
    "searchName": "GenesByGoTerm",
    "parameters": _go_search_params(GL_ORG, "GO:0003735"),
}

_s1_kinase_exclude: dict[str, Any] = {
    "id": "s1_kinase_exclude",
    "displayName": "Kinase activity (GO:0004672)",
    "searchName": "GenesByGoTerm",
    "parameters": _go_search_params(GL_ORG, "GO:0004672"),
}

_s1_housekeeping_union: dict[str, Any] = {
    "id": "s1_housekeeping",
    "displayName": "Ribosomal U Kinases",
    "operator": "UNION",
    "primaryInput": _s1_ribosomal,
    "secondaryInput": _s1_kinase_exclude,
}

STRAT1_ANTIGENIC_VARIATION: dict[str, Any] = {
    "id": "s1_root",
    "displayName": "Antigenic variation surface repertoire",
    "operator": "MINUS",
    "primaryInput": _s1_broad_union,
    "secondaryInput": _s1_housekeeping_union,
}

# ---------------------------------------------------------------------------
# Strategy 2: GlWB Encystation Pathway (10 nodes)
# ---------------------------------------------------------------------------

_s2_cyst_text: dict[str, Any] = {
    "id": "s2_cyst_text",
    "displayName": "Cyst wall genes (text)",
    "searchName": "GenesByText",
    "parameters": _text_search_params(GL_ORG, "cyst wall", whole_words="no"),
}

_s2_encystation_text: dict[str, Any] = {
    "id": "s2_encystation_text",
    "displayName": "Encystation genes (text)",
    "searchName": "GenesByText",
    "parameters": _text_search_params(GL_ORG, "encystation", whole_words="no"),
}

_s2_cyst_encystation: dict[str, Any] = {
    "id": "s2_cyst_enc_union",
    "displayName": "Cyst wall U Encystation",
    "operator": "UNION",
    "primaryInput": _s2_cyst_text,
    "secondaryInput": _s2_encystation_text,
}

_s2_signal: dict[str, Any] = {
    "id": "s2_signal",
    "displayName": "Signal peptide",
    "searchName": "GenesWithSignalPeptide",
    "parameters": _signal_peptide_params(GL_ORG),
}

_s2_protease_go: dict[str, Any] = {
    "id": "s2_protease_go",
    "displayName": "GO: proteolysis",
    "searchName": "GenesByGoTerm",
    "parameters": _go_search_params(GL_ORG, "GO:0006508"),
}

_s2_secreted_proteases: dict[str, Any] = {
    "id": "s2_secreted_proteases",
    "displayName": "Secreted proteases",
    "operator": "INTERSECT",
    "primaryInput": _s2_signal,
    "secondaryInput": _s2_protease_go,
}

_s2_diff_genes: dict[str, Any] = {
    "id": "s2_diff_genes",
    "displayName": "Differentiation genes",
    "operator": "UNION",
    "primaryInput": _s2_cyst_encystation,
    "secondaryInput": _s2_secreted_proteases,
}

_s2_protein_coding: dict[str, Any] = {
    "id": "s2_protein_coding",
    "displayName": "Protein coding genes",
    "searchName": "GenesByGeneType",
    "parameters": _gene_type_params(GL_ORG),
}

_s2_filtered: dict[str, Any] = {
    "id": "s2_filtered",
    "displayName": "Encystation genes (verified)",
    "operator": "INTERSECT",
    "primaryInput": _s2_diff_genes,
    "secondaryInput": _s2_protein_coding,
}

_s2_cytoskeleton: dict[str, Any] = {
    "id": "s2_cytoskeleton",
    "displayName": "GO: cytoskeleton",
    "searchName": "GenesByGoTerm",
    "parameters": _go_search_params(GL_ORG, "GO:0005856"),
}

STRAT2_ENCYSTATION: dict[str, Any] = {
    "id": "s2_root",
    "displayName": "Encystation pathway genes",
    "operator": "MINUS",
    "primaryInput": _s2_filtered,
    "secondaryInput": _s2_cytoskeleton,
}

# ---------------------------------------------------------------------------
# Strategy 3: GlWB Drug Targets (10 nodes)
# ---------------------------------------------------------------------------

_s3_oxidoreductase: dict[str, Any] = {
    "id": "s3_oxidoreductase",
    "displayName": "GO: oxidoreductase activity",
    "searchName": "GenesByGoTerm",
    "parameters": _go_search_params(GL_ORG, "GO:0016491"),
}

_s3_ec_kinases: dict[str, Any] = {
    "id": "s3_ec_kinases",
    "displayName": "EC kinases (2.7.11.1)",
    "searchName": "GenesByEcNumber",
    "parameters": _ec_kinase_params(GL_ORG, GL_EC_SOURCES),
}

_s3_enzymes_union: dict[str, Any] = {
    "id": "s3_enzymes_union",
    "displayName": "Oxidoreductases U Kinases",
    "operator": "UNION",
    "primaryInput": _s3_oxidoreductase,
    "secondaryInput": _s3_ec_kinases,
}

_s3_mol_weight: dict[str, Any] = {
    "id": "s3_mol_weight",
    "displayName": "MW 20-200 kDa",
    "searchName": "GenesByMolecularWeight",
    "parameters": _mol_weight_params(GL_ORG, "20000", "200000"),
}

_s3_sized_enzymes: dict[str, Any] = {
    "id": "s3_sized_enzymes",
    "displayName": "Enzymes in size range",
    "operator": "INTERSECT",
    "primaryInput": _s3_enzymes_union,
    "secondaryInput": _s3_mol_weight,
}

_s3_nitro_text: dict[str, Any] = {
    "id": "s3_nitro_text",
    "displayName": "Nitroreductases (text)",
    "searchName": "GenesByText",
    "parameters": _text_search_params(GL_ORG, "nitroreductase", whole_words="no"),
}

_s3_pyruvate_text: dict[str, Any] = {
    "id": "s3_pyruvate_text",
    "displayName": "Pyruvate enzymes (text)",
    "searchName": "GenesByText",
    "parameters": _text_search_params(GL_ORG, "pyruvate", whole_words="no"),
}

_s3_specific_targets: dict[str, Any] = {
    "id": "s3_specific_union",
    "displayName": "Nitroreductases U PFOR/pyruvate",
    "operator": "UNION",
    "primaryInput": _s3_nitro_text,
    "secondaryInput": _s3_pyruvate_text,
}

_s3_all_targets: dict[str, Any] = {
    "id": "s3_all_targets",
    "displayName": "All candidate drug targets",
    "operator": "UNION",
    "primaryInput": _s3_sized_enzymes,
    "secondaryInput": _s3_specific_targets,
}

_s3_ribosomal: dict[str, Any] = {
    "id": "s3_ribosomal",
    "displayName": "Ribosomal (GO:0003735)",
    "searchName": "GenesByGoTerm",
    "parameters": _go_search_params(GL_ORG, "GO:0003735"),
}

STRAT3_DRUG_TARGETS: dict[str, Any] = {
    "id": "s3_root",
    "displayName": "Drug target candidates",
    "operator": "MINUS",
    "primaryInput": _s3_all_targets,
    "secondaryInput": _s3_ribosomal,
}

# ---------------------------------------------------------------------------
# Strategy 4: GlWB Cytoskeleton & Attachment (10 nodes)
# ---------------------------------------------------------------------------

_s4_giardin: dict[str, Any] = {
    "id": "s4_giardin",
    "displayName": "Giardins (text)",
    "searchName": "GenesByText",
    "parameters": _text_search_params(GL_ORG, "giardin", whole_words="no"),
}

_s4_tubulin: dict[str, Any] = {
    "id": "s4_tubulin",
    "displayName": "Tubulins (text)",
    "searchName": "GenesByText",
    "parameters": _text_search_params(GL_ORG, "tubulin", whole_words="no"),
}

_s4_disc_proteins: dict[str, Any] = {
    "id": "s4_disc_union",
    "displayName": "Giardins U Tubulins",
    "operator": "UNION",
    "primaryInput": _s4_giardin,
    "secondaryInput": _s4_tubulin,
}

_s4_microtubule_go: dict[str, Any] = {
    "id": "s4_microtubule",
    "displayName": "GO: microtubule-based process",
    "searchName": "GenesByGoTerm",
    "parameters": _go_search_params(GL_ORG, "GO:0007018"),
}

_s4_cilium_go: dict[str, Any] = {
    "id": "s4_cilium",
    "displayName": "GO: cilium",
    "searchName": "GenesByGoTerm",
    "parameters": _go_search_params(GL_ORG, "GO:0005929"),
}

_s4_flagellar: dict[str, Any] = {
    "id": "s4_flagellar",
    "displayName": "Microtubule intersect Cilium",
    "operator": "INTERSECT",
    "primaryInput": _s4_microtubule_go,
    "secondaryInput": _s4_cilium_go,
}

_s4_all_cyto: dict[str, Any] = {
    "id": "s4_all_cyto",
    "displayName": "Disc + Flagellar proteins",
    "operator": "UNION",
    "primaryInput": _s4_disc_proteins,
    "secondaryInput": _s4_flagellar,
}

_s4_mol_weight: dict[str, Any] = {
    "id": "s4_mol_weight",
    "displayName": "MW >= 10 kDa",
    "searchName": "GenesByMolecularWeight",
    "parameters": _mol_weight_params(GL_ORG, "10000", "1000000"),
}

_s4_sized: dict[str, Any] = {
    "id": "s4_sized",
    "displayName": "Cytoskeletal (sized)",
    "operator": "INTERSECT",
    "primaryInput": _s4_all_cyto,
    "secondaryInput": _s4_mol_weight,
}

_s4_nuclear: dict[str, Any] = {
    "id": "s4_nuclear",
    "displayName": "GO: nucleus",
    "searchName": "GenesByGoTerm",
    "parameters": _go_search_params(GL_ORG, "GO:0005634"),
}

STRAT4_CYTOSKELETON: dict[str, Any] = {
    "id": "s4_root",
    "displayName": "Cytoskeleton and attachment",
    "operator": "MINUS",
    "primaryInput": _s4_sized,
    "secondaryInput": _s4_nuclear,
}

# ---------------------------------------------------------------------------
# Strategy 5: GlWB Kinase Signaling Network (8 nodes)
# ---------------------------------------------------------------------------

_s5_ec_kinases: dict[str, Any] = {
    "id": "s5_ec_kinases",
    "displayName": "EC kinases (2.7.11.1)",
    "searchName": "GenesByEcNumber",
    "parameters": _ec_kinase_params(GL_ORG, GL_EC_SOURCES),
}

_s5_go_kinase: dict[str, Any] = {
    "id": "s5_go_kinase",
    "displayName": "GO: kinase activity",
    "searchName": "GenesByGoTerm",
    "parameters": _go_search_params(GL_ORG, "GO:0004672"),
}

_s5_go_atp: dict[str, Any] = {
    "id": "s5_go_atp",
    "displayName": "GO: ATP binding",
    "searchName": "GenesByGoTerm",
    "parameters": _go_search_params(GL_ORG, "GO:0005524"),
}

_s5_go_kinase_atp: dict[str, Any] = {
    "id": "s5_kinase_atp",
    "displayName": "GO kinase intersect ATP binding",
    "operator": "INTERSECT",
    "primaryInput": _s5_go_kinase,
    "secondaryInput": _s5_go_atp,
}

_s5_all_kinases: dict[str, Any] = {
    "id": "s5_all_kinases",
    "displayName": "EC U GO kinases",
    "operator": "UNION",
    "primaryInput": _s5_ec_kinases,
    "secondaryInput": _s5_go_kinase_atp,
}

_s5_protein_coding: dict[str, Any] = {
    "id": "s5_protein_coding",
    "displayName": "Protein coding",
    "searchName": "GenesByGeneType",
    "parameters": _gene_type_params(GL_ORG),
}

_s5_verified_kinases: dict[str, Any] = {
    "id": "s5_verified",
    "displayName": "Verified kinases",
    "operator": "INTERSECT",
    "primaryInput": _s5_all_kinases,
    "secondaryInput": _s5_protein_coding,
}

_s5_translation: dict[str, Any] = {
    "id": "s5_translation",
    "displayName": "GO: translation",
    "searchName": "GenesByGoTerm",
    "parameters": _go_search_params(GL_ORG, "GO:0006412"),
}

STRAT5_KINASE_SIGNALING: dict[str, Any] = {
    "id": "s5_root",
    "displayName": "Kinase signaling network",
    "operator": "MINUS",
    "primaryInput": _s5_verified_kinases,
    "secondaryInput": _s5_translation,
}

# ---------------------------------------------------------------------------
# Strategy 6: GlWB Secreted Virulence Factors (8 nodes)
# ---------------------------------------------------------------------------

_s6_signal: dict[str, Any] = {
    "id": "s6_signal",
    "displayName": "Signal peptide",
    "searchName": "GenesWithSignalPeptide",
    "parameters": _signal_peptide_params(GL_ORG),
}

_s6_protease_go: dict[str, Any] = {
    "id": "s6_protease",
    "displayName": "GO: proteolysis",
    "searchName": "GenesByGoTerm",
    "parameters": _go_search_params(GL_ORG, "GO:0006508"),
}

_s6_hydrolase_go: dict[str, Any] = {
    "id": "s6_hydrolase",
    "displayName": "GO: hydrolase",
    "searchName": "GenesByGoTerm",
    "parameters": _go_search_params(GL_ORG, "GO:0016787"),
}

_s6_enzyme_union: dict[str, Any] = {
    "id": "s6_enzyme_union",
    "displayName": "Proteases U Hydrolases",
    "operator": "UNION",
    "primaryInput": _s6_protease_go,
    "secondaryInput": _s6_hydrolase_go,
}

_s6_secreted_enzymes: dict[str, Any] = {
    "id": "s6_secreted_enzymes",
    "displayName": "Secreted enzymes",
    "operator": "INTERSECT",
    "primaryInput": _s6_signal,
    "secondaryInput": _s6_enzyme_union,
}

_s6_cathepsin_text: dict[str, Any] = {
    "id": "s6_cathepsin",
    "displayName": "Cathepsins (text)",
    "searchName": "GenesByText",
    "parameters": _text_search_params(GL_ORG, "cathepsin", whole_words="no"),
}

_s6_all_virulence: dict[str, Any] = {
    "id": "s6_all_virulence",
    "displayName": "Secreted virulence factors",
    "operator": "UNION",
    "primaryInput": _s6_secreted_enzymes,
    "secondaryInput": _s6_cathepsin_text,
}

_s6_ribosomal: dict[str, Any] = {
    "id": "s6_ribosomal",
    "displayName": "Ribosomal (GO:0003735)",
    "searchName": "GenesByGoTerm",
    "parameters": _go_search_params(GL_ORG, "GO:0003735"),
}

STRAT6_VIRULENCE: dict[str, Any] = {
    "id": "s6_root",
    "displayName": "Secreted virulence factors",
    "operator": "MINUS",
    "primaryInput": _s6_all_virulence,
    "secondaryInput": _s6_ribosomal,
}

# ---------------------------------------------------------------------------
# Seed definitions
# ---------------------------------------------------------------------------

SEEDS: list[SeedDef] = [
    # 1) Antigenic Variation — VSPs, HCMPs, surface repertoire (12 nodes)
    SeedDef(
        name="GlWB Antigenic Variation Surface Repertoire",
        description=(
            "Giardia's immune evasion strategy: variant surface proteins (VSPs) "
            "and high-cysteine membrane proteins (HCMPs) that are surface-exposed, "
            "belong to expanded paralog families, and exclude housekeeping genes. "
            "12-node strategy combining text search, TM domains, paralog count, "
            "GO membrane, minus ribosomal and kinase genes."
        ),
        site_id="giardiadb",
        step_tree=STRAT1_ANTIGENIC_VARIATION,
        control_set=ControlSetDef(
            name="G. lamblia Antigenic Variation (curated)",
            positive_ids=GIARDIA_VSP[:50] + GIARDIA_HCMP[:30],
            negative_ids=GIARDIA_RIBOSOMAL[:40] + GIARDIA_HISTONES,
            provenance_notes=(
                "Positives: variant surface proteins (VSPs) and high-cysteine "
                "membrane proteins (HCMPs) — the immune evasion surface repertoire. "
                "Negatives: ribosomal structural proteins and histone genes — "
                "housekeeping/nuclear genes with no surface role."
            ),
            tags=["antigenic-variation", "giardia", "seed"],
        ),
    ),
    # 2) Encystation Pathway (10 nodes)
    SeedDef(
        name="GlWB Encystation Differentiation Pathway",
        description=(
            "Genes involved in trophozoite-to-cyst differentiation: cyst wall "
            "proteins (CWP1-3), encystation-specific proteases and secretory "
            "granule proteins, and secreted proteases. Verified as protein coding "
            "and excluding cytoskeletal genes."
        ),
        site_id="giardiadb",
        step_tree=STRAT2_ENCYSTATION,
        control_set=ControlSetDef(
            name="G. lamblia Encystation (curated)",
            positive_ids=(
                GIARDIA_CYST_WALL + GIARDIA_ENCYSTATION + GIARDIA_PROTEASES[:8]
            ),
            negative_ids=GIARDIA_GIARDINS[:12] + GIARDIA_TUBULIN[:8],
            provenance_notes=(
                "Positives: cyst wall proteins (CWP1-3), encystation-specific "
                "genes, and differentiation proteases. "
                "Negatives: giardins and tubulins — cytoskeletal structural "
                "proteins excluded from encystation pathway."
            ),
            tags=["encystation", "giardia", "seed"],
        ),
    ),
    # 3) Drug Targets — PFOR, nitroreductases, metabolic enzymes (10 nodes)
    SeedDef(
        name="GlWB Drug Target Candidates",
        description=(
            "Potential drug targets in Giardia: pyruvate-flavodoxin oxidoreductases "
            "(PFOR — metronidazole activation), nitroreductases, and metabolic "
            "enzymes from the anaerobic energy metabolism. Combined with EC "
            "kinases (NEK family) as potential kinase inhibitor targets. "
            "Size-filtered and excluding ribosomal housekeeping."
        ),
        site_id="giardiadb",
        step_tree=STRAT3_DRUG_TARGETS,
        control_set=ControlSetDef(
            name="G. lamblia Drug Targets (curated)",
            positive_ids=(
                GIARDIA_DRUG_TARGETS + GIARDIA_METABOLIC[:10] + GIARDIA_NEK_KINASES[:30]
            ),
            negative_ids=GIARDIA_RIBOSOMAL[:40],
            provenance_notes=(
                "Positives: PFOR, nitroreductases, ferredoxins, metabolic "
                "enzymes, and NEK kinases — druggable targets. "
                "Negatives: ribosomal structural proteins — stable housekeeping."
            ),
            tags=["drug-target", "giardia", "seed"],
        ),
    ),
    # 4) Cytoskeleton & Attachment — disc, flagella, motors (10 nodes)
    SeedDef(
        name="GlWB Cytoskeleton and Attachment Apparatus",
        description=(
            "Giardia's unique cytoskeletal structures: ventral disc (giardins), "
            "flagellar apparatus (4 pairs), tubulins (alpha, beta, gamma, delta, "
            "epsilon), dynein and kinesin motors. GO-filtered for microtubule "
            "processes and cilium, size-filtered, excluding nuclear proteins."
        ),
        site_id="giardiadb",
        step_tree=STRAT4_CYTOSKELETON,
        control_set=ControlSetDef(
            name="G. lamblia Cytoskeleton (curated)",
            positive_ids=(
                GIARDIA_GIARDINS
                + GIARDIA_TUBULIN[:10]
                + GIARDIA_DYNEIN[:15]
                + GIARDIA_KINESIN
                + GIARDIA_CYTOSKELETAL_ORGANELLE
                + GIARDIA_ACTIN
                + GIARDIA_AXONEME
            ),
            negative_ids=GIARDIA_RIBOSOMAL[:30] + GIARDIA_HISTONES,
            provenance_notes=(
                "Positives: giardins, tubulins, dyneins, kinesins, actin, "
                "axoneme proteins — cytoskeletal and motility apparatus. "
                "Negatives: ribosomal and histone genes — nuclear/housekeeping."
            ),
            tags=["cytoskeleton", "giardia", "seed"],
        ),
    ),
    # 5) Kinase Signaling Network (8 nodes)
    SeedDef(
        name="GlWB Kinase Signaling Network",
        description=(
            "Giardia's expanded kinase repertoire, dominated by NEK kinases "
            "(~179 members). Combines EC 2.7.11.1 with GO kinase activity "
            "intersected with ATP binding for high confidence. The NEK expansion "
            "is linked to encystation, flagellar regulation, and cell cycle control."
        ),
        site_id="giardiadb",
        step_tree=STRAT5_KINASE_SIGNALING,
        control_set=ControlSetDef(
            name="G. lamblia NEK Kinases (curated)",
            positive_ids=GIARDIA_NEK_KINASES[:60],
            negative_ids=GIARDIA_RIBOSOMAL[:30] + GIARDIA_VSP[:20],
            provenance_notes=(
                "Positives: NEK family kinases — massively expanded in Giardia "
                "for encystation and flagellar control. "
                "Negatives: ribosomal proteins and VSPs — non-kinase genes."
            ),
            tags=["kinase", "giardia", "seed"],
        ),
    ),
    # 6) Secreted Virulence Factors (8 nodes)
    SeedDef(
        name="GlWB Secreted Virulence Factors",
        description=(
            "Secreted and surface proteins contributing to Giardia pathogenesis: "
            "cathepsin proteases (B and L), secreted hydrolases, and signal "
            "peptide-bearing enzymes. These damage host intestinal epithelium "
            "and modulate host immune response."
        ),
        site_id="giardiadb",
        step_tree=STRAT6_VIRULENCE,
        control_set=ControlSetDef(
            name="G. lamblia Virulence Factors (curated)",
            positive_ids=(
                GIARDIA_CATHEPSINS + GIARDIA_PROTEASES[:8] + GIARDIA_TENASCIN[:5]
            ),
            negative_ids=GIARDIA_RIBOSOMAL[:20] + GIARDIA_HISTONES,
            provenance_notes=(
                "Positives: cathepsin proteases, secreted proteases, and "
                "tenascin-like proteins — secreted virulence factors. "
                "Negatives: ribosomal and histone genes — non-secreted housekeeping."
            ),
            tags=["virulence", "giardia", "seed"],
        ),
    ),
]
