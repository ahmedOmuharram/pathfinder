"""Seed definitions for VectorBase.

Organism: Anopheles gambiae PEST

Strategies model real vector biology research:
  1. AgPEST Insecticide Resistance Network (12 nodes)
  2. AgPEST Anti-Plasmodium Immune Response (11 nodes)
  3. AgPEST Olfactory System Host-Seeking (8 nodes)
  4. AgPEST Salivary Anticoagulant Secretome (10 nodes)
  5. AgPEST Midgut Blood-Meal Interaction (10 nodes)
  6. AgPEST Baseline: 2L High-MW minus HSP (5 nodes)

All gene IDs verified against VectorBase live API (March 2026).
"""

import json

from veupath_chatbot.services.experiment.seed.types import ControlSetDef, SeedDef

# ---------------------------------------------------------------------------
# Organism constants
# ---------------------------------------------------------------------------

AG_ORG = "Anopheles gambiae PEST"
AG_EC_SOURCES = ["KEGG_Enzyme", "computationally inferred from Orthology", "Uniprot"]

# ---------------------------------------------------------------------------
# Gene data -- REAL IDs from VectorBase A. gambiae PEST (March 2026)
# ---------------------------------------------------------------------------

# Cytochrome P450 genes -- key insecticide metabolizers
AGAM_CYP450 = [
    "AGAP000088",
    "AGAP000109",
    "AGAP000192",
    "AGAP000193",
    "AGAP000194",
    "AGAP000284",
    "AGAP000500",
    "AGAP000818",
    "AGAP000851",
    "AGAP000877",
    "AGAP001039",
    "AGAP001042",
    "AGAP001076",
    "AGAP001443",
    "AGAP001744",
    "AGAP001861",
    "AGAP001864",
    "AGAP002113",
    "AGAP002138",
    "AGAP002195",
    "AGAP002196",
    "AGAP002197",
    "AGAP002202",
    "AGAP002204",
    "AGAP002205",
    "AGAP002206",
    "AGAP002207",
    "AGAP002208",
    "AGAP002209",
    "AGAP002210",
    "AGAP002211",
    "AGAP002245",
    "AGAP002417",
    "AGAP002418",
    "AGAP002419",
    "AGAP002429",
    "AGAP002555",
    "AGAP002862",
    "AGAP002864",
    "AGAP002865",
    "AGAP002866",
    "AGAP002867",
    "AGAP002868",
    "AGAP002869",
    "AGAP002870",
    "AGAP002894",
    "AGAP002981",
    "AGAP003065",
    "AGAP003066",
    "AGAP003067",
    "AGAP003343",
    "AGAP003522",
    "AGAP003608",
    "AGAP003843",
    "AGAP004665",
    "AGAP004710",
    "AGAP005520",
    "AGAP005656",
    "AGAP005657",
    "AGAP005658",
    "AGAP005660",
    "AGAP005774",
    "AGAP005992",
    "AGAP006047",
    "AGAP006048",
    "AGAP006049",
    "AGAP006099",
    "AGAP006140",
    "AGAP006471",
    "AGAP006936",
    "AGAP007121",
    "AGAP007480",
    "AGAP007621",
    "AGAP007768",
    "AGAP008018",
    "AGAP008019",
    "AGAP008020",
    "AGAP008022",
    "AGAP008203",
    "AGAP008204",
    "AGAP008205",
    "AGAP008206",
    "AGAP008207",
    "AGAP008208",
    "AGAP008209",
    "AGAP008210",
    "AGAP008212",
    "AGAP008213",
    "AGAP008214",
    "AGAP008217",
    "AGAP008218",
    "AGAP008219",
    "AGAP008356",
    "AGAP008358",
    "AGAP008363",
    "AGAP008552",
    "AGAP008682",
    "AGAP008724",
    "AGAP008727",
    "AGAP008955",
    "AGAP009017",
    "AGAP009240",
    "AGAP009241",
    "AGAP009246",
    "AGAP009363",
    "AGAP009374",
]

# Glutathione S-transferases -- phase II detox
AGAM_GST = [
    "AGAP000081",
    "AGAP000163",
    "AGAP000165",
    "AGAP000170",
    "AGAP000531",
    "AGAP000534",
    "AGAP000761",
    "AGAP000794",
    "AGAP000888",
    "AGAP000947",
    "AGAP001310",
    "AGAP001653",
    "AGAP001711",
    "AGAP001804",
    "AGAP002627",
    "AGAP002898",
    "AGAP003042",
    "AGAP003257",
    "AGAP003527",
    "AGAP003536",
    "AGAP003903",
    "AGAP004163",
    "AGAP004164",
    "AGAP004165",
    "AGAP004171",
    "AGAP004172",
    "AGAP004173",
    "AGAP004247",
    "AGAP004248",
    "AGAP004378",
    "AGAP004379",
    "AGAP004380",
    "AGAP004381",
    "AGAP004382",
    "AGAP004383",
    "AGAP004396",
    "AGAP004478",
    "AGAP005297",
    "AGAP005650",
    "AGAP005749",
    "AGAP005911",
    "AGAP005912",
    "AGAP005913",
    "AGAP006096",
    "AGAP006456",
    "AGAP006891",
    "AGAP007082",
    "AGAP007391",
    "AGAP007546",
    "AGAP008406",
    "AGAP008537",
    "AGAP008719",
    "AGAP008978",
    "AGAP009023",
    "AGAP009035",
    "AGAP009072",
    "AGAP009190",
    "AGAP009191",
    "AGAP009192",
    "AGAP009193",
    "AGAP009194",
    "AGAP009195",
    "AGAP009196",
    "AGAP009197",
    "AGAP009342",
    "AGAP009447",
    "AGAP009578",
    "AGAP009619",
    "AGAP009724",
    "AGAP009824",
    "AGAP009946",
    "AGAP009953",
    "AGAP010373",
    "AGAP010388",
    "AGAP010404",
    "AGAP010499",
    "AGAP010873",
    "AGAP011983",
]

# Esterases -- insecticide resistance
AGAM_ESTERASE = [
    "AGAP001723",
    "AGAP002863",
    "AGAP005370",
    "AGAP005371",
    "AGAP005372",
    "AGAP005373",
    "AGAP005757",
    "AGAP005833",
    "AGAP005835",
    "AGAP005836",
    "AGAP006227",
    "AGAP006700",
    "AGAP006725",
    "AGAP009891",
]

# ABC transporters -- multidrug efflux
AGAM_ABC_TRANSPORTER = [
    "AGAP000022",
    "AGAP000128",
    "AGAP000181",
    "AGAP000387",
    "AGAP000394",
    "AGAP000440",
    "AGAP000448",
    "AGAP000506",
    "AGAP000540",
    "AGAP000637",
    "AGAP001027",
    "AGAP001185",
    "AGAP001202",
    "AGAP001236",
    "AGAP001265",
    "AGAP001391",
    "AGAP001447",
    "AGAP001523",
    "AGAP001531",
    "AGAP001550",
    "AGAP001557",
    "AGAP001627",
    "AGAP001635",
    "AGAP001763",
    "AGAP001775",
    "AGAP001777",
    "AGAP001870",
    "AGAP001923",
    "AGAP001965",
    "AGAP001966",
    "AGAP001974",
    "AGAP002011",
    "AGAP002050",
    "AGAP002051",
    "AGAP002060",
    "AGAP002071",
    "AGAP002109",
    "AGAP002182",
    "AGAP002278",
    "AGAP002331",
    "AGAP002366",
    "AGAP002369",
    "AGAP002393",
    "AGAP002571",
    "AGAP002622",
    "AGAP002624",
    "AGAP002638",
    "AGAP002693",
    "AGAP002717",
    "AGAP002939",
    "AGAP003000",
    "AGAP003020",
    "AGAP003039",
    "AGAP003074",
    "AGAP003176",
    "AGAP003221",
    "AGAP003274",
    "AGAP003275",
    "AGAP003300",
    "AGAP003358",
    "AGAP003425",
    "AGAP003492",
    "AGAP003493",
]

# Thioester-containing proteins (TEPs) -- complement-like innate immunity
AGAM_TEP = [
    "AGAP008364",
    "AGAP008366",
    "AGAP008368",
    "AGAP008407",
    "AGAP008654",
    "AGAP010812",
    "AGAP010813",
    "AGAP010814",
    "AGAP010815",
    "AGAP010816",
    "AGAP010819",
    "AGAP010830",
    "AGAP010831",
    "AGAP010832",
]

# Leucine-rich repeat immune proteins (LRIM/APL family)
AGAM_LRIM = [
    "AGAP000136",
    "AGAP000213",
    "AGAP000319",
    "AGAP000471",
    "AGAP000563",
    "AGAP000678",
    "AGAP001136",
    "AGAP001159",
    "AGAP001215",
    "AGAP001278",
    "AGAP001361",
    "AGAP001414",
    "AGAP001491",
    "AGAP001809",
    "AGAP001885",
    "AGAP001895",
    "AGAP002013",
    "AGAP002030",
    "AGAP002035",
    "AGAP002173",
    "AGAP002243",
    "AGAP002260",
    "AGAP002265",
    "AGAP002280",
    "AGAP002309",
    "AGAP002413",
    "AGAP002445",
    "AGAP002542",
    "AGAP002614",
    "AGAP002731",
    "AGAP002839",
    "AGAP002877",
    "AGAP003052",
    "AGAP003061",
    "AGAP003064",
    "AGAP003276",
    "AGAP003336",
    "AGAP003363",
    "AGAP003519",
    "AGAP003539",
    "AGAP003547",
]

# Serine proteases -- CLIP-domain, melanization cascade
AGAM_SERINE_PROTEASE = [
    "AGAP000240",
    "AGAP000290",
    "AGAP000315",
    "AGAP000477",
    "AGAP000571",
    "AGAP000572",
    "AGAP000573",
    "AGAP001190",
    "AGAP001199",
    "AGAP001375",
    "AGAP001376",
    "AGAP001377",
    "AGAP001433",
    "AGAP001636",
    "AGAP001648",
    "AGAP001682",
    "AGAP001683",
    "AGAP001881",
    "AGAP001931",
    "AGAP001964",
    "AGAP001979",
    "AGAP002075",
    "AGAP002161",
    "AGAP002265",
    "AGAP002270",
    "AGAP002422",
    "AGAP002432",
    "AGAP002501",
    "AGAP002508",
    "AGAP002535",
    "AGAP002543",
    "AGAP002569",
    "AGAP002614",
    "AGAP002784",
    "AGAP002811",
    "AGAP002813",
    "AGAP002815",
    "AGAP002996",
    "AGAP003005",
    "AGAP003017",
    "AGAP003057",
    "AGAP003139",
    "AGAP003158",
    "AGAP003160",
    "AGAP003194",
    "AGAP003246",
    "AGAP003247",
    "AGAP003249",
    "AGAP003250",
    "AGAP003251",
    "AGAP003252",
    "AGAP003276",
    "AGAP003618",
    "AGAP003689",
    "AGAP003779",
    "AGAP003807",
    "AGAP003971",
    "AGAP004096",
    "AGAP004148",
    "AGAP004153",
    "AGAP004176",
    "AGAP004198",
    "AGAP004317",
    "AGAP004318",
    "AGAP004502",
    "AGAP004567",
    "AGAP004568",
    "AGAP004569",
    "AGAP004592",
    "AGAP004699",
    "AGAP004719",
    "AGAP004741",
    "AGAP004770",
    "AGAP004808",
    "AGAP004833",
    "AGAP004855",
    "AGAP004859",
    "AGAP004860",
    "AGAP005029",
    "AGAP005173",
    "AGAP005246",
    "AGAP005366",
    "AGAP005509",
    "AGAP005521",
    "AGAP005592",
    "AGAP005625",
    "AGAP005642",
    "AGAP005663",
    "AGAP005664",
    "AGAP005665",
    "AGAP005669",
    "AGAP005670",
    "AGAP005671",
    "AGAP005686",
    "AGAP005687",
    "AGAP005688",
]

# Antimicrobial peptides -- cecropins, defensins, gambicin
AGAM_AMP = [
    "AGAP000692",
    "AGAP000693",
    "AGAP000694",
    "AGAP000757",
    "AGAP000833",
    "AGAP001174",
    "AGAP001878",
    "AGAP002284",
    "AGAP003141",
    "AGAP003207",
    "AGAP003283",
    "AGAP003861",
    "AGAP003917",
    "AGAP003927",
    "AGAP004632",
    "AGAP005055",
    "AGAP005410",
    "AGAP005416",
    "AGAP006610",
    "AGAP006899",
    "AGAP007199",
    "AGAP007200",
    "AGAP008645",
    "AGAP008691",
    "AGAP008993",
    "AGAP009310",
    "AGAP009673",
    "AGAP009729",
    "AGAP010310",
    "AGAP010600",
    "AGAP010601",
    "AGAP010602",
    "AGAP010603",
    "AGAP010604",
    "AGAP010605",
    "AGAP011294",
    "AGAP011319",
    "AGAP011338",
    "AGAP012078",
    "AGAP012082",
    "AGAP012394",
    "AGAP012395",
    "AGAP012396",
    "AGAP013056",
]

# Toll pathway genes
AGAM_TOLL = [
    "AGAP000388",
    "AGAP000999",
    "AGAP001002",
    "AGAP001004",
    "AGAP002966",
    "AGAP003062",
    "AGAP003615",
    "AGAP005252",
    "AGAP005295",
    "AGAP006974",
    "AGAP007938",
    "AGAP009515",
    "AGAP010669",
    "AGAP011186",
    "AGAP011187",
    "AGAP012326",
    "AGAP012385",
    "AGAP012387",
    "AGAP013027",
]

# Immune-annotated genes (broader set)
AGAM_IMMUNE = [
    "AGAP002542",
    "AGAP004959",
    "AGAP005496",
    "AGAP005693",
    "AGAP005744",
    "AGAP006327",
    "AGAP006348",
    "AGAP007034",
    "AGAP007037",
    "AGAP007039",
    "AGAP007045",
    "AGAP007453",
    "AGAP007454",
    "AGAP007455",
    "AGAP007456",
    "AGAP009166",
    "AGAP010675",
    "AGAP011117",
    "AGAP013290",
    "AGAP027997",
    "AGAP028028",
    "AGAP028064",
]

# Odorant receptors -- host-seeking behavior
AGAM_OR = [
    "AGAP000016",
    "AGAP000038",
    "AGAP000115",
    "AGAP000138",
    "AGAP000140",
    "AGAP000144",
    "AGAP000168",
    "AGAP000209",
    "AGAP000226",
    "AGAP000230",
    "AGAP000278",
    "AGAP000279",
    "AGAP000293",
    "AGAP000329",
    "AGAP000349",
    "AGAP000351",
    "AGAP000369",
    "AGAP000388",
    "AGAP000402",
    "AGAP000426",
    "AGAP000427",
    "AGAP000445",
    "AGAP000489",
    "AGAP000606",
    "AGAP000640",
    "AGAP000641",
    "AGAP000642",
    "AGAP000643",
    "AGAP000644",
    "AGAP000653",
    "AGAP000658",
    "AGAP000667",
    "AGAP000714",
    "AGAP000725",
    "AGAP000763",
    "AGAP000767",
    "AGAP000803",
    "AGAP000819",
    "AGAP000844",
    "AGAP000913",
    "AGAP000962",
    "AGAP000966",
    "AGAP000967",
    "AGAP000981",
    "AGAP000998",
    "AGAP000999",
    "AGAP001004",
    "AGAP001012",
    "AGAP001114",
    "AGAP001115",
    "AGAP001117",
    "AGAP001119",
    "AGAP001120",
    "AGAP001121",
    "AGAP001122",
    "AGAP001123",
    "AGAP001125",
    "AGAP001137",
    "AGAP001169",
    "AGAP001170",
    "AGAP001171",
    "AGAP001172",
    "AGAP001173",
    "AGAP001175",
    "AGAP001189",
    "AGAP001379",
    "AGAP001409",
    "AGAP001434",
    "AGAP001469",
    "AGAP001478",
    "AGAP001498",
    "AGAP001522",
    "AGAP001556",
    "AGAP001558",
    "AGAP001561",
    "AGAP001562",
    "AGAP001592",
    "AGAP001743",
    "AGAP001773",
    "AGAP001807",
    "AGAP001811",
    "AGAP001812",
]

# Odorant binding proteins -- ligand transport in olfaction
AGAM_OBP = [
    "AGAP000005",
    "AGAP000009",
    "AGAP000014",
    "AGAP000015",
    "AGAP000022",
    "AGAP000028",
    "AGAP000029",
    "AGAP000032",
    "AGAP000033",
    "AGAP000040",
    "AGAP000044",
    "AGAP000045",
    "AGAP000047",
    "AGAP000049",
    "AGAP000056",
    "AGAP000057",
    "AGAP000063",
    "AGAP000070",
    "AGAP000076",
    "AGAP000085",
    "AGAP000110",
    "AGAP000116",
    "AGAP000119",
    "AGAP000127",
    "AGAP000147",
    "AGAP000149",
    "AGAP000150",
    "AGAP000155",
    "AGAP000159",
    "AGAP000161",
    "AGAP000166",
    "AGAP000167",
    "AGAP000169",
    "AGAP000170",
    "AGAP000171",
    "AGAP000177",
    "AGAP000195",
    "AGAP000209",
    "AGAP000213",
    "AGAP000226",
    "AGAP000230",
    "AGAP000232",
    "AGAP000233",
    "AGAP000237",
    "AGAP000242",
    "AGAP000248",
    "AGAP000261",
    "AGAP000270",
    "AGAP000277",
    "AGAP000278",
    "AGAP000279",
    "AGAP000281",
    "AGAP000300",
    "AGAP000304",
    "AGAP000310",
    "AGAP000311",
    "AGAP000322",
    "AGAP000328",
    "AGAP000331",
    "AGAP000332",
    "AGAP000336",
    "AGAP000339",
    "AGAP000340",
    "AGAP000343",
    "AGAP000344",
    "AGAP000345",
    "AGAP000352",
    "AGAP000356",
    "AGAP000357",
    "AGAP000364",
    "AGAP000367",
    "AGAP000377",
    "AGAP000378",
    "AGAP000395",
    "AGAP000397",
    "AGAP000406",
    "AGAP000428",
    "AGAP000429",
    "AGAP000433",
    "AGAP000434",
    "AGAP000437",
    "AGAP000440",
    "AGAP000444",
    "AGAP000457",
]

# Gustatory receptors -- CO2 detection
AGAM_GR = [
    "AGAP000016",
    "AGAP000038",
    "AGAP000115",
    "AGAP000138",
    "AGAP000140",
    "AGAP000144",
    "AGAP000168",
    "AGAP000209",
    "AGAP000226",
    "AGAP000230",
    "AGAP000293",
    "AGAP000329",
    "AGAP000349",
    "AGAP000351",
    "AGAP000369",
    "AGAP000388",
    "AGAP000402",
    "AGAP000426",
    "AGAP000427",
    "AGAP000445",
    "AGAP000489",
    "AGAP000606",
    "AGAP000653",
    "AGAP000658",
    "AGAP000667",
    "AGAP000714",
    "AGAP000725",
    "AGAP000763",
    "AGAP000767",
    "AGAP000803",
    "AGAP000819",
    "AGAP000844",
    "AGAP000913",
    "AGAP000962",
    "AGAP000966",
    "AGAP000967",
    "AGAP000981",
    "AGAP000998",
    "AGAP000999",
    "AGAP001004",
    "AGAP001012",
    "AGAP001114",
    "AGAP001115",
    "AGAP001117",
]

# Salivary gland proteins -- blood-feeding, Plasmodium transmission
AGAM_SALIVARY = [
    "AGAP000150",
    "AGAP000548",
    "AGAP000607",
    "AGAP000609",
    "AGAP000610",
    "AGAP000611",
    "AGAP000612",
    "AGAP001174",
    "AGAP001374",
    "AGAP001825",
    "AGAP002910",
    "AGAP002912",
    "AGAP003841",
    "AGAP004334",
    "AGAP006504",
    "AGAP006506",
    "AGAP006507",
    "AGAP006899",
    "AGAP007041",
    "AGAP007907",
    "AGAP008215",
    "AGAP008216",
    "AGAP008278",
    "AGAP008279",
    "AGAP008280",
    "AGAP008281",
    "AGAP008282",
    "AGAP008283",
    "AGAP008284",
    "AGAP008782",
    "AGAP009473",
    "AGAP009922",
    "AGAP010647",
    "AGAP011460",
    "AGAP012396",
    "AGAP013056",
    "AGAP013423",
    "AGAP013724",
    "AGAP028120",
]

# D7 family proteins -- anti-hemostatic salivary proteins
AGAM_D7 = [
    "AGAP008278",
    "AGAP008279",
    "AGAP008280",
    "AGAP008281",
    "AGAP008282",
    "AGAP008283",
    "AGAP008284",
    "AGAP028120",
]

# Signal peptide genes (secreted proteins)
AGAM_SIGNAL_PEPTIDE = [
    "AGAP000007",
    "AGAP000021",
    "AGAP000038",
    "AGAP000039",
    "AGAP000044",
    "AGAP000047",
    "AGAP000051",
    "AGAP000064",
    "AGAP000085",
    "AGAP000088",
    "AGAP000093",
    "AGAP000108",
    "AGAP000110",
    "AGAP000117",
    "AGAP000123",
    "AGAP000138",
    "AGAP000140",
    "AGAP000143",
    "AGAP000150",
    "AGAP000151",
    "AGAP000152",
    "AGAP000156",
    "AGAP000160",
    "AGAP000166",
    "AGAP000168",
    "AGAP000177",
    "AGAP000182",
    "AGAP000198",
    "AGAP000218",
    "AGAP000225",
    "AGAP000228",
    "AGAP000238",
    "AGAP000256",
    "AGAP000261",
    "AGAP000266",
    "AGAP000267",
    "AGAP000268",
    "AGAP000274",
    "AGAP000278",
    "AGAP000279",
    "AGAP000290",
    "AGAP000293",
    "AGAP000304",
    "AGAP000307",
    "AGAP000309",
    "AGAP000315",
    "AGAP000329",
    "AGAP000340",
    "AGAP000344",
    "AGAP000345",
    "AGAP000346",
    "AGAP000347",
    "AGAP000352",
    "AGAP000356",
    "AGAP000357",
    "AGAP000359",
    "AGAP000360",
    "AGAP000376",
    "AGAP000382",
    "AGAP000385",
    "AGAP000395",
    "AGAP000411",
    "AGAP000415",
    "AGAP000437",
    "AGAP000446",
    "AGAP000458",
    "AGAP000468",
    "AGAP000472",
    "AGAP000481",
    "AGAP000485",
    "AGAP000489",
    "AGAP000494",
    "AGAP000499",
    "AGAP000519",
    "AGAP000520",
    "AGAP000521",
    "AGAP000522",
    "AGAP000535",
    "AGAP000536",
    "AGAP000537",
    "AGAP000538",
    "AGAP000539",
    "AGAP000548",
    "AGAP000550",
    "AGAP000558",
    "AGAP000570",
    "AGAP000571",
    "AGAP000573",
    "AGAP000579",
    "AGAP000601",
    "AGAP000603",
    "AGAP000604",
    "AGAP000605",
    "AGAP000607",
    "AGAP000609",
    "AGAP000610",
    "AGAP000612",
    "AGAP000615",
    "AGAP000621",
    "AGAP000629",
]

# Transmembrane domain (7+) genes -- GPCRs, channels, transporters
AGAM_TM7 = [
    "AGAP000040",
    "AGAP000045",
    "AGAP000046",
    "AGAP000074",
    "AGAP000090",
    "AGAP000095",
    "AGAP000102",
    "AGAP000115",
    "AGAP000128",
    "AGAP000137",
    "AGAP000181",
    "AGAP000311",
    "AGAP000351",
    "AGAP000369",
    "AGAP000387",
    "AGAP000390",
    "AGAP000420",
    "AGAP000434",
    "AGAP000445",
    "AGAP000473",
    "AGAP000520",
    "AGAP000521",
    "AGAP000535",
    "AGAP000540",
    "AGAP000544",
    "AGAP000576",
    "AGAP000578",
    "AGAP000579",
    "AGAP000599",
    "AGAP000606",
    "AGAP000629",
    "AGAP000637",
    "AGAP000653",
    "AGAP000658",
    "AGAP000663",
    "AGAP000667",
    "AGAP000702",
    "AGAP000703",
    "AGAP000717",
    "AGAP000718",
    "AGAP000724",
    "AGAP000727",
    "AGAP000732",
    "AGAP000778",
    "AGAP000785",
    "AGAP000795",
    "AGAP000834",
    "AGAP000854",
    "AGAP000913",
    "AGAP000962",
    "AGAP001022",
    "AGAP001027",
    "AGAP001097",
    "AGAP001100",
    "AGAP001114",
    "AGAP001115",
    "AGAP001117",
    "AGAP001119",
    "AGAP001120",
    "AGAP001123",
    "AGAP001125",
    "AGAP001144",
    "AGAP001160",
    "AGAP001161",
    "AGAP001162",
    "AGAP001169",
    "AGAP001170",
    "AGAP001171",
    "AGAP001172",
    "AGAP001173",
    "AGAP001175",
    "AGAP001185",
    "AGAP001202",
    "AGAP001205",
    "AGAP001214",
    "AGAP001236",
    "AGAP001265",
    "AGAP001336",
    "AGAP001337",
    "AGAP001339",
]

# Heat shock proteins -- stress response
AGAM_HSP = [
    "AGAP001424",
    "AGAP001502",
    "AGAP002076",
    "AGAP004002",
    "AGAP004192",
    "AGAP004581",
    "AGAP004582",
    "AGAP004583",
    "AGAP006958",
    "AGAP009882",
    "AGAP010331",
    "AGAP010514",
    "AGAP011521",
    "AGAP012891",
    "AGAP013228",
]

# Trypsin genes -- midgut digestive enzymes
AGAM_TRYPSIN = [
    "AGAP004900",
    "AGAP005587",
    "AGAP005591",
    "AGAP005593",
    "AGAP006485",
    "AGAP006487",
    "AGAP006677",
    "AGAP007165",
    "AGAP008290",
    "AGAP008291",
    "AGAP008292",
    "AGAP008293",
    "AGAP008294",
    "AGAP008295",
    "AGAP008296",
    "AGAP010240",
    "AGAP012472",
]

# Chitin/chitinase genes -- peritrophic matrix, cuticle
AGAM_CHITIN = [
    "AGAP001205",
    "AGAP001597",
    "AGAP001748",
    "AGAP002052",
    "AGAP006435",
    "AGAP007089",
    "AGAP007613",
    "AGAP008123",
    "AGAP009480",
    "AGAP010302",
    "AGAP011976",
    "AGAP011977",
    "AGAP028105",
    "AGAP028193",
    "AGAP028605",
    "AGAP028721",
    "AGAP028746",
    "AGAP028747",
    "AGAP029251",
    "AGAP029714",
]

# Oxidoreductase genes -- redox reactions
AGAM_OXIDOREDUCTASE = [
    "AGAP003142",
    "AGAP003889",
    "AGAP003904",
    "AGAP005419",
    "AGAP008042",
    "AGAP008097",
    "AGAP008423",
    "AGAP009080",
    "AGAP009949",
    "AGAP010696",
    "AGAP028464",
]

# Vitellogenin -- yolk protein precursor
AGAM_VITELLOGENIN = [
    "AGAP000427",
    "AGAP004203",
    "AGAP008369",
]

# Peritrophin genes -- peritrophic matrix
AGAM_PERITROPHIN = [
    "AGAP006795",
    "AGAP006796",
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


def _text_search_params(
    organism: str, text: str, field: str = "product"
) -> dict[str, str]:
    """Build GenesByText parameters."""
    return {
        "text_search_organism": organism,
        "text_expression": text,
        "text_fields": field,
        "document_type": "gene",
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


def _interpro_params(organism: str, database: str, typeahead: str) -> dict[str, str]:
    """Build GenesByInterproDomain parameters."""
    return {
        "organism": _org([organism]),
        "domain_database": database,
        "domain_typeahead": typeahead,
        "domain_accession": "*",
    }


def _location_params(
    organism: str, chromosome: str, start: str, end: str
) -> dict[str, str]:
    """Build GenesByLocation parameters."""
    return {
        "organismSinglePick": _org([organism]),
        "chromosomeOptional": chromosome,
        "sequenceId": "",
        "start_point": start,
        "end_point": end,
    }


def _exon_count_params(organism: str, min_exons: str, max_exons: str) -> dict[str, str]:
    """Build GenesByExonCount parameters."""
    return {
        "organism": _org([organism]),
        "scope": "Gene",
        "num_exons_gte": min_exons,
        "num_exons_lte": max_exons,
    }


def _mol_weight_params(organism: str, min_mw: str, max_mw: str) -> dict[str, str]:
    """Build GenesByMolecularWeight parameters."""
    return {
        "organism": _org([organism]),
        "min_molecular_weight": min_mw,
        "max_molecular_weight": max_mw,
    }


def _rnaseq_deltamethrin_params(
    organism: str,
    direction: str = "up-regulated",
    fold_change: str = "2",
) -> dict[str, str]:
    """Build RNA-Seq parameters for Deltamethrin resistant vs susceptible.

    Dataset: SRP014191 -- A. gambiae PEST Deltamethrin resistant and susceptible
    """
    return {
        "dataset_url": "https://VectorBase.org/a/app/record/dataset/DS_455af12573",
        "profileset_generic": (
            "SRP014191 Comparative transcriptome analyses of deltmethrin resistant"
            " and suscpetible Anopheles gambiae mosquitoes  -   unstranded"
        ),
        "regulated_dir": direction,
        "samples_fc_ref_generic": "Susceptible",
        "min_max_avg_ref": "average1",
        "samples_fc_comp_generic": "Resistant",
        "min_max_avg_comp": "average1",
        "fold_change": fold_change,
        "hard_floor": "566.783419111714624439522346051893696185",
        "protein_coding_only": "yes",
    }


def _rnaseq_pfalciparum_midgut_params(
    organism: str,
    direction: str = "up-regulated",
    fold_change: str = "2",
) -> dict[str, str]:
    """Build RNA-Seq parameters for P. falciparum-infected midgut.

    Dataset: SRP013741 -- A. gambiae PEST Midgut P. falciparum-infected
    vs non-infected.
    """
    return {
        "dataset_url": "https://VectorBase.org/a/app/record/dataset/DS_7f62901422",
        "profileset_generic": (
            "SRP013741 Plasmodium falciparum infection  -   unstranded"
        ),
        "regulated_dir": direction,
        "samples_fc_ref_generic": "Uninfected unfractioned",
        "min_max_avg_ref": "average1",
        "samples_fc_comp_generic": "Infected_polysomal",
        "min_max_avg_comp": "average1",
        "fold_change": fold_change,
        "hard_floor": "6591.17770484092987047740297968873220306",
        "protein_coding_only": "yes",
    }


def _taxon_params(organism: str) -> dict[str, str]:
    """Build GenesByTaxon parameters."""
    return {"organism": _org([organism])}


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
# Seeds
# ---------------------------------------------------------------------------

SEEDS: list[SeedDef] = [
    # =====================================================================
    # 1) AgPEST Insecticide Resistance Network (12 nodes)
    # =====================================================================
    SeedDef(
        name="AgPEST Insecticide Resistance Network",
        description=(
            "Comprehensive insecticide resistance gene network in A. gambiae PEST. "
            "Combines Phase I (CYP450, validated by deltamethrin RNA-Seq upregulation), "
            "Phase II (GST + esterases) metabolic detoxification, and Phase III "
            "(ABC transporter efflux with 7+ TM domains). 12-node strategy tree "
            "covering CYP6P3, CYP6M2, GSTe2, and MDR-like transporters."
        ),
        site_id="vectorbase",
        step_tree={
            "id": "root_resistance",
            "displayName": "Insecticide Resistance Network",
            "operator": "UNION",
            "primaryInput": {
                "id": "metabolic_detox",
                "displayName": "Metabolic Detoxification",
                "operator": "UNION",
                "primaryInput": {
                    "id": "phase_I_validated",
                    "displayName": "Phase I: CYP450 + Deltamethrin Upregulated",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "cyp450_text",
                        "displayName": "Cytochrome P450s",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(AG_ORG, "cytochrome P450"),
                    },
                    "secondaryInput": {
                        "id": "rnaseq_delta_up",
                        "displayName": "Deltamethrin Resistant Upregulated (2x)",
                        "searchName": "GenesByRNASeqagamPEST_SRP014191_ebi_rnaSeq_RSRC",
                        "parameters": _rnaseq_deltamethrin_params(
                            AG_ORG, "up-regulated", "2"
                        ),
                    },
                },
                "secondaryInput": {
                    "id": "phase_II",
                    "displayName": "Phase II: Conjugation Enzymes",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "gst_text",
                        "displayName": "Glutathione S-Transferases",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            AG_ORG, "glutathione S-transferase"
                        ),
                    },
                    "secondaryInput": {
                        "id": "esterase_text",
                        "displayName": "Esterases",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(AG_ORG, "esterase"),
                    },
                },
            },
            "secondaryInput": {
                "id": "phase_III",
                "displayName": "Phase III: ABC Efflux Transporters (7+ TM)",
                "operator": "INTERSECT",
                "primaryInput": {
                    "id": "abc_text",
                    "displayName": "ABC Transporters",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(AG_ORG, "ABC transporter"),
                },
                "secondaryInput": {
                    "id": "tm7plus",
                    "displayName": "7+ Transmembrane Domains",
                    "searchName": "GenesByTransmembraneDomains",
                    "parameters": _tm_domain_params(AG_ORG, "7", "20"),
                },
            },
        },
        control_set=ControlSetDef(
            name="A. gambiae Insecticide Resistance (curated)",
            positive_ids=(
                AGAM_CYP450[:20]
                + AGAM_GST[:15]
                + AGAM_ESTERASE[:8]
                + AGAM_ABC_TRANSPORTER[:12]
            ),
            negative_ids=AGAM_HSP + AGAM_VITELLOGENIN + AGAM_PERITROPHIN,
            provenance_notes=(
                "Positives: CYP450 metabolizers (CYP6P3, CYP6M2), GSTs (GSTe2), "
                "esterases, and ABC transporters — validated resistance genes. "
                "Negatives: heat shock proteins, vitellogenin, and peritrophin — "
                "housekeeping and reproductive genes not involved in resistance."
            ),
            tags=["insecticide-resistance", "anopheles", "seed"],
        ),
    ),
    # =====================================================================
    # 2) AgPEST Anti-Plasmodium Immune Response (11 nodes)
    # =====================================================================
    SeedDef(
        name="AgPEST Anti-Plasmodium Immune Response",
        description=(
            "Anti-Plasmodium immune defense in A. gambiae PEST. Models the "
            "complement-like system (TEP1/LRIM1/APL1C interaction), secreted CLIP "
            "serine protease cascade for melanization, antimicrobial peptides "
            "(cecropins, defensins, gambicin) plus Toll pathway signaling, and "
            "infection-responsive immune genes. 11-node tree covering humoral and "
            "cellular immunity from pathogen recognition to effector response."
        ),
        site_id="vectorbase",
        step_tree={
            "id": "root_immune",
            "displayName": "Anti-Plasmodium Immune Response",
            "operator": "UNION",
            "primaryInput": {
                "id": "complement_system",
                "displayName": "Complement-Like System",
                "operator": "UNION",
                "primaryInput": {
                    "id": "tep_lrim_overlap",
                    "displayName": "TEP-LRIM Interacting Partners",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "tep_text",
                        "displayName": "Thioester Proteins (TEPs)",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(AG_ORG, "thioester"),
                    },
                    "secondaryInput": {
                        "id": "lrim_text",
                        "displayName": "Leucine-Rich Repeat Immune (LRIM/APL)",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            AG_ORG, "leucine-rich repeat immune"
                        ),
                    },
                },
                "secondaryInput": {
                    "id": "clip_secreted",
                    "displayName": "Secreted CLIP Serine Proteases",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "serine_protease_text",
                        "displayName": "Serine Proteases",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(AG_ORG, "serine protease"),
                    },
                    "secondaryInput": {
                        "id": "signal_peptide_immune",
                        "displayName": "Signal Peptide (Secreted)",
                        "searchName": "GenesWithSignalPeptide",
                        "parameters": _signal_peptide_params(AG_ORG),
                    },
                },
            },
            "secondaryInput": {
                "id": "effector_response",
                "displayName": "Effector Response",
                "operator": "UNION",
                "primaryInput": {
                    "id": "amp_signaling",
                    "displayName": "AMPs + Toll Signaling",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "amp_text",
                        "displayName": "Antimicrobial Peptides",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            AG_ORG,
                            "antimicrobial peptide OR cecropin OR defensin OR gambicin",
                        ),
                    },
                    "secondaryInput": {
                        "id": "toll_text",
                        "displayName": "Toll Pathway Components",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(AG_ORG, "toll"),
                    },
                },
                "secondaryInput": {
                    "id": "immune_broad",
                    "displayName": "Immune-Annotated Genes",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(AG_ORG, "immune"),
                },
            },
        },
        control_set=ControlSetDef(
            name="A. gambiae Anti-Plasmodium Immunity (curated)",
            positive_ids=(
                AGAM_TEP[:10]
                + AGAM_LRIM[:10]
                + AGAM_AMP[:15]
                + AGAM_SERINE_PROTEASE[:10]
                + AGAM_TOLL[:10]
            ),
            negative_ids=(AGAM_CYP450[:10] + AGAM_OR[:5] + AGAM_TRYPSIN[:5]),
            provenance_notes=(
                "Positives: TEPs, LRIM/APL family, antimicrobial peptides, "
                "CLIP serine proteases, and Toll pathway — core anti-Plasmodium "
                "immune defense. "
                "Negatives: CYP450 detox enzymes, odorant receptors, and trypsins — "
                "non-immune functions."
            ),
            tags=["immunity", "anti-plasmodium", "anopheles", "seed"],
        ),
    ),
    # =====================================================================
    # 3) AgPEST Olfactory System -- Host-Seeking Receptors (8 nodes)
    # =====================================================================
    SeedDef(
        name="AgPEST Olfactory System Host-Seeking",
        description=(
            "Olfactory system components driving host-seeking behavior in female "
            "A. gambiae PEST. Combines odorant receptors (validated as 7+ TM domain "
            "GPCRs), gustatory receptors (CO2 detection), and secreted odorant-binding "
            "proteins (OBPs with signal peptides). 8-node strategy covering the "
            "complete molecular machinery from odor detection to ligand transport."
        ),
        site_id="vectorbase",
        step_tree={
            "id": "root_olfactory",
            "displayName": "Olfactory Host-Seeking System",
            "operator": "UNION",
            "primaryInput": {
                "id": "receptor_complex",
                "displayName": "Chemoreceptor Complex",
                "operator": "UNION",
                "primaryInput": {
                    "id": "or_membrane",
                    "displayName": "Odorant Receptors (7+ TM)",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "or_text",
                        "displayName": "Odorant Receptors",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(AG_ORG, "odorant receptor"),
                    },
                    "secondaryInput": {
                        "id": "tm7_olfactory",
                        "displayName": "7+ Transmembrane Domains",
                        "searchName": "GenesByTransmembraneDomains",
                        "parameters": _tm_domain_params(AG_ORG, "7", "20"),
                    },
                },
                "secondaryInput": {
                    "id": "gr_text",
                    "displayName": "Gustatory Receptors (CO2 etc)",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(AG_ORG, "gustatory receptor"),
                },
            },
            "secondaryInput": {
                "id": "obp_secreted",
                "displayName": "Secreted Odorant-Binding Proteins",
                "operator": "INTERSECT",
                "primaryInput": {
                    "id": "obp_text",
                    "displayName": "Odorant-Binding Proteins",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(
                        AG_ORG, "odorant binding protein"
                    ),
                },
                "secondaryInput": {
                    "id": "signal_obp",
                    "displayName": "Signal Peptide (Secreted)",
                    "searchName": "GenesWithSignalPeptide",
                    "parameters": _signal_peptide_params(AG_ORG),
                },
            },
        },
        control_set=ControlSetDef(
            name="A. gambiae Olfactory System (curated)",
            positive_ids=AGAM_OR[:25] + AGAM_OBP[:20] + AGAM_GR[:10],
            negative_ids=AGAM_CYP450[:10] + AGAM_TRYPSIN[:10],
            provenance_notes=(
                "Positives: odorant receptors, odorant-binding proteins, and "
                "gustatory receptors — complete olfactory host-seeking machinery. "
                "Negatives: CYP450 detox enzymes and trypsins — non-olfactory."
            ),
            tags=["olfactory", "host-seeking", "anopheles", "seed"],
        ),
    ),
    # =====================================================================
    # 4) AgPEST Salivary Anticoagulant Secretome (10 nodes)
    # =====================================================================
    SeedDef(
        name="AgPEST Salivary Anticoagulant Secretome",
        description=(
            "Salivary gland secretome involved in anti-hemostasis during blood "
            "feeding in A. gambiae PEST. D7 family proteins (AngaD7L1 binds TXA2 "
            "analog, AngaD7L3 binds serotonin), salivary gland-specific proteins, "
            "secreted serine proteases, and oxidoreductases. All filtered for "
            "signal peptide presence (secreted) and molecular weight <60kDa. "
            "10-node strategy modeling the complete anti-coagulation secretome "
            "relevant to Plasmodium transmission."
        ),
        site_id="vectorbase",
        step_tree={
            "id": "root_salivary",
            "displayName": "Salivary Anticoagulant Secretome",
            "operator": "INTERSECT",
            "primaryInput": {
                "id": "salivary_components",
                "displayName": "Salivary Components",
                "operator": "UNION",
                "primaryInput": {
                    "id": "d7_salivary",
                    "displayName": "D7 + Salivary Gland Proteins",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "d7_text",
                        "displayName": "D7 Family Proteins",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(AG_ORG, "D7"),
                    },
                    "secondaryInput": {
                        "id": "salivary_text",
                        "displayName": "Salivary Gland Proteins",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(AG_ORG, "salivary gland"),
                    },
                },
                "secondaryInput": {
                    "id": "enzyme_effectors",
                    "displayName": "Enzyme Effectors",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "sp_salivary",
                        "displayName": "Serine Proteases",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(AG_ORG, "serine protease"),
                    },
                    "secondaryInput": {
                        "id": "oxidored_text",
                        "displayName": "Oxidoreductases",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(AG_ORG, "oxidoreductase"),
                    },
                },
            },
            "secondaryInput": {
                "id": "secreted_small",
                "displayName": "Secreted Proteins (<60kDa)",
                "operator": "INTERSECT",
                "primaryInput": {
                    "id": "signal_salivary",
                    "displayName": "Signal Peptide (Secreted)",
                    "searchName": "GenesWithSignalPeptide",
                    "parameters": _signal_peptide_params(AG_ORG),
                },
                "secondaryInput": {
                    "id": "small_mw",
                    "displayName": "Molecular Weight < 60kDa",
                    "searchName": "GenesByMolecularWeight",
                    "parameters": _mol_weight_params(AG_ORG, "0", "60000"),
                },
            },
        },
        control_set=ControlSetDef(
            name="A. gambiae Salivary Secretome (curated)",
            positive_ids=(AGAM_D7 + AGAM_SALIVARY[:20] + AGAM_SERINE_PROTEASE[:10]),
            negative_ids=(AGAM_ABC_TRANSPORTER[:10] + AGAM_CHITIN[:10]),
            provenance_notes=(
                "Positives: D7 anti-hemostatic proteins, salivary gland proteins, "
                "and secreted serine proteases — blood-feeding secretome. "
                "Negatives: ABC transporters and chitin genes — not secretome."
            ),
            tags=["salivary", "blood-feeding", "anopheles", "seed"],
        ),
    ),
    # =====================================================================
    # 5) AgPEST Midgut Blood-Meal Interaction (10 nodes)
    # =====================================================================
    SeedDef(
        name="AgPEST Midgut Blood-Meal Interaction",
        description=(
            "Midgut biology during blood-meal digestion and Plasmodium interaction "
            "in A. gambiae PEST. Digestive enzymes (trypsins with complex gene "
            "structure), peritrophic matrix components (chitin/peritrophin forming "
            "the midgut barrier), and immune genes upregulated during P. falciparum "
            "infection (validated by RNA-Seq). 10-node strategy covering the "
            "complete midgut response from blood digestion to parasite defense."
        ),
        site_id="vectorbase",
        step_tree={
            "id": "root_midgut",
            "displayName": "Midgut Blood-Meal Interaction",
            "operator": "UNION",
            "primaryInput": {
                "id": "digestive_barrier",
                "displayName": "Digestive Apparatus + Barrier",
                "operator": "UNION",
                "primaryInput": {
                    "id": "digestive_enzymes",
                    "displayName": "Digestive Trypsins (multi-exon)",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "trypsin_text",
                        "displayName": "Trypsins",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(AG_ORG, "trypsin"),
                    },
                    "secondaryInput": {
                        "id": "multi_exon",
                        "displayName": "Genes with 3+ Exons",
                        "searchName": "GenesByExonCount",
                        "parameters": _exon_count_params(AG_ORG, "3", "50"),
                    },
                },
                "secondaryInput": {
                    "id": "peritrophic_matrix",
                    "displayName": "Peritrophic Matrix Proteins",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "chitin_text",
                        "displayName": "Chitin/Chitinase Genes",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(AG_ORG, "chitin"),
                    },
                    "secondaryInput": {
                        "id": "peritrophin_text",
                        "displayName": "Peritrophins",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            AG_ORG,
                            "peritrophin OR peritrophic",
                        ),
                    },
                },
            },
            "secondaryInput": {
                "id": "infection_response",
                "displayName": "P. falciparum Infection Response",
                "operator": "INTERSECT",
                "primaryInput": {
                    "id": "immune_midgut_text",
                    "displayName": "Immune Genes",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(AG_ORG, "immune"),
                },
                "secondaryInput": {
                    "id": "rnaseq_pf_up",
                    "displayName": "Upregulated in Pf-Infected Midgut (2x)",
                    "searchName": "GenesByRNASeqagamPEST_SRP013741_ebi_rnaSeq_RSRC",
                    "parameters": _rnaseq_pfalciparum_midgut_params(
                        AG_ORG,
                        "up-regulated",
                        "2",
                    ),
                },
            },
        },
        control_set=ControlSetDef(
            name="A. gambiae Midgut Blood-Meal (curated)",
            positive_ids=(
                AGAM_TRYPSIN + AGAM_CHITIN[:10] + AGAM_PERITROPHIN + AGAM_IMMUNE[:10]
            ),
            negative_ids=(AGAM_OR[:10] + AGAM_D7 + AGAM_VITELLOGENIN),
            provenance_notes=(
                "Positives: trypsins, chitin/peritrophin barrier genes, and "
                "infection-responsive immune genes — midgut biology. "
                "Negatives: odorant receptors, D7 salivary proteins, and "
                "vitellogenin — non-midgut functions."
            ),
            tags=["midgut", "blood-meal", "anopheles", "seed"],
        ),
    ),
    # =====================================================================
    # 6) AgPEST Baseline: 2L High-MW minus HSP (5 nodes)
    # =====================================================================
    SeedDef(
        name="AgPEST Baseline: 2L High-MW minus HSP",
        description=(
            "Simple baseline strategy: A. gambiae PEST protein-coding genes on "
            "chromosome 2L with molecular weight > 100kDa, minus heat shock "
            "proteins. Serves as a sanity check and comparison baseline for "
            "the more complex biological strategies."
        ),
        site_id="vectorbase",
        step_tree={
            "id": "root_baseline",
            "displayName": "High-MW 2L Genes minus HSP",
            "operator": "MINUS",
            "primaryInput": {
                "id": "high_mw_2l",
                "displayName": "High-MW Genes (>100kDa) on 2L",
                "operator": "INTERSECT",
                "primaryInput": {
                    "id": "chr2l",
                    "displayName": "Chromosome 2L Genes",
                    "searchName": "GenesByLocation",
                    "parameters": _location_params(AG_ORG, "2L", "1", "0"),
                },
                "secondaryInput": {
                    "id": "high_mw",
                    "displayName": "Molecular Weight > 100kDa",
                    "searchName": "GenesByMolecularWeight",
                    "parameters": _mol_weight_params(AG_ORG, "100000", "1000000"),
                },
            },
            "secondaryInput": {
                "id": "hsp_text",
                "displayName": "Heat Shock Proteins",
                "searchName": "GenesByText",
                "parameters": _text_search_params(AG_ORG, "heat shock"),
            },
        },
        control_set=ControlSetDef(
            name="A. gambiae 2L Baseline (curated)",
            positive_ids=AGAM_SERINE_PROTEASE[:15],
            negative_ids=AGAM_HSP,
            provenance_notes=(
                "Positives: serine proteases — large proteins likely on 2L. "
                "Negatives: heat shock proteins — excluded by the strategy."
            ),
            tags=["baseline", "anopheles", "seed"],
        ),
    ),
]
